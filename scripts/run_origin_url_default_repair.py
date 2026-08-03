"""Run the mandatory bounded origin-URL repair cascade.

Default product behavior:

1. deterministic URL generation and HTTP probing;
2. Tavily search repair when stage 1 does not select a URL;
3. deep evidence grading of observed candidates;
4. one bounded LLM adjudication when deterministic evidence is ambiguous;
5. explicit operator-review, configuration-blocked, or repair-exhausted state.

The command is review-only. It never persists a candidate URL or mutates connector,
source, job, ranking, application, or scheduler state.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Mapping

import requests

from scripts.run_origin_evidence_adjudication import (
    HttpBudget,
    _safe_fetch,
    collect_artifact_candidates,
)
from scripts.run_origin_source_discovery_agent import (
    load_local_env_file,
    run_for_company as run_atomic_origin_discovery,
)
from src.search_intelligence.origin_llm_model_campaign_provider import adjudicate_model
from src.search_intelligence.origin_llm_model_campaign_types import (
    MODEL_PRICES_USD_PER_MILLION,
)
from src.search_intelligence.origin_source_evidence import (
    OriginEvidenceAssessment,
    assess_origin_evidence_candidate,
    decide_origin_evidence,
    should_request_llm_adjudication,
)
from src.search_intelligence.origin_url_default_repair import (
    blocked_stage,
    compatibility_payload,
    evidence_stage,
    finalize_outcome,
    selected_url,
    skipped_stage,
    stage_from_discovery,
)

RESULT = "ORIGIN_URL_DEFAULT_REPAIR_COMPLETED"


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


def _origin_args(args: argparse.Namespace, *, providers: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        target_location=args.target_location,
        reviewed_by=args.reviewed_by,
        timeout_seconds=args.timeout_seconds,
        max_candidates=args.max_url_candidates,
        market_evidence_limit=args.market_evidence_limit,
        search_provider=providers,
        search_query_limit=args.search_query_limit,
        search_max_results=args.search_max_results,
        search_timeout_seconds=args.search_timeout_seconds,
        search_depth=args.search_depth,
        search_results_json=args.search_results_json,
        no_probe=False,
    )


def _reserved_llm_cost_usd(args: argparse.Namespace) -> float | None:
    prices = MODEL_PRICES_USD_PER_MILLION.get(args.llm_model)
    if prices is None:
        return None
    input_price, output_price = prices
    return (
        args.llm_reserved_input_tokens * input_price / 1_000_000
        + args.llm_max_output_tokens * output_price / 1_000_000
    )


def _empty_evidence_payload(
    *,
    company_key: str,
    company_name: str,
    reason: str,
) -> dict[str, object]:
    return {
        "company_key": company_key,
        "company_name": company_name,
        "deterministic_decision": "no_candidates_after_provider_repair",
        "selected_candidate_id": None,
        "selected_url": None,
        "confidence_score": 0.0,
        "confidence_band": "none",
        "selection_margin": 0.0,
        "manual_review_required": False,
        "adjudication_reasons": [reason],
        "assessments": [],
        "reason": reason,
        "llm_eligible": False,
    }


def _deep_evidence_and_llm_repair(
    args: argparse.Namespace,
    *,
    discovery_payload: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object] | None, str | None, str | None]:
    company_key = str(discovery_payload.get("company_key") or "")
    company_name = str(discovery_payload.get("company_name") or company_key)
    candidates = collect_artifact_candidates(
        discovery_payload,
        maximum=args.max_evidence_candidates,
    )
    if not candidates:
        payload = _empty_evidence_payload(
            company_key=company_key,
            company_name=company_name,
            reason="No non-aggregator URL candidate remained after Tavily repair.",
        )
        return payload, None, None, None

    budget = HttpBudget(args.max_evidence_http_requests)
    session = requests.Session()
    assessments: list[OriginEvidenceAssessment] = []
    for index, candidate in enumerate(candidates, start=1):
        page = _safe_fetch(
            candidate.url,
            timeout_seconds=args.evidence_timeout_seconds,
            max_response_bytes=args.max_response_bytes,
            budget=budget,
            session=session,
        )
        assessments.append(
            assess_origin_evidence_candidate(
                candidate_id=f"C{index}",
                candidate=candidate,
                company_key=company_key,
                company_name=company_name,
                page=page,
                target_location=args.target_location,
                target_locale=args.target_locale,
            )
        )

    decision = decide_origin_evidence(
        company_key=company_key,
        company_name=company_name,
        assessments=assessments,
    )
    payload = decision.to_json()
    payload["reason"] = "; ".join(decision.adjudication_reasons)
    llm_eligible = should_request_llm_adjudication(decision)
    payload["llm_eligible"] = llm_eligible
    payload["http_request_attempts"] = budget.attempts

    if not llm_eligible:
        return payload, None, None, None
    if args.disable_llm:
        return payload, None, None, "llm_disabled_diagnostic_override"

    api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
    if _missing_secret(api_key):
        return payload, None, None, "missing_openai_api_key"
    if not args.llm_model:
        return payload, None, None, "missing_llm_model"

    reserved_cost = _reserved_llm_cost_usd(args)
    if reserved_cost is None:
        return payload, None, None, "missing_llm_price_reservation"
    if reserved_cost > args.max_estimated_llm_cost_usd_per_company:
        return payload, None, None, "llm_cost_reservation_exceeds_ceiling"

    observation = adjudicate_model(
        decision,
        api_key=api_key,
        model=args.llm_model,
        reasoning_effort=args.llm_reasoning_effort,
        max_output_tokens=args.llm_max_output_tokens,
        timeout_seconds=args.llm_timeout_seconds,
    )
    observation_payload = observation.to_json()
    observation_payload["pessimistic_reserved_cost_usd"] = round(reserved_cost, 8)
    result = observation.result
    recommended_url: str | None = None
    if result.adjudication is not None and result.adjudication.recommended_candidate_id:
        recommended_id = result.adjudication.recommended_candidate_id
        recommended = next(
            (item for item in assessments if item.candidate_id == recommended_id),
            None,
        )
        if recommended is not None:
            recommended_url = recommended.final_url
    return payload, observation_payload, recommended_url, None


def run_default_repair_for_company(
    args: argparse.Namespace,
    company_key: str,
) -> dict[str, object]:
    stages = []

    baseline = run_atomic_origin_discovery(
        _origin_args(args, providers=["none"]),
        company_key,
    )
    baseline_stage = stage_from_discovery("deterministic_baseline", baseline)
    stages.append(baseline_stage)
    company_name = str(baseline.get("company_name") or company_key)

    if selected_url(baseline):
        stages.append(
            skipped_stage(
                "tavily_repair",
                "Baseline selected a validated URL; provider repair was unnecessary.",
            )
        )
        stages.append(
            skipped_stage(
                "evidence_and_llm_repair",
                "Baseline selected a validated URL; deep repair was unnecessary.",
            )
        )
        outcome = finalize_outcome(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
        )
        return compatibility_payload(outcome, last_discovery_payload=baseline)

    if args.disable_tavily:
        stages.append(
            blocked_stage(
                "tavily_repair",
                "tavily_disabled_diagnostic_override",
                "Tavily repair is mandatory in the default product path.",
            )
        )
        stages.append(
            skipped_stage(
                "evidence_and_llm_repair",
                "Deep repair requires the provider-enriched candidate set.",
            )
        )
        outcome = finalize_outcome(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
        )
        return compatibility_payload(outcome, last_discovery_payload=baseline)

    tavily_key = str(os.getenv("TAVILY_API_KEY") or "").strip()
    if _missing_secret(tavily_key):
        stages.append(
            blocked_stage(
                "tavily_repair",
                "missing_tavily_api_key",
                "Tavily repair is mandatory after deterministic not_found.",
            )
        )
        stages.append(
            skipped_stage(
                "evidence_and_llm_repair",
                "Deep repair requires the provider-enriched candidate set.",
            )
        )
        outcome = finalize_outcome(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
        )
        return compatibility_payload(outcome, last_discovery_payload=baseline)

    tavily = run_atomic_origin_discovery(
        _origin_args(args, providers=["tavily"]),
        company_key,
    )
    stages.append(
        stage_from_discovery(
            "tavily_repair",
            tavily,
            provider_request_count=args.search_query_limit,
        )
    )
    if selected_url(tavily):
        stages.append(
            skipped_stage(
                "evidence_and_llm_repair",
                "Tavily repair selected a validated URL; deeper repair was unnecessary.",
            )
        )
        outcome = finalize_outcome(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
        )
        payload = compatibility_payload(outcome, last_discovery_payload=tavily)
        payload["baseline_result"] = baseline
        return payload

    evidence_payload, llm_observation, recommended_url, blocker = (
        _deep_evidence_and_llm_repair(args, discovery_payload=tavily)
    )
    llm_status: str | None = None
    llm_attempted = False
    llm_provider_request_count = 0
    if llm_observation is not None:
        provider_result = llm_observation.get("provider_result")
        if isinstance(provider_result, Mapping):
            llm_status = str(provider_result.get("status") or "") or None
            llm_attempted = bool(provider_result.get("request_attempted"))
            llm_provider_request_count = int(llm_attempted)

    stages.append(
        evidence_stage(
            evidence_payload,
            llm_attempted=llm_attempted,
            llm_status=llm_status,
            llm_recommended_url=recommended_url,
            llm_provider_request_count=llm_provider_request_count,
            blocker=blocker,
        )
    )
    outcome = finalize_outcome(
        company_key=company_key,
        company_name=company_name,
        stages=stages,
    )
    payload = compatibility_payload(outcome, last_discovery_payload=tavily)
    payload["baseline_result"] = baseline
    payload["evidence_review"] = evidence_payload
    payload["llm_observation"] = llm_observation
    return payload


def write_report(
    payloads: list[Mapping[str, object]],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_dir / f"origin_url_default_repair_{stamp}.json"
    report = {
        "schema_version": "origin_url_default_repair.v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "review_output_only_not_pipeline_input": True,
        "results": list(payloads),
    }
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the mandatory default origin URL repair cascade."
    )
    parser.add_argument("--company-key", action="append", required=True)
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--target-locale", default="de")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--max-url-candidates", type=int, default=12)
    parser.add_argument("--market-evidence-limit", type=int, default=30)
    parser.add_argument("--search-query-limit", type=int, default=4)
    parser.add_argument("--search-max-results", type=int, default=5)
    parser.add_argument("--search-timeout-seconds", type=float, default=8.0)
    parser.add_argument(
        "--search-depth",
        default="advanced",
        choices=("basic", "advanced"),
    )
    parser.add_argument("--search-results-json")
    parser.add_argument("--max-evidence-candidates", type=int, default=4)
    parser.add_argument("--max-evidence-http-requests", type=int, default=12)
    parser.add_argument("--evidence-timeout-seconds", type=float, default=8.0)
    parser.add_argument("--max-response-bytes", type=int, default=750_000)
    parser.add_argument(
        "--llm-model",
        default=os.getenv("ORIGIN_ADJUDICATION_MODEL", "gpt-5.4-mini"),
    )
    parser.add_argument("--llm-reasoning-effort", default="low")
    parser.add_argument("--llm-max-output-tokens", type=int, default=600)
    parser.add_argument("--llm-reserved-input-tokens", type=int, default=5000)
    parser.add_argument("--llm-timeout-seconds", type=float, default=60.0)
    parser.add_argument(
        "--max-estimated-llm-cost-usd-per-company",
        type=float,
        default=0.01,
    )
    parser.add_argument(
        "--disable-tavily",
        action="store_true",
        help="Diagnostic override only; produces a configuration-blocked result.",
    )
    parser.add_argument(
        "--disable-llm",
        action="store_true",
        help="Diagnostic override only; blocks eligible LLM repair.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    if not 1 <= len(args.company_key) <= 5:
        raise SystemExit("--company-key requires between one and five values")
    if args.search_query_limit < 1 or args.search_query_limit > 6:
        raise SystemExit("--search-query-limit must be between 1 and 6")
    if args.max_evidence_candidates < 1 or args.max_evidence_candidates > 6:
        raise SystemExit("--max-evidence-candidates must be between 1 and 6")
    if args.max_evidence_http_requests < args.max_evidence_candidates:
        raise SystemExit(
            "--max-evidence-http-requests must cover at least one request per candidate"
        )
    if args.max_estimated_llm_cost_usd_per_company < 0:
        raise SystemExit("LLM cost ceiling must not be negative")

    payloads = [
        run_default_repair_for_company(args, company_key)
        for company_key in args.company_key
    ]
    for payload in payloads:
        repair = payload.get("default_repair")
        repair_map = repair if isinstance(repair, Mapping) else {}
        print(
            "origin_url_default_repair: "
            f"company_key={payload.get('company_key')} "
            f"final_state={repair_map.get('final_state')} "
            f"selected_url={repair_map.get('selected_url') or '<none>'} "
            f"recommended_url={repair_map.get('recommended_url') or '<none>'}"
        )
        for stage in repair_map.get("stages", []):
            if not isinstance(stage, Mapping):
                continue
            print(
                "  stage: "
                f"name={stage.get('name')} attempted={stage.get('attempted')} "
                f"status={stage.get('status')} decision={stage.get('decision')} "
                f"confidence={stage.get('confidence_score')} "
                f"provider_requests={stage.get('provider_request_count')} "
                f"blocker={stage.get('blocker') or '-'}"
            )

    path = write_report(payloads, args.output_dir)
    print(f"artifact_json: {path}")
    print(f"RESULT: {RESULT}")
    return 0


def main() -> None:
    load_local_env_file()
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
