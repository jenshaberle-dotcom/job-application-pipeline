"""Run origin repair with a true deterministic-before-provider boundary.

The adaptive runtime originally generated deterministic symbol-brand hosts and
Tavily results in one combined candidate batch. A deterministic hit could
therefore still incur every Tavily request and was reported as
``selected_tavily_repair``. This orchestrator preserves the existing helpers but
executes each source as a separate finite stage:

1. deterministic baseline;
2. deterministic symbol-brand and operator hypotheses;
3. Tavily adaptive search only after deterministic miss;
4. one early LLM search-hypothesis expansion;
5. deep evidence and optional late LLM adjudication.

No database or pipeline state is mutated.
"""

from __future__ import annotations

import argparse
import os
from typing import Mapping

from scripts import run_origin_url_adaptive_repair as adaptive
from scripts.run_origin_source_discovery_agent import load_local_env_file
from src.search_intelligence.adaptive_origin_search import (
    SearchProgressLedger,
    deterministic_brand_url_hypotheses,
    domain_followup_queries,
    initial_adaptive_queries,
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

RESULT = adaptive.RESULT
build_parser = adaptive.build_parser
write_report = adaptive.write_report


def _complete(
    *,
    company_key: str,
    company_name: str,
    stages: list[object],
    last_payload: Mapping[str, object],
    baseline: Mapping[str, object],
    trace: Mapping[str, object],
    ledger: SearchProgressLedger,
    early_llm_observation: Mapping[str, object] | None = None,
    evidence_review: Mapping[str, object] | None = None,
    late_llm_observation: Mapping[str, object] | None = None,
) -> dict[str, object]:
    outcome = finalize_outcome(
        company_key=company_key,
        company_name=company_name,
        stages=stages,  # type: ignore[arg-type]
    )
    payload = compatibility_payload(outcome, last_discovery_payload=last_payload)
    payload["baseline_result"] = dict(baseline)
    payload["adaptive_search"] = {**dict(trace), **ledger.to_json()}
    payload["score_semantics"] = {
        "selected_or_review_stage": "confidence_score",
        "not_found_stage": "best_observed_candidate_score_not_decision_confidence",
    }
    if early_llm_observation is not None:
        payload["early_llm_observation"] = dict(early_llm_observation)
    if evidence_review is not None:
        payload["evidence_review"] = dict(evidence_review)
    if late_llm_observation is not None:
        payload["llm_observation"] = dict(late_llm_observation)
    return payload


def run_default_repair_for_company(
    args: argparse.Namespace,
    company_key: str,
) -> dict[str, object]:
    stages: list[object] = []
    ledger = SearchProgressLedger()
    discovery_payloads: list[Mapping[str, object]] = []
    trace: dict[str, object] = {
        "finite_state_machine": True,
        "identical_retry_forbidden": True,
        "deterministic_before_provider": True,
        "early_llm_role": "novel_search_hypotheses_only",
        "late_llm_role": "observed_evidence_adjudication_only",
    }

    baseline = adaptive.run_atomic_origin_discovery(
        adaptive._origin_args(args, providers=["none"]),
        company_key,
    )
    discovery_payloads.append(baseline)
    baseline_fingerprint, _ = ledger.record_state(baseline)
    trace["baseline_fingerprint"] = baseline_fingerprint
    stages.append(stage_from_discovery("deterministic_baseline", baseline))
    company_name = str(baseline.get("company_name") or company_key)

    if selected_url(baseline):
        stages.extend(
            [
                skipped_stage(
                    "deterministic_symbol_brand",
                    "Baseline selected a validated URL.",
                ),
                skipped_stage("tavily_repair", "Baseline selected a validated URL."),
                skipped_stage(
                    "llm_search_hypothesis_repair",
                    "Baseline selected a validated URL.",
                ),
                skipped_stage(
                    "evidence_and_llm_repair",
                    "Baseline selected a validated URL.",
                ),
            ]
        )
        return _complete(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
            last_payload=baseline,
            baseline=baseline,
            trace=trace,
            ledger=ledger,
        )

    deterministic_limit = int(adaptive._value(args, "max_brand_host_hypotheses", 6))
    direct_urls = ledger.novel_urls(
        deterministic_brand_url_hypotheses(
            company_name=company_name,
            company_key=company_key,
            maximum=deterministic_limit,
        )
    )
    operator_urls = ledger.novel_urls(
        str(item) for item in (adaptive._value(args, "operator_url", []) or [])
    )
    direct_rows = adaptive._hypothesis_rows(
        company_key=company_key,
        urls=direct_urls,
        provider="deterministic_symbol_brand",
        rationale="symbol-aware high-value career host hypothesis",
    )
    direct_rows.extend(
        adaptive._hypothesis_rows(
            company_key=company_key,
            urls=operator_urls,
            provider="operator_supplied_unvalidated",
            rationale="operator hint; still requires deterministic validation",
        )
    )
    if direct_rows:
        deterministic = adaptive._run_atomic_with_rows(
            args,
            company_key=company_key,
            rows=direct_rows,
        )
    else:
        deterministic = dict(baseline)
        deterministic["reason"] = "No novel deterministic brand-host hypothesis."
        deterministic["decision"] = "not_found"
        deterministic["selected_url"] = None
    discovery_payloads.append(deterministic)
    direct_fingerprint, direct_progressed = ledger.record_state(deterministic)
    deterministic["deterministic_symbol_brand_round"] = {
        "direct_url_hypotheses": list(direct_urls),
        "operator_urls": list(operator_urls),
        "provider_requests": 0,
        "candidate_rows": len(direct_rows),
        "state_fingerprint": direct_fingerprint,
        "state_progressed": direct_progressed,
    }
    stages.append(stage_from_discovery("deterministic_symbol_brand", deterministic))
    trace["deterministic_symbol_brand_round"] = deterministic[
        "deterministic_symbol_brand_round"
    ]

    if selected_url(deterministic):
        stages.extend(
            [
                skipped_stage(
                    "tavily_repair",
                    "Deterministic symbol-brand validation selected a URL; provider search was unnecessary.",
                ),
                skipped_stage(
                    "llm_search_hypothesis_repair",
                    "Deterministic symbol-brand validation selected a URL.",
                ),
                skipped_stage(
                    "evidence_and_llm_repair",
                    "Deterministic symbol-brand validation selected a URL.",
                ),
            ]
        )
        return _complete(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
            last_payload=deterministic,
            baseline=baseline,
            trace=trace,
            ledger=ledger,
        )

    if args.disable_tavily:
        stages.extend(
            [
                blocked_stage(
                    "tavily_repair",
                    "tavily_disabled_diagnostic_override",
                    "Tavily is mandatory only after both deterministic stages miss.",
                ),
                skipped_stage(
                    "llm_search_hypothesis_repair",
                    "Early LLM hypotheses require adaptive search context.",
                ),
                skipped_stage(
                    "evidence_and_llm_repair",
                    "Deep repair requires provider-enriched candidates.",
                ),
            ]
        )
        return _complete(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
            last_payload=deterministic,
            baseline=baseline,
            trace=trace,
            ledger=ledger,
        )

    tavily_key = str(os.getenv("TAVILY_API_KEY") or "").strip()
    if adaptive._missing_secret(tavily_key):
        stages.extend(
            [
                blocked_stage(
                    "tavily_repair",
                    "missing_tavily_api_key",
                    "Tavily is mandatory only after both deterministic stages miss.",
                ),
                skipped_stage(
                    "llm_search_hypothesis_repair",
                    "Early LLM hypotheses require adaptive search context.",
                ),
                skipped_stage(
                    "evidence_and_llm_repair",
                    "Deep repair requires provider-enriched candidates.",
                ),
            ]
        )
        return _complete(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
            last_payload=deterministic,
            baseline=baseline,
            trace=trace,
            ledger=ledger,
        )

    max_adaptive_candidates = int(adaptive._value(args, "max_adaptive_candidates", 18))
    initial_limit = int(
        adaptive._value(
            args,
            "initial_search_query_limit",
            min(int(adaptive._value(args, "search_query_limit", 4)), 5),
        )
    )
    followup_limit = int(adaptive._value(args, "domain_followup_query_limit", 3))
    initial_queries = ledger.novel_queries(
        initial_adaptive_queries(
            company_name=company_name,
            company_key=company_key,
            target_location=args.target_location,
            maximum=initial_limit,
        )
    )
    initial_rows, initial_requests = adaptive._search_rows(
        args,
        company_key=company_key,
        queries=initial_queries,
        ledger=ledger,
        maximum_results=max_adaptive_candidates,
    )
    followup_queries = ledger.novel_queries(
        domain_followup_queries(
            adaptive._domains_from_rows(initial_rows),
            maximum=followup_limit,
        )
    )
    followup_rows, followup_requests = adaptive._search_rows(
        args,
        company_key=company_key,
        queries=followup_queries,
        ledger=ledger,
        maximum_results=max(0, max_adaptive_candidates - len(initial_rows)),
    )
    search_rows = adaptive._dedupe_rows(
        [*initial_rows, *followup_rows],
        maximum=max_adaptive_candidates,
    )
    if search_rows:
        tavily = adaptive._run_atomic_with_rows(
            args,
            company_key=company_key,
            rows=search_rows,
        )
    else:
        tavily = dict(deterministic)
        tavily["decision"] = "not_found"
        tavily["selected_url"] = None
        tavily["reason"] = "Tavily completed without a novel non-aggregator URL."
    discovery_payloads.append(tavily)
    tavily_fingerprint, tavily_progressed = ledger.record_state(tavily)
    tavily["adaptive_search_round"] = {
        "initial_queries": list(initial_queries),
        "domain_followup_queries": list(followup_queries),
        "provider_requests": initial_requests + followup_requests,
        "candidate_rows": len(search_rows),
        "state_fingerprint": tavily_fingerprint,
        "state_progressed": tavily_progressed,
    }
    stages.append(
        stage_from_discovery(
            "tavily_repair",
            tavily,
            provider_request_count=initial_requests + followup_requests,
        )
    )
    trace["adaptive_round"] = tavily["adaptive_search_round"]

    if selected_url(tavily):
        stages.extend(
            [
                skipped_stage(
                    "llm_search_hypothesis_repair",
                    "Tavily search selected a validated URL.",
                ),
                skipped_stage(
                    "evidence_and_llm_repair",
                    "Tavily search selected a validated URL.",
                ),
            ]
        )
        return _complete(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
            last_payload=tavily,
            baseline=baseline,
            trace=trace,
            ledger=ledger,
        )

    early_observation, early_blocker = adaptive._early_llm_hypotheses(
        args,
        company_key=company_key,
        company_name=company_name,
        baseline=baseline,
        latest=tavily,
        ledger=ledger,
    )
    early_payload = None if early_observation is None else early_observation.to_json()
    latest_discovery: Mapping[str, object] = tavily
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
        llm_query_rows, llm_query_requests = adaptive._search_rows(
            args,
            company_key=company_key,
            queries=hypotheses.queries,
            ledger=ledger,
            maximum_results=max_adaptive_candidates,
        )
        llm_url_rows = adaptive._hypothesis_rows(
            company_key=company_key,
            urls=hypotheses.urls,
            provider="llm_search_hypothesis",
            rationale=hypotheses.rationale,
        )
        novel_rows = adaptive._dedupe_rows(
            [*llm_url_rows, *llm_query_rows],
            maximum=max_adaptive_candidates,
        )
        if novel_rows:
            llm_discovery = adaptive._run_atomic_with_rows(
                args,
                company_key=company_key,
                rows=novel_rows,
            )
            discovery_payloads.append(llm_discovery)
            llm_fingerprint, llm_progressed = ledger.record_state(llm_discovery)
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
            trace["llm_hypothesis_round"] = llm_discovery[
                "llm_search_hypothesis_round"
            ]
        else:
            no_progress = dict(tavily)
            no_progress["reason"] = (
                "Early LLM returned no novel query or URL after anti-repeat filtering."
            )
            stages.append(
                stage_from_discovery(
                    "llm_search_hypothesis_repair",
                    no_progress,
                    provider_request_count=1,
                )
            )
            trace["llm_hypothesis_round"] = {
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
        return _complete(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
            last_payload=latest_discovery,
            baseline=baseline,
            trace=trace,
            ledger=ledger,
            early_llm_observation=early_payload,
        )

    merged = adaptive._merge_payloads(discovery_payloads)
    evidence_payload, late_observation, recommended_url, evidence_blocker = (
        adaptive._deep_evidence_and_late_llm_repair(
            args,
            discovery_payload=merged,
        )
    )
    late_status: str | None = None
    late_attempted = False
    late_request_count = 0
    if late_observation is not None:
        provider_result = late_observation.get("provider_result")
        if isinstance(provider_result, Mapping):
            late_status = str(provider_result.get("status") or "") or None
            late_attempted = bool(provider_result.get("request_attempted"))
            late_request_count = int(late_attempted)
    stages.append(
        evidence_stage(
            evidence_payload,
            llm_attempted=late_attempted,
            llm_status=late_status,
            llm_recommended_url=recommended_url,
            llm_provider_request_count=late_request_count,
            blocker=evidence_blocker,
        )
    )
    return _complete(
        company_key=company_key,
        company_name=company_name,
        stages=stages,
        last_payload=merged,
        baseline=baseline,
        trace=trace,
        ledger=ledger,
        early_llm_observation=early_payload,
        evidence_review=evidence_payload,
        late_llm_observation=late_observation,
    )


def _validate_args(args: argparse.Namespace) -> None:
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
        raise SystemExit("evidence HTTP budget must cover every evidence candidate")
    if args.max_estimated_llm_cost_usd_per_company < 0:
        raise SystemExit("late LLM cost ceiling must not be negative")
    if args.max_search_llm_cost_usd_per_company < 0:
        raise SystemExit("early LLM cost ceiling must not be negative")


def run(args: argparse.Namespace) -> int:
    _validate_args(args)
    payloads = [run_default_repair_for_company(args, key) for key in args.company_key]
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
            score_name = (
                "best_candidate_score"
                if stage.get("status") == "not_found"
                else "confidence"
            )
            print(
                "  stage: "
                f"name={stage.get('name')} attempted={stage.get('attempted')} "
                f"status={stage.get('status')} decision={stage.get('decision')} "
                f"{score_name}={stage.get('confidence_score')} "
                f"provider_requests={stage.get('provider_request_count')} "
                f"blocker={stage.get('blocker') or '-'}"
            )
        search = payload.get("adaptive_search")
        if isinstance(search, Mapping):
            print(
                "  anti_repeat: "
                f"queries={len(search.get('attempted_queries', []))} "
                f"urls={len(search.get('attempted_urls', []))} "
                f"repeated_state={search.get('repeated_state_detected')}"
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
