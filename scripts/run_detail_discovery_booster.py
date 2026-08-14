"""Run one bounded LLM-BOOST-001 Detail Discovery booster.

The command first runs the existing DETAIL-001 repair logic with external search
explicitly disabled.  Only that provider-free D0 result may unlock the shared
search/model cascade.  Tavily/model stages propose URLs only; every proposal is
shape-checked, boundedly fetched and routed through the existing same-base-domain
and concrete-detail validator before Detail Discovery can resolve.

This command has no database write path and never applies a detail gate.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Mapping, Sequence

from scripts.run_employer_origin_detail_evidence_repair_agent import (
    DEFAULT_LOCATION_TERMS,
    DEFAULT_PROFILE_TERMS,
    LinkCandidate,
    SourceCandidate,
    build_repair_outcome,
    concrete_job_detail_url,
    plausible_origin_url,
    unique_ordered,
    validate_detail_candidates,
)
from scripts.run_origin_source_discovery_agent import load_local_env_file, web_search
from src.search_intelligence.detail_discovery_booster_execution import (
    DetailCandidateValidationObservation,
    DetailDiscoveryHypothesisObservation,
    execute_detail_discovery_booster,
)
from src.search_intelligence.detail_discovery_gap import analyze_detail_discovery_gap
from src.search_intelligence.detail_discovery_hypothesis_provider import (
    request_detail_discovery_hypotheses,
)
from src.search_intelligence.llm_booster_policy import (
    HARD_COST_CEILING_USD,
    MODEL_CONFIG,
    BoosterStage,
)
from src.search_intelligence.origin_llm_model_campaign_types import (
    MODEL_PRICES_USD_PER_MILLION,
)
from src.search_intelligence.tavily_budget_policy import classify_tavily_budget

RESULT = "DETAIL_DISCOVERY_BOOSTER_COMPLETED"


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
) -> DetailDiscoveryHypothesisObservation:
    model, _reasoning = MODEL_CONFIG[stage]
    return DetailDiscoveryHypothesisObservation(
        status=status,
        request_attempted=False,
        urls=(),
        model=model,
        response_id=None,
        estimated_cost_usd=0.0,
        rationale=message[:700],
        product_authority=False,
    )


def _candidate_from_args(args: argparse.Namespace) -> SourceCandidate:
    return SourceCandidate(
        id=args.candidate_id,
        company_key=args.company_key,
        company_name=args.company_name,
        candidate_url=args.candidate_url,
        source_name_candidate=args.source_name,
        source_family_candidate=args.source_family,
        source_target_candidate=args.source_target,
        source_type_candidate=args.source_type,
        status=args.candidate_status,
        risk_level=args.risk_level,
    )


def _detail_terms(args: argparse.Namespace) -> tuple[tuple[str, ...], tuple[str, ...]]:
    profile_terms = unique_ordered(
        [*DEFAULT_PROFILE_TERMS, *(args.profile_term or [])]
    )
    location_terms = unique_ordered(
        [*DEFAULT_LOCATION_TERMS, *(args.location_term or [])]
    )
    if args.target_location:
        location_terms = unique_ordered([args.target_location, *location_terms])
    return profile_terms, location_terms


def _initial_candidate_summaries(
    evidence: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    raw = evidence.get("authoritative_detail_assessments")
    if not isinstance(raw, list):
        return ()
    result: list[Mapping[str, object]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        summary = dict(item)
        summary["source_stage"] = "deterministic"
        summary["deterministic_validation_required"] = False
        summary["product_authority"] = False
        result.append(summary)
    return tuple(result)


def _seed_urls(evidence: Mapping[str, object]) -> tuple[str, ...]:
    raw = evidence.get("preliminary_detail_candidates")
    if not isinstance(raw, list):
        return ()
    result: list[str] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        url = str(item.get("url") or item.get("final_url") or "").strip()
        if url:
            result.append(url)
    return tuple(result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run canonical search-first Detail Discovery booster."
    )
    parser.add_argument("--candidate-id", type=int, required=True)
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--candidate-url", required=True)
    parser.add_argument("--source-name", default="detail-discovery-shadow")
    parser.add_argument("--source-family", default="employer_origin")
    parser.add_argument("--source-target", default="hannover")
    parser.add_argument(
        "--source-type", default="employer_origin_career_site"
    )
    parser.add_argument("--candidate-status", default="manual_review")
    parser.add_argument("--risk-level", default="low")
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--profile-term", action="append")
    parser.add_argument("--location-term", action="append")
    parser.add_argument("--max-d0-seed-pages", type=int, default=8)
    parser.add_argument("--max-d0-detail-pages", type=int, default=6)
    parser.add_argument("--tavily-remaining-credits", type=int, default=None)
    parser.add_argument("--disable-tavily", action="store_true")
    parser.add_argument("--tavily-provider-unavailable", action="store_true")
    parser.add_argument("--disable-llm", action="store_true")
    parser.add_argument(
        "--search-depth", choices=("basic", "advanced"), default="advanced"
    )
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
    if args.candidate_id < 1:
        raise SystemExit("--candidate-id must be positive")
    if args.max_d0_seed_pages < 1 or args.max_d0_seed_pages > 20:
        raise SystemExit("--max-d0-seed-pages must be between 1 and 20")
    if args.max_d0_detail_pages < 1 or args.max_d0_detail_pages > 12:
        raise SystemExit("--max-d0-detail-pages must be between 1 and 12")
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
    candidate = _candidate_from_args(args)
    profile_terms, location_terms = _detail_terms(args)
    tavily_key = str(os.getenv("TAVILY_API_KEY") or "").strip()
    openai_key = str(os.getenv("OPENAI_API_KEY") or "").strip()

    d0 = build_repair_outcome(
        candidate=candidate,
        gates={},
        profile_terms=profile_terms,
        location_terms=location_terms,
        max_seed_pages=args.max_d0_seed_pages,
        max_detail_pages=args.max_d0_detail_pages,
        enable_search_discovery=False,
        max_search_queries=0,
        max_search_results=1,
    )
    deterministic_evidence = dict(d0.evidence)
    if deterministic_evidence.get("search_discovery_enabled") is not False:
        raise RuntimeError("DETAIL_D0_SEARCH_ISOLATION_BREACHED")

    tavily_budget = classify_tavily_budget(
        search_depth=args.search_depth,
        remaining_credits=args.tavily_remaining_credits,
        explicitly_disabled=args.disable_tavily,
        key_available=not _missing_secret(tavily_key),
        provider_available=not args.tavily_provider_unavailable,
    )
    gap = analyze_detail_discovery_gap(
        candidate_id=candidate.id,
        company_key=candidate.company_key,
        candidate_url=candidate.candidate_url,
        deterministic_evidence=deterministic_evidence,
        tavily_state=tavily_budget.state,
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

    def validate(url: str) -> DetailCandidateValidationObservation:
        if not concrete_job_detail_url(url):
            return DetailCandidateValidationObservation(
                candidate_url=url,
                accepted=False,
                final_url=None,
                classification="rejected",
                failure_reason="not_concrete_job_detail_url",
                evidence={"network_request_attempted": False},
            )
        if not plausible_origin_url(url, candidate):
            return DetailCandidateValidationObservation(
                candidate_url=url,
                accepted=False,
                final_url=None,
                classification="rejected",
                failure_reason="domain_not_plausible",
                evidence={"network_request_attempted": False},
            )
        link = LinkCandidate(
            url=url,
            source_url=candidate.candidate_url,
            text="semantic booster detail URL hypothesis",
            profile_terms=(),
            location_terms=(),
            reason="LLM-BOOST-001 candidate; deterministic validation required",
        )
        details, rejected, requested, assessments = validate_detail_candidates(
            candidate=candidate,
            link_candidates=(link,),
            profile_terms=profile_terms,
            location_terms=location_terms,
            max_detail_pages=1,
        )
        if details:
            detail = details[0]
            return DetailCandidateValidationObservation(
                candidate_url=url,
                accepted=True,
                final_url=detail.final_url,
                classification="accepted",
                failure_reason=None,
                evidence={
                    "network_request_attempted": True,
                    "requested_urls": list(requested),
                    "profile_terms": list(detail.profile_terms),
                    "location_terms": list(detail.location_terms),
                    "status_code": detail.status_code,
                    "title": detail.title,
                    "raw_html_persisted": False,
                },
            )
        assessment = assessments[0] if assessments else {}
        return DetailCandidateValidationObservation(
            candidate_url=url,
            accepted=False,
            final_url=None,
            classification=str(assessment.get("decision") or "rejected"),
            failure_reason=(
                str(assessment.get("failure_reason"))
                if assessment.get("failure_reason")
                else "deterministic_detail_validation_failed"
            ),
            evidence={
                "network_request_attempted": bool(requested),
                "requested_urls": list(requested),
                "rejected_urls": list(rejected),
                "assessment": dict(assessment),
                "raw_html_persisted": False,
            },
        )

    model_observations: list[dict[str, object]] = []

    def model(
        stage: BoosterStage,
        summaries: tuple[Mapping[str, object], ...],
        ledger,
    ) -> DetailDiscoveryHypothesisObservation:  # type: ignore[no-untyped-def]
        if args.disable_llm:
            observation = _blocked_observation(
                stage=stage,
                status="disabled",
                message="Detail Discovery model hypotheses disabled by runtime policy.",
            )
            model_observations.append(observation.to_json())
            return observation
        if _missing_secret(openai_key):
            observation = _blocked_observation(
                stage=stage,
                status="configuration_blocked",
                message="Detail Discovery hypotheses require the OpenAI provider key.",
            )
            model_observations.append(observation.to_json())
            return observation
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
            observation = _blocked_observation(
                stage=stage,
                status="configuration_blocked",
                message=f"No bounded price reservation exists for {model_name}.",
            )
            model_observations.append(observation.to_json())
            return observation
        if reserved_cost > ceiling:
            observation = _blocked_observation(
                stage=stage,
                status="configuration_blocked",
                message=(
                    f"Reserved {model_name} cost ${reserved_cost:.6f} exceeds "
                    f"the stage ceiling ${ceiling:.6f}."
                ),
            )
            model_observations.append(observation.to_json())
            return observation
        observation = request_detail_discovery_hypotheses(
            company_key=candidate.company_key,
            company_name=candidate.company_name,
            candidate_url=candidate.candidate_url,
            gap_evidence=gap.to_json(),
            attempted_candidate_summaries=summaries,
            ledger=ledger,
            api_key=openai_key,
            model=model_name,
            reasoning_effort=reasoning,
            max_output_tokens=max_output,
            timeout_seconds=args.model_timeout_seconds,
        )
        model_observations.append(observation.to_json())
        return observation

    execution = execute_detail_discovery_booster(
        company_name=candidate.company_name,
        candidate_url=candidate.candidate_url,
        decision=gap,
        max_tavily_requests=affordable_requests,
        search=search,
        validate=validate,
        model=model,
        seed_urls=_seed_urls(deterministic_evidence),
        initial_candidate_summaries=_initial_candidate_summaries(
            deterministic_evidence
        ),
    )
    payload: dict[str, object] = {
        "schema_version": "detail_discovery_booster.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "candidate": {
            "candidate_id": candidate.id,
            "company_key": candidate.company_key,
            "company_name": candidate.company_name,
            "candidate_url": candidate.candidate_url,
        },
        "deterministic_d0": {
            "gate_status": d0.gate_status,
            "decision": d0.decision,
            "stop_reason": d0.stop_reason,
            "evidence": deterministic_evidence,
        },
        "detail_discovery_gap": gap.to_json(),
        "tavily_budget": tavily_budget.to_json(),
        "affordable_tavily_requests": affordable_requests,
        "model_observations": model_observations,
        "execution": execution.to_json(),
        "boundary": {
            "d0_external_search_enabled": False,
            "database_requests": 0,
            "database_writes": 0,
            "detail_gate_write": False,
            "product_writes": 0,
            "product_authority": False,
            "connector_build": False,
            "connector_registration": False,
            "source_activation": False,
            "raw_html_persisted": False,
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
        "detail_discovery_booster: "
        f"resolved={execution.get('resolved')} "
        f"resolved_url={execution.get('resolved_url') or '<deterministic-or-none>'} "
        f"provider_requests={execution.get('provider_requests')} "
        f"llm_requests={execution.get('llm_requests')}"
    )
    print(f"RESULT: {RESULT}")


if __name__ == "__main__":
    main()
