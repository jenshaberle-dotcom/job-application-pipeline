"""Run the bounded LLM-BOOST-001 Listing Discovery booster.

The command first performs the canonical deterministic Listing Surface Evidence
analysis. Provider stages are eligible only for a real external-information gap.
Tavily uses sanitized runtime-supplied non-PAYG credit telemetry; model output is
hypothesis-only and every proposed URL is re-fetched/revalidated before the
station can resolve. No database or product mutation exists in this command.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Mapping, Sequence

from scripts.run_origin_source_discovery_agent import load_local_env_file, web_search
from src.search_intelligence.connector_feasibility import bounded_fetch
from src.search_intelligence.listing_booster_execution import execute_listing_booster
from src.search_intelligence.listing_route_hypothesis_provider import (
    ListingRouteHypothesisObservation,
    request_listing_route_hypotheses,
)
from src.search_intelligence.listing_surface_evidence import analyze_listing_surface
from src.search_intelligence.llm_booster_policy import (
    HARD_COST_CEILING_USD,
    MODEL_CONFIG,
    BoosterStage,
)
from src.search_intelligence.origin_llm_model_campaign_types import (
    MODEL_PRICES_USD_PER_MILLION,
)
from src.search_intelligence.tavily_budget_policy import classify_tavily_budget

RESULT = "LISTING_DISCOVERY_BOOSTER_COMPLETED"


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
    *,
    model: str,
    reserved_input_tokens: int,
    max_output_tokens: int,
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
    *,
    stage: BoosterStage,
    status: str,
    failure_class: str,
    message: str,
) -> ListingRouteHypothesisObservation:
    model, _reasoning = MODEL_CONFIG[stage]
    return ListingRouteHypothesisObservation(
        status=status,
        request_attempted=False,
        model=model,
        response_id=None,
        latency_ms=0,
        estimated_cost_usd=0.0,
        packet_sha256="",
        urls=(),
        rationale="",
        product_authority=False,
        failure_class=failure_class,
        failure_message=message,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the canonical search-first Listing Discovery booster."
    )
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--origin-url", required=True)
    parser.add_argument(
        "--tavily-remaining-credits",
        type=int,
        default=None,
        help="Sanitized current non-PAYG Tavily credits supplied by Runtime.",
    )
    parser.add_argument("--disable-tavily", action="store_true")
    parser.add_argument("--tavily-provider-unavailable", action="store_true")
    parser.add_argument("--disable-llm", action="store_true")
    parser.add_argument("--search-depth", choices=("basic", "advanced"), default="advanced")
    parser.add_argument("--max-tavily-requests", type=int, default=2)
    parser.add_argument("--search-max-results", type=int, default=5)
    parser.add_argument("--search-timeout-seconds", type=float, default=20.0)
    parser.add_argument("--model-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--reserved-input-tokens", type=int, default=3500)
    parser.add_argument("--model-max-output-tokens", type=int, default=500)
    parser.add_argument("--luna-max-output-tokens", type=int, default=6000)
    parser.add_argument(
        "--previous-evidence-fingerprint",
        default=None,
        help="Accepted prior Listing evidence fingerprint; exact match suppresses all spend.",
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.tavily_remaining_credits is not None and args.tavily_remaining_credits < 0:
        raise SystemExit("--tavily-remaining-credits must not be negative")
    if not 0 <= args.max_tavily_requests <= 3:
        raise SystemExit("--max-tavily-requests must be between 0 and 3")
    if args.search_max_results < 1 or args.search_max_results > 10:
        raise SystemExit("--search-max-results must be between 1 and 10")
    if args.reserved_input_tokens < 1:
        raise SystemExit("--reserved-input-tokens must be positive")
    if args.model_max_output_tokens < 1 or args.luna_max_output_tokens < 1:
        raise SystemExit("model output token bounds must be positive")


def run(args: argparse.Namespace) -> dict[str, object]:
    _validate_args(args)
    tavily_key = str(os.getenv("TAVILY_API_KEY") or "").strip()
    openai_key = str(os.getenv("OPENAI_API_KEY") or "").strip()

    origin_fetch = bounded_fetch(args.origin_url)
    deterministic = analyze_listing_surface(
        origin_url=args.origin_url,
        fetch_result=origin_fetch,
    )
    tavily_budget = classify_tavily_budget(
        search_depth=args.search_depth,
        remaining_credits=args.tavily_remaining_credits,
        explicitly_disabled=args.disable_tavily,
        key_available=not _missing_secret(tavily_key),
        provider_available=not args.tavily_provider_unavailable,
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

    def fetch(url: str):  # type: ignore[no-untyped-def]
        return bounded_fetch(url)

    def model(
        stage: BoosterStage,
        summaries: tuple[Mapping[str, object], ...],
        ledger,
    ) -> ListingRouteHypothesisObservation:  # type: ignore[no-untyped-def]
        if args.disable_llm:
            return _blocked_observation(
                stage=stage,
                status="disabled",
                failure_class="llm_disabled",
                message="Listing model hypotheses disabled by explicit runtime policy.",
            )
        if _missing_secret(openai_key):
            return _blocked_observation(
                stage=stage,
                status="configuration_blocked",
                failure_class="missing_openai_api_key",
                message="Listing model hypotheses require the OpenAI provider key.",
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
                failure_class="missing_model_price_reservation",
                message=f"No bounded price reservation exists for {model_name}.",
            )
        if reserved_cost > ceiling:
            return _blocked_observation(
                stage=stage,
                status="configuration_blocked",
                failure_class="model_cost_reservation_exceeds_ceiling",
                message=(
                    f"Reserved {model_name} cost ${reserved_cost:.6f} exceeds "
                    f"the stage ceiling ${ceiling:.6f}."
                ),
            )
        observation = request_listing_route_hypotheses(
            company_key=args.company_key,
            company_name=args.company_name,
            origin_url=args.origin_url,
            deterministic_evidence=deterministic.to_json(),
            attempted_candidate_summaries=summaries,
            ledger=ledger,
            api_key=openai_key,
            model=model_name,
            reasoning_effort=reasoning,
            max_output_tokens=max_output,
            timeout_seconds=args.model_timeout_seconds,
        )
        payload = observation.to_json()
        payload["pessimistic_reserved_cost_usd"] = round(reserved_cost, 8)
        # The immutable observation type remains transport evidence; reservation
        # metadata is included in the outer execution report below.
        return observation

    execution = execute_listing_booster(
        company_name=args.company_name,
        deterministic_evidence=deterministic,
        tavily_state=tavily_budget.state,
        max_tavily_requests=affordable_requests,
        search=search,
        fetch=fetch,
        model=model,
        previous_evidence_fingerprint=args.previous_evidence_fingerprint,
    )
    payload = {
        "schema_version": "listing_discovery_booster.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "company_key": args.company_key,
        "company_name": args.company_name,
        "origin_url": args.origin_url,
        "deterministic_listing_evidence": deterministic.to_json(),
        "tavily_budget": tavily_budget.to_json(),
        "affordable_tavily_requests": affordable_requests,
        "execution": execution.to_json(),
        "boundary": {
            "database_requests": 0,
            "product_writes": 0,
            "product_authority": False,
            "connector_build": False,
            "connector_registration": False,
            "source_activation": False,
            "ranking_or_application_write": False,
        },
    }
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return payload


def main() -> None:
    load_local_env_file()
    args = build_parser().parse_args()
    payload = run(args)
    execution = payload["execution"]
    assert isinstance(execution, Mapping)
    print(
        "listing_discovery_booster: "
        f"resolved={execution.get('resolved')} "
        f"resolved_url={execution.get('resolved_url') or '<none>'} "
        f"provider_requests={execution.get('provider_requests')} "
        f"llm_requests={execution.get('llm_requests')}"
    )
    print(f"evidence_fingerprint={payload['deterministic_listing_evidence']['evidence_fingerprint']}")  # type: ignore[index]
    print(f"RESULT: {RESULT}")


if __name__ == "__main__":
    main()
