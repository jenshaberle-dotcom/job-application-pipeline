"""Run the bounded adaptive origin-URL repair cascade.

The runtime is an intentionally finite search automaton:

1. deterministic baseline;
2. symbol-aware brand hosts plus adaptive Tavily queries;
3. corporate-domain follow-up queries;
4. one early LLM request for novel search/URL hypotheses;
5. deterministic validation of only the novel hypotheses;
6. deep evidence grading;
7. one late LLM adjudication when the evidence itself is ambiguous.

No stage may repeat an already attempted query or URL. A repeated discovery-state
fingerprint is recorded as no progress and cannot trigger another loop. The
command is review-only and never persists or activates an origin source.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from typing import Iterable, Mapping, Sequence
from urllib.parse import urlparse

import requests

from scripts.run_origin_evidence_adjudication import (
    HttpBudget,
    _safe_fetch,
    collect_artifact_candidates,
)
from scripts.run_origin_source_discovery_agent import (
    load_local_env_file,
    run_for_company as run_atomic_origin_discovery,
    web_search,
)
from src.search_intelligence.adaptive_origin_search import (
    SearchProgressLedger,
    deterministic_brand_url_hypotheses,
    domain_followup_queries,
    initial_adaptive_queries,
    normalize_url,
)
from src.search_intelligence.origin_llm_model_campaign_provider import adjudicate_model
from src.search_intelligence.origin_llm_model_campaign_types import (
    MODEL_PRICES_USD_PER_MILLION,
)
from src.search_intelligence.origin_search_hypothesis_provider import (
    SearchHypothesisObservation,
    request_search_hypotheses,
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


def _value(args: argparse.Namespace, name: str, default: object) -> object:
    return getattr(args, name, default)


def _origin_args(
    args: argparse.Namespace,
    *,
    providers: list[str],
    search_results_json: str | None = None,
    max_generated_candidates: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        target_location=args.target_location,
        reviewed_by=args.reviewed_by,
        timeout_seconds=args.timeout_seconds,
        max_candidates=(
            args.max_url_candidates
            if max_generated_candidates is None
            else max_generated_candidates
        ),
        market_evidence_limit=args.market_evidence_limit,
        search_provider=providers,
        search_query_limit=int(_value(args, "search_query_limit", 4)),
        search_max_results=args.search_max_results,
        search_timeout_seconds=args.search_timeout_seconds,
        search_depth=args.search_depth,
        search_results_json=search_results_json,
        no_probe=False,
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


def _late_llm_reserved_cost_usd(args: argparse.Namespace) -> float | None:
    return _reserved_cost_usd(
        model=args.llm_model,
        reserved_input_tokens=args.llm_reserved_input_tokens,
        max_output_tokens=args.llm_max_output_tokens,
    )


def _early_llm_reserved_cost_usd(args: argparse.Namespace) -> float | None:
    return _reserved_cost_usd(
        model=str(_value(args, "search_llm_model", args.llm_model)),
        reserved_input_tokens=int(
            _value(args, "search_llm_reserved_input_tokens", 3500)
        ),
        max_output_tokens=int(_value(args, "search_llm_max_output_tokens", 500)),
    )


def _row(
    *,
    company_key: str,
    url: str,
    provider: str,
    title: str,
    snippet: str,
    query: str,
) -> dict[str, object]:
    return {
        "company_key": company_key,
        "url": url,
        "provider": provider,
        "title": title,
        "snippet": snippet,
        "query": query,
    }


def _dedupe_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    maximum: int,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in rows:
        normalized = normalize_url(str(raw.get("url") or ""))
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        row = dict(raw)
        row["url"] = normalized
        result.append(row)
        if len(result) >= maximum:
            break
    return result


def _search_rows(
    args: argparse.Namespace,
    *,
    company_key: str,
    queries: Sequence[str],
    ledger: SearchProgressLedger,
    maximum_results: int,
) -> tuple[list[dict[str, object]], int]:
    rows: list[dict[str, object]] = []
    requests_made = 0
    for query in queries:
        if len(rows) >= maximum_results:
            break
        print(f"adaptive_web_search: provider=tavily query={query}")
        results = web_search(
            query,
            provider="tavily",
            max_results=args.search_max_results,
            timeout_seconds=args.search_timeout_seconds,
            search_depth=args.search_depth,
        )
        requests_made += 1
        for result in results:
            novel = ledger.novel_urls([result.url])
            if not novel:
                continue
            rows.append(
                _row(
                    company_key=company_key,
                    url=novel[0],
                    provider="tavily_adaptive_search",
                    title=result.title,
                    snippet=result.snippet,
                    query=query,
                )
            )
            if len(rows) >= maximum_results:
                break
    return rows, requests_made


def _hypothesis_rows(
    *,
    company_key: str,
    urls: Sequence[str],
    provider: str,
    rationale: str,
) -> list[dict[str, object]]:
    return [
        _row(
            company_key=company_key,
            url=url,
            provider=provider,
            title=f"{provider} URL hypothesis",
            snippet=rationale,
            query="",
        )
        for url in urls
    ]


def _run_atomic_with_rows(
    args: argparse.Namespace,
    *,
    company_key: str,
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        prefix="origin-adaptive-search-",
        delete=False,
    ) as handle:
        json.dump({"results": list(rows)}, handle, ensure_ascii=False)
        temp_path = Path(handle.name)
    try:
        return run_atomic_origin_discovery(
            _origin_args(
                args,
                providers=["none"],
                search_results_json=str(temp_path),
                max_generated_candidates=0,
            ),
            company_key,
        )
    finally:
        temp_path.unlink(missing_ok=True)


def _domains_from_rows(rows: Iterable[Mapping[str, object]]) -> tuple[str, ...]:
    domains: list[str] = []
    for row in rows:
        normalized = normalize_url(str(row.get("url") or ""))
        if normalized is None:
            continue
        host = str(urlparse(normalized).hostname or "").lower()
        if host and host not in domains:
            domains.append(host)
    return tuple(domains)


def _merge_payloads(
    payloads: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if not payloads:
        return {}
    result = dict(payloads[-1])
    merged_lists: dict[str, list[dict[str, object]]] = {
        "search_results": [],
        "alternatives": [],
        "rejected": [],
    }
    seen: dict[str, set[str]] = {key: set() for key in merged_lists}
    for payload in payloads:
        for key in merged_lists:
            rows = payload.get(key)
            if not isinstance(rows, list):
                continue
            for raw in rows:
                if not isinstance(raw, Mapping):
                    continue
                normalized = normalize_url(
                    str(raw.get("final_url") or raw.get("url") or "")
                )
                identity = normalized or json.dumps(
                    dict(raw), sort_keys=True, ensure_ascii=False
                )
                if identity in seen[key]:
                    continue
                seen[key].add(identity)
                merged_lists[key].append(dict(raw))
    for key, rows in merged_lists.items():
        result[key] = rows
    result["search_result_count"] = len(merged_lists["search_results"])
    result["candidate_count"] = sum(
        int(payload.get("candidate_count") or 0) for payload in payloads
    )
    result["assessed_count"] = sum(
        int(payload.get("assessed_count") or 0) for payload in payloads
    )
    best = max(
        payloads,
        key=lambda item: float(item.get("confidence_score") or 0.0),
    )
    if not selected_url(result):
        result["confidence_score"] = best.get("confidence_score")
        if any(payload.get("decision") == "manual_review_required" for payload in payloads):
            result["decision"] = "manual_review_required"
        else:
            result["decision"] = "not_found"
        result["selected_url"] = None
    return result


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


def _deep_evidence_and_late_llm_repair(
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
            reason="No non-aggregator URL candidate remained after adaptive repair.",
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

    reserved_cost = _late_llm_reserved_cost_usd(args)
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


def _early_llm_hypotheses(
    args: argparse.Namespace,
    *,
    company_key: str,
    company_name: str,
    baseline: Mapping[str, object],
    latest: Mapping[str, object],
    ledger: SearchProgressLedger,
) -> tuple[SearchHypothesisObservation | None, str | None]:
    if args.disable_llm:
        return None, "llm_disabled_diagnostic_override"
    api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
    if _missing_secret(api_key):
        return None, "missing_openai_api_key"

    model = str(_value(args, "search_llm_model", args.llm_model))
    reserved_cost = _early_llm_reserved_cost_usd(args)
    ceiling = float(_value(args, "max_search_llm_cost_usd_per_company", 0.01))
    if reserved_cost is None:
        return None, "missing_search_llm_price_reservation"
    if reserved_cost > ceiling:
        return None, "search_llm_cost_reservation_exceeds_ceiling"

    observation = request_search_hypotheses(
        company_key=company_key,
        company_name=company_name,
        baseline_payload=baseline,
        latest_payload=latest,
        ledger=ledger,
        api_key=api_key,
        model=model,
        reasoning_effort=str(_value(args, "search_llm_reasoning_effort", "low")),
        max_output_tokens=int(_value(args, "search_llm_max_output_tokens", 500)),
        timeout_seconds=float(_value(args, "search_llm_timeout_seconds", 60.0)),
    )
    if observation.status != "completed":
        return observation, "search_llm_provider_failed_closed"
    return observation, None


def run_default_repair_for_company(
    args: argparse.Namespace,
    company_key: str,
) -> dict[str, object]:
    stages = []
    ledger = SearchProgressLedger()
    discovery_payloads: list[Mapping[str, object]] = []
    adaptive_trace: dict[str, object] = {
        "finite_state_machine": True,
        "identical_retry_forbidden": True,
        "early_llm_role": "novel_search_hypotheses_only",
        "late_llm_role": "observed_evidence_adjudication_only",
    }

    baseline = run_atomic_origin_discovery(
        _origin_args(args, providers=["none"]),
        company_key,
    )
    discovery_payloads.append(baseline)
    baseline_fingerprint, _ = ledger.record_state(baseline)
    adaptive_trace["baseline_fingerprint"] = baseline_fingerprint
    stages.append(stage_from_discovery("deterministic_baseline", baseline))
    company_name = str(baseline.get("company_name") or company_key)

    if selected_url(baseline):
        stages.extend(
            [
                skipped_stage(
                    "tavily_repair",
                    "Baseline selected a validated URL; adaptive search was unnecessary.",
                ),
                skipped_stage(
                    "llm_search_hypothesis_repair",
                    "Baseline selected a validated URL; early LLM was unnecessary.",
                ),
                skipped_stage(
                    "evidence_and_llm_repair",
                    "Baseline selected a validated URL; deep repair was unnecessary.",
                ),
            ]
        )
        outcome = finalize_outcome(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
        )
        payload = compatibility_payload(outcome, last_discovery_payload=baseline)
        payload["adaptive_search"] = {**adaptive_trace, **ledger.to_json()}
        return payload

    if args.disable_tavily:
        stages.extend(
            [
                blocked_stage(
                    "tavily_repair",
                    "tavily_disabled_diagnostic_override",
                    "Adaptive Tavily repair is mandatory after baseline not_found.",
                ),
                skipped_stage(
                    "llm_search_hypothesis_repair",
                    "Early LLM hypotheses require the adaptive search context.",
                ),
                skipped_stage(
                    "evidence_and_llm_repair",
                    "Deep repair requires the provider-enriched candidate set.",
                ),
            ]
        )
        outcome = finalize_outcome(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
        )
        payload = compatibility_payload(outcome, last_discovery_payload=baseline)
        payload["adaptive_search"] = {**adaptive_trace, **ledger.to_json()}
        return payload

    tavily_key = str(os.getenv("TAVILY_API_KEY") or "").strip()
    if _missing_secret(tavily_key):
        stages.extend(
            [
                blocked_stage(
                    "tavily_repair",
                    "missing_tavily_api_key",
                    "Adaptive Tavily repair is mandatory after baseline not_found.",
                ),
                skipped_stage(
                    "llm_search_hypothesis_repair",
                    "Early LLM hypotheses require the adaptive search context.",
                ),
                skipped_stage(
                    "evidence_and_llm_repair",
                    "Deep repair requires the provider-enriched candidate set.",
                ),
            ]
        )
        outcome = finalize_outcome(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
        )
        payload = compatibility_payload(outcome, last_discovery_payload=baseline)
        payload["adaptive_search"] = {**adaptive_trace, **ledger.to_json()}
        return payload

    max_adaptive_candidates = int(_value(args, "max_adaptive_candidates", 18))
    deterministic_limit = int(_value(args, "max_brand_host_hypotheses", 6))
    initial_limit = int(
        _value(
            args,
            "initial_search_query_limit",
            min(int(_value(args, "search_query_limit", 4)), 5),
        )
    )
    followup_limit = int(_value(args, "domain_followup_query_limit", 3))

    direct_urls = ledger.novel_urls(
        deterministic_brand_url_hypotheses(
            company_name=company_name,
            company_key=company_key,
            maximum=deterministic_limit,
        )
    )
    operator_urls = ledger.novel_urls(
        str(item)
        for item in (_value(args, "operator_url", []) or [])
    )
    direct_rows = _hypothesis_rows(
        company_key=company_key,
        urls=direct_urls,
        provider="deterministic_symbol_brand",
        rationale="symbol-aware high-value career host hypothesis",
    )
    direct_rows.extend(
        _hypothesis_rows(
            company_key=company_key,
            urls=operator_urls,
            provider="operator_supplied_unvalidated",
            rationale="operator hint; still requires deterministic validation",
        )
    )

    initial_queries = ledger.novel_queries(
        initial_adaptive_queries(
            company_name=company_name,
            company_key=company_key,
            target_location=args.target_location,
            maximum=initial_limit,
        )
    )
    initial_rows, initial_requests = _search_rows(
        args,
        company_key=company_key,
        queries=initial_queries,
        ledger=ledger,
        maximum_results=max(0, max_adaptive_candidates - len(direct_rows)),
    )
    followup_queries = ledger.novel_queries(
        domain_followup_queries(
            _domains_from_rows(initial_rows),
            maximum=followup_limit,
        )
    )
    followup_rows, followup_requests = _search_rows(
        args,
        company_key=company_key,
        queries=followup_queries,
        ledger=ledger,
        maximum_results=max(
            0,
            max_adaptive_candidates - len(direct_rows) - len(initial_rows),
        ),
    )
    adaptive_rows = _dedupe_rows(
        [*direct_rows, *initial_rows, *followup_rows],
        maximum=max_adaptive_candidates,
    )
    adaptive = _run_atomic_with_rows(
        args,
        company_key=company_key,
        rows=adaptive_rows,
    )
    discovery_payloads.append(adaptive)
    adaptive_fingerprint, adaptive_progressed = ledger.record_state(adaptive)
    adaptive["reason"] = (
        str(adaptive.get("reason") or "")
        + "; adaptive human-search simulation "
        + ("changed discovery state" if adaptive_progressed else "made no state progress")
    ).strip("; ")
    adaptive["adaptive_search_round"] = {
        "direct_url_hypotheses": list(direct_urls),
        "operator_urls": list(operator_urls),
        "initial_queries": list(initial_queries),
        "domain_followup_queries": list(followup_queries),
        "provider_requests": initial_requests + followup_requests,
        "candidate_rows": len(adaptive_rows),
        "state_fingerprint": adaptive_fingerprint,
        "state_progressed": adaptive_progressed,
    }
    stages.append(
        stage_from_discovery(
            "tavily_repair",
            adaptive,
            provider_request_count=initial_requests + followup_requests,
        )
    )
    adaptive_trace["adaptive_round"] = adaptive["adaptive_search_round"]

    if selected_url(adaptive):
        stages.extend(
            [
                skipped_stage(
                    "llm_search_hypothesis_repair",
                    "Adaptive search selected a validated URL; early LLM was unnecessary.",
                ),
                skipped_stage(
                    "evidence_and_llm_repair",
                    "Adaptive search selected a validated URL; deep repair was unnecessary.",
                ),
            ]
        )
        outcome = finalize_outcome(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
        )
        payload = compatibility_payload(outcome, last_discovery_payload=adaptive)
        payload["baseline_result"] = baseline
        payload["adaptive_search"] = {**adaptive_trace, **ledger.to_json()}
        return payload

    early_observation, early_blocker = _early_llm_hypotheses(
        args,
        company_key=company_key,
        company_name=company_name,
        baseline=baseline,
        latest=adaptive,
        ledger=ledger,
    )
    early_payload = None if early_observation is None else early_observation.to_json()
    latest_discovery: Mapping[str, object] = adaptive
    if early_blocker:
        stages.append(
            blocked_stage(
                "llm_search_hypothesis_repair",
                early_blocker,
                "The bounded early LLM search-space expansion could not complete.",
            )
        )
    else:
        assert early_observation is not None
        hypotheses = early_observation.hypotheses
        assert hypotheses is not None
        llm_query_rows, llm_query_requests = _search_rows(
            args,
            company_key=company_key,
            queries=hypotheses.queries,
            ledger=ledger,
            maximum_results=max_adaptive_candidates,
        )
        llm_url_rows = _hypothesis_rows(
            company_key=company_key,
            urls=hypotheses.urls,
            provider="llm_search_hypothesis",
            rationale=hypotheses.rationale,
        )
        novel_rows = _dedupe_rows(
            [*llm_url_rows, *llm_query_rows],
            maximum=max_adaptive_candidates,
        )
        if novel_rows:
            llm_discovery = _run_atomic_with_rows(
                args,
                company_key=company_key,
                rows=novel_rows,
            )
            discovery_payloads.append(llm_discovery)
            llm_fingerprint, llm_progressed = ledger.record_state(llm_discovery)
            llm_discovery["reason"] = (
                str(llm_discovery.get("reason") or "")
                + "; early LLM added only novel hypotheses; "
                + ("state changed" if llm_progressed else "state fingerprint repeated")
            ).strip("; ")
            llm_discovery["llm_search_hypothesis_round"] = {
                "queries": list(hypotheses.queries),
                "urls": list(hypotheses.urls),
                "provider_requests": 1 + llm_query_requests,
                "candidate_rows": len(novel_rows),
                "state_fingerprint": llm_fingerprint,
                "state_progressed": llm_progressed,
                "no_repeat_guard_triggered": not llm_progressed,
            }
            stages.append(
                stage_from_discovery(
                    "llm_search_hypothesis_repair",
                    llm_discovery,
                    provider_request_count=1 + llm_query_requests,
                )
            )
            latest_discovery = llm_discovery
            adaptive_trace["llm_hypothesis_round"] = llm_discovery[
                "llm_search_hypothesis_round"
            ]
        else:
            no_progress = dict(adaptive)
            no_progress["reason"] = (
                "Early LLM completed but returned no novel query or URL after "
                "anti-repeat filtering. No repeated provider round was executed."
            )
            stages.append(
                stage_from_discovery(
                    "llm_search_hypothesis_repair",
                    no_progress,
                    provider_request_count=1,
                )
            )
            adaptive_trace["llm_hypothesis_round"] = {
                "queries": [],
                "urls": [],
                "provider_requests": 1,
                "candidate_rows": 0,
                "state_progressed": False,
                "no_repeat_guard_triggered": True,
            }

    if selected_url(latest_discovery):
        stages.append(
            skipped_stage(
                "evidence_and_llm_repair",
                "Early LLM hypotheses produced a deterministically selected URL.",
            )
        )
        outcome = finalize_outcome(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
        )
        payload = compatibility_payload(outcome, last_discovery_payload=latest_discovery)
        payload["baseline_result"] = baseline
        payload["early_llm_observation"] = early_payload
        payload["adaptive_search"] = {**adaptive_trace, **ledger.to_json()}
        return payload

    merged_discovery = _merge_payloads(discovery_payloads)
    evidence_payload, late_llm_observation, recommended_url, evidence_blocker = (
        _deep_evidence_and_late_llm_repair(
            args,
            discovery_payload=merged_discovery,
        )
    )
    late_status: str | None = None
    late_attempted = False
    late_provider_request_count = 0
    if late_llm_observation is not None:
        provider_result = late_llm_observation.get("provider_result")
        if isinstance(provider_result, Mapping):
            late_status = str(provider_result.get("status") or "") or None
            late_attempted = bool(provider_result.get("request_attempted"))
            late_provider_request_count = int(late_attempted)

    stages.append(
        evidence_stage(
            evidence_payload,
            llm_attempted=late_attempted,
            llm_status=late_status,
            llm_recommended_url=recommended_url,
            llm_provider_request_count=late_provider_request_count,
            blocker=evidence_blocker,
        )
    )
    outcome = finalize_outcome(
        company_key=company_key,
        company_name=company_name,
        stages=stages,
    )
    payload = compatibility_payload(outcome, last_discovery_payload=merged_discovery)
    payload["baseline_result"] = baseline
    payload["early_llm_observation"] = early_payload
    payload["evidence_review"] = evidence_payload
    payload["llm_observation"] = late_llm_observation
    payload["adaptive_search"] = {**adaptive_trace, **ledger.to_json()}
    return payload


def write_report(
    payloads: list[Mapping[str, object]],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_dir / f"origin_url_default_repair_{stamp}.json"
    report = {
        "schema_version": "origin_url_default_repair.v2",
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
        description="Run the mandatory adaptive origin URL repair cascade."
    )
    parser.add_argument("--company-key", action="append", required=True)
    parser.add_argument("--operator-url", action="append", default=[])
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--target-locale", default="de")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--max-url-candidates", type=int, default=12)
    parser.add_argument("--market-evidence-limit", type=int, default=30)
    parser.add_argument("--search-query-limit", type=int, default=5)
    parser.add_argument("--initial-search-query-limit", type=int, default=5)
    parser.add_argument("--domain-followup-query-limit", type=int, default=3)
    parser.add_argument("--max-brand-host-hypotheses", type=int, default=6)
    parser.add_argument("--max-adaptive-candidates", type=int, default=18)
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
        "--search-llm-model",
        default=os.getenv("ORIGIN_SEARCH_HYPOTHESIS_MODEL", "gpt-5.4-mini"),
    )
    parser.add_argument("--search-llm-reasoning-effort", default="low")
    parser.add_argument("--search-llm-max-output-tokens", type=int, default=500)
    parser.add_argument("--search-llm-reserved-input-tokens", type=int, default=3500)
    parser.add_argument("--search-llm-timeout-seconds", type=float, default=60.0)
    parser.add_argument(
        "--max-search-llm-cost-usd-per-company",
        type=float,
        default=0.01,
    )
    parser.add_argument("--disable-tavily", action="store_true")
    parser.add_argument("--disable-llm", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    if not 1 <= len(args.company_key) <= 5:
        raise SystemExit("--company-key requires between one and five values")
    if not 1 <= args.initial_search_query_limit <= 6:
        raise SystemExit("--initial-search-query-limit must be between 1 and 6")
    if not 0 <= args.domain_followup_query_limit <= 4:
        raise SystemExit("--domain-followup-query-limit must be between 0 and 4")
    if not 1 <= args.max_brand_host_hypotheses <= 12:
        raise SystemExit("--max-brand-host-hypotheses must be between 1 and 12")
    if not 4 <= args.max_adaptive_candidates <= 24:
        raise SystemExit("--max-adaptive-candidates must be between 4 and 24")
    if args.max_evidence_candidates < 1 or args.max_evidence_candidates > 6:
        raise SystemExit("--max-evidence-candidates must be between 1 and 6")
    if args.max_evidence_http_requests < args.max_evidence_candidates:
        raise SystemExit(
            "--max-evidence-http-requests must cover at least one request per candidate"
        )
    if args.max_estimated_llm_cost_usd_per_company < 0:
        raise SystemExit("late LLM cost ceiling must not be negative")
    if args.max_search_llm_cost_usd_per_company < 0:
        raise SystemExit("early LLM cost ceiling must not be negative")

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
        adaptive = payload.get("adaptive_search")
        if isinstance(adaptive, Mapping):
            print(
                "  anti_repeat: "
                f"queries={len(adaptive.get('attempted_queries', []))} "
                f"urls={len(adaptive.get('attempted_urls', []))} "
                f"repeated_state={adaptive.get('repeated_state_detected')}"
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
