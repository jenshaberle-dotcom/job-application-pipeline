"""Run one bounded LLM-BOOST-001 ATS authority-gap evidence acquisition.

The command consumes a *historical deterministic authority-attempt observation*.
It never fetches the blocked ATS evidence URL itself. Search/model stages may
only propose alternate ATS URLs; every proposal remains candidate evidence that
requires provider-specific deterministic authority validation.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Mapping, Sequence

from scripts.run_origin_source_discovery_agent import load_local_env_file, web_search
from src.search_intelligence.ats_authority_gap import (
    ATSAuthorityAttemptOutcome,
    analyze_ats_authority_gap,
    build_ats_authority_attempt_observation,
)
from src.search_intelligence.ats_authority_gap_execution import (
    ATSAuthorityHypothesisObservation,
    execute_ats_authority_gap_booster,
)
from src.search_intelligence.ats_authority_hypothesis_provider import (
    request_ats_authority_hypotheses,
)
from src.search_intelligence.ats_delegation_evidence import analyze_ats_delegation
from src.search_intelligence.llm_booster_policy import (
    HARD_COST_CEILING_USD,
    MODEL_CONFIG,
    BoosterStage,
)
from src.search_intelligence.origin_llm_model_campaign_types import (
    MODEL_PRICES_USD_PER_MILLION,
)
from src.search_intelligence.tavily_budget_policy import classify_tavily_budget

RESULT = "ATS_AUTHORITY_GAP_BOOSTER_COMPLETED"


def _missing_secret(value: str | None) -> bool:
    text = str(value or "").strip()
    lowered = text.lower()
    return (
        not text
        or text == "..."
        or text in {"<YOUR_API_KEY>", "YOUR_API_KEY", "changeme"}
        or "your_api_key" in lowered
        or "realer_key" in lowered
    )


def _reserved_cost_usd(
    *, model: str, reserved_input_tokens: int, max_output_tokens: int
) -> float | None:
    prices = MODEL_PRICES_USD_PER_MILLION.get(model)
    if prices is None:
        return None
    input_price, output_price = prices
    return (
        reserved_input_tokens * input_price / 1_000_000
        + max_output_tokens * output_price / 1_000_000
    )


def _blocked_observation(
    *, stage: BoosterStage, status: str, message: str
) -> ATSAuthorityHypothesisObservation:
    model, _reasoning = MODEL_CONFIG[stage]
    return ATSAuthorityHypothesisObservation(
        status=status,
        request_attempted=False,
        urls=(),
        model=model,
        response_id=None,
        estimated_cost_usd=0.0,
        rationale=message[:700],
        product_authority=False,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run bounded search-first ATS authority-gap evidence acquisition."
    )
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--evidence-url", required=True)
    parser.add_argument("--validation-contract", required=True)
    parser.add_argument("--expected-provider", required=True)
    parser.add_argument(
        "--attempt-outcome",
        choices=tuple(item.value for item in ATSAuthorityAttemptOutcome),
        required=True,
    )
    parser.add_argument("--attempt-http-status", type=int, default=None)
    parser.add_argument("--attempt-final-url", default=None)
    parser.add_argument("--tavily-remaining-credits", type=int, default=None)
    parser.add_argument("--disable-tavily", action="store_true")
    parser.add_argument("--tavily-provider-unavailable", action="store_true")
    parser.add_argument("--disable-llm", action="store_true")
    parser.add_argument("--search-depth", choices=("basic", "advanced"), default="advanced")
    parser.add_argument("--max-tavily-requests", type=int, default=1)
    parser.add_argument("--search-max-results", type=int, default=5)
    parser.add_argument("--search-timeout-seconds", type=float, default=20.0)
    parser.add_argument("--model-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--reserved-input-tokens", type=int, default=3500)
    parser.add_argument("--model-max-output-tokens", type=int, default=500)
    parser.add_argument("--luna-max-output-tokens", type=int, default=1200)
    parser.add_argument("--previous-gap-fingerprint", default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.tavily_remaining_credits is not None and args.tavily_remaining_credits < 0:
        raise SystemExit("--tavily-remaining-credits must not be negative")
    if not 0 <= args.max_tavily_requests <= 1:
        raise SystemExit("--max-tavily-requests must be 0 or 1")
    if not 1 <= args.search_max_results <= 10:
        raise SystemExit("--search-max-results must be between 1 and 10")
    if args.reserved_input_tokens < 1:
        raise SystemExit("--reserved-input-tokens must be positive")
    if args.model_max_output_tokens < 1 or args.luna_max_output_tokens < 1:
        raise SystemExit("model output token bounds must be positive")


def run(args: argparse.Namespace) -> dict[str, object]:
    _validate_args(args)
    tavily_key = str(os.getenv("TAVILY_API_KEY") or "").strip()
    openai_key = str(os.getenv("OPENAI_API_KEY") or "").strip()

    delegation = analyze_ats_delegation(
        candidate_urls=(args.target_url,),
        employer_backed_urls=(args.target_url,),
    )
    if delegation.provider != args.expected_provider:
        raise SystemExit(
            f"recognized ATS provider mismatch expected={args.expected_provider} "
            f"actual={delegation.provider or '<none>'}"
        )
    attempt = build_ats_authority_attempt_observation(
        provider=args.expected_provider,
        employer_identity=args.company_name,
        target_url=args.target_url,
        evidence_url=args.evidence_url,
        validation_contract=args.validation_contract,
        outcome=ATSAuthorityAttemptOutcome(args.attempt_outcome),
        http_status=args.attempt_http_status,
        final_url=args.attempt_final_url,
    )
    tavily_budget = classify_tavily_budget(
        search_depth=args.search_depth,
        remaining_credits=args.tavily_remaining_credits,
        explicitly_disabled=args.disable_tavily,
        key_available=not _missing_secret(tavily_key),
        provider_available=not args.tavily_provider_unavailable,
    )
    decision = analyze_ats_authority_gap(
        delegation_evidence=delegation,
        tavily_state=tavily_budget.state,
        authority_attempt=attempt,
        previous_gap_fingerprint=args.previous_gap_fingerprint,
    )
    affordable_requests = 0
    if tavily_budget.search_allowed and tavily_budget.remaining_credits is not None:
        affordable_requests = min(
            args.max_tavily_requests,
            tavily_budget.remaining_credits // tavily_budget.next_request_credits,
        )

    def search(query: str) -> Sequence[str]:
        results = web_search(
            query,
            provider="tavily",
            max_results=args.search_max_results,
            timeout_seconds=args.search_timeout_seconds,
            search_depth=args.search_depth,
        )
        return tuple(result.url for result in results)

    def model(
        stage: BoosterStage,
        summaries: tuple[Mapping[str, object], ...],
        ledger,
    ) -> ATSAuthorityHypothesisObservation:  # type: ignore[no-untyped-def]
        if args.disable_llm:
            return _blocked_observation(
                stage=stage,
                status="disabled",
                message="ATS model hypotheses disabled by explicit runtime policy.",
            )
        if _missing_secret(openai_key):
            return _blocked_observation(
                stage=stage,
                status="configuration_blocked",
                message="ATS model hypotheses require the OpenAI provider key.",
            )
        model_name, reasoning = MODEL_CONFIG[stage]
        max_output = (
            args.luna_max_output_tokens
            if stage == BoosterStage.LUNA_MAX
            else args.model_max_output_tokens
        )
        reserved_cost = _reserved_cost_usd(
            model=model_name,
            reserved_input_tokens=args.reserved_input_tokens,
            max_output_tokens=max_output,
        )
        ceiling = HARD_COST_CEILING_USD[stage]
        if reserved_cost is None:
            return _blocked_observation(
                stage=stage,
                status="configuration_blocked",
                message=f"No bounded price reservation exists for {model_name}.",
            )
        if reserved_cost > ceiling:
            return _blocked_observation(
                stage=stage,
                status="configuration_blocked",
                message=(
                    f"Reserved {model_name} cost ${reserved_cost:.6f} exceeds "
                    f"the stage ceiling ${ceiling:.6f}."
                ),
            )
        return request_ats_authority_hypotheses(
            company_key=args.company_key,
            company_name=args.company_name,
            expected_provider=args.expected_provider,
            authority_gap_evidence=decision.to_json(),
            attempted_candidate_summaries=summaries,
            ledger=ledger,
            api_key=openai_key,
            model=model_name,
            reasoning_effort=reasoning,
            max_output_tokens=max_output,
            timeout_seconds=args.model_timeout_seconds,
        )

    execution = execute_ats_authority_gap_booster(
        company_name=args.company_name,
        decision=decision,
        expected_provider=args.expected_provider,
        max_tavily_requests=affordable_requests,
        search=search,
        model=model,
        blocked_candidate_urls=(args.evidence_url,),
    )
    payload: dict[str, object] = {
        "schema_version": "ats_authority_gap_booster.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "company_key": args.company_key,
        "company_name": args.company_name,
        "expected_provider": args.expected_provider,
        "historical_authority_attempt": attempt.to_json(),
        "authority_gap_decision": decision.to_json(),
        "tavily_budget": tavily_budget.to_json(),
        "affordable_tavily_requests": affordable_requests,
        "execution": execution.to_json(),
        "boundary": {
            "blocked_evidence_url_network_replayed": False,
            "database_requests": 0,
            "database_writes": 0,
            "product_writes": 0,
            "tenant_authority": False,
            "delegation_permitted": False,
            "product_authority": False,
            "connector_build": False,
            "connector_registration": False,
            "source_activation": False,
        },
    }
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return payload


def main() -> None:
    load_local_env_file()
    args = build_parser().parse_args()
    payload = run(args)
    execution = payload["execution"]
    assert isinstance(execution, Mapping)
    print(
        "ats_authority_gap_booster: "
        f"candidate_found={execution.get('candidate_found')} "
        f"selected={execution.get('selected_candidate_url') or '<none>'} "
        f"provider_requests={execution.get('provider_requests')} "
        f"llm_requests={execution.get('llm_requests')}"
    )
    print(f"RESULT: {RESULT}")


if __name__ == "__main__":
    main()
