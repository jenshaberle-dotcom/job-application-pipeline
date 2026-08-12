"""Run origin repair with model-first direct hypotheses before Tavily.

Runtime evidence from job-pipeline-runtime#77 proved that most current deterministic
origin misses can be resolved by bounded direct URL hypotheses before spending a
search-provider credit. The generic finite controller therefore executes:

1. deterministic baseline;
2. deterministic symbol-brand/operator URL hypotheses;
3. primary direct URL hypotheses from the configured small search model;
4. direct URL hypothesis escalation from the configured stronger model;
5. Tavily only for the residual search space, using deferred model queries first;
6. deep evidence and optional late LLM adjudication.

Neither model may select an origin. Every direct URL hypothesis is passed through
the unchanged deterministic origin-discovery HTTP/company-identity/career gates.
Model-generated search queries are merely deferred inputs for Tavily. No database
or pipeline state is mutated.
"""

from __future__ import annotations

import argparse
import os
from typing import Mapping, Sequence

from scripts import run_origin_url_adaptive_repair as adaptive
from scripts.run_origin_source_discovery_agent import load_local_env_file
from src.search_intelligence.adaptive_origin_search import (
    SearchProgressLedger,
    deterministic_brand_url_hypotheses,
    domain_followup_queries,
    initial_adaptive_queries,
)
from src.search_intelligence.origin_url_default_repair import (
    RepairStage,
    blocked_stage,
    compatibility_payload,
    evidence_stage,
    finalize_outcome,
    selected_url,
    skipped_stage,
    stage_from_discovery,
)

RESULT = adaptive.RESULT
write_report = adaptive.write_report
PRIMARY_STAGE = "llm_search_hypothesis_repair"
ESCALATION_STAGE = "llm_search_hypothesis_escalation_repair"


def build_parser() -> argparse.ArgumentParser:
    parser = adaptive.build_parser()
    parser.add_argument(
        "--search-llm-escalation-model",
        default=os.getenv("ORIGIN_SEARCH_HYPOTHESIS_ESCALATION_MODEL", "gpt-5.5"),
    )
    parser.add_argument(
        "--max-search-llm-escalation-cost-usd-per-company",
        type=float,
        default=0.05,
    )
    return parser


def _complete(
    *,
    company_key: str,
    company_name: str,
    stages: list[RepairStage],
    last_payload: Mapping[str, object],
    baseline: Mapping[str, object],
    trace: Mapping[str, object],
    ledger: SearchProgressLedger,
    primary_observation: Mapping[str, object] | None = None,
    escalation_observation: Mapping[str, object] | None = None,
    evidence_review: Mapping[str, object] | None = None,
    late_llm_observation: Mapping[str, object] | None = None,
) -> dict[str, object]:
    outcome = finalize_outcome(
        company_key=company_key,
        company_name=company_name,
        stages=stages,
    )
    payload = compatibility_payload(outcome, last_discovery_payload=last_payload)
    payload["baseline_result"] = dict(baseline)
    payload["adaptive_search"] = {**dict(trace), **ledger.to_json()}
    payload["score_semantics"] = {
        "selected_or_review_stage": "confidence_score",
        "not_found_stage": "best_observed_candidate_score_not_decision_confidence",
    }
    if primary_observation is not None:
        # Compatibility key consumed by existing runtime/accounting code.
        payload["early_llm_observation"] = dict(primary_observation)
    if escalation_observation is not None:
        payload["search_llm_escalation_observation"] = dict(escalation_observation)
    if evidence_review is not None:
        payload["evidence_review"] = dict(evidence_review)
    if late_llm_observation is not None:
        payload["llm_observation"] = dict(late_llm_observation)
    return payload


def _blocked_model_stage(
    *,
    name: str,
    blocker: str,
    reason: str,
    request_attempted: bool,
) -> RepairStage:
    return RepairStage(
        name=name,
        attempted=request_attempted,
        status="configuration_blocked",
        decision=None,
        selected_url=None,
        recommended_url=None,
        confidence_score=0.0,
        candidate_count=0,
        provider_request_count=int(request_attempted),
        reason=reason,
        blocker=blocker,
    )


def _model_cost_reservation(
    args: argparse.Namespace,
    *,
    model: str,
) -> float | None:
    return adaptive._reserved_cost_usd(
        model=model,
        reserved_input_tokens=int(
            adaptive._value(args, "search_llm_reserved_input_tokens", 3500)
        ),
        max_output_tokens=int(adaptive._value(args, "search_llm_max_output_tokens", 500)),
    )


def _run_direct_model_stage(
    args: argparse.Namespace,
    *,
    company_key: str,
    company_name: str,
    baseline: Mapping[str, object],
    latest: Mapping[str, object],
    ledger: SearchProgressLedger,
    stage_name: str,
    model: str,
    cost_ceiling: float,
    provider_label: str,
) -> tuple[
    RepairStage,
    Mapping[str, object],
    dict[str, object] | None,
    tuple[str, ...],
]:
    api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
    if adaptive._missing_secret(api_key):
        return (
            _blocked_model_stage(
                name=stage_name,
                blocker="missing_openai_api_key",
                reason="Model-first origin hypotheses require the OpenAI provider key.",
                request_attempted=False,
            ),
            latest,
            None,
            (),
        )
    if not model:
        return (
            _blocked_model_stage(
                name=stage_name,
                blocker="missing_search_llm_model",
                reason="Model-first origin hypotheses require an explicit model.",
                request_attempted=False,
            ),
            latest,
            None,
            (),
        )

    reserved_cost = _model_cost_reservation(args, model=model)
    if reserved_cost is None:
        return (
            _blocked_model_stage(
                name=stage_name,
                blocker="missing_search_llm_price_reservation",
                reason=f"No bounded price reservation exists for {model}.",
                request_attempted=False,
            ),
            latest,
            None,
            (),
        )
    if reserved_cost > cost_ceiling:
        return (
            _blocked_model_stage(
                name=stage_name,
                blocker="search_llm_cost_reservation_exceeds_ceiling",
                reason=(
                    f"Reserved {model} hypothesis cost ${reserved_cost:.6f} exceeds "
                    f"the stage ceiling ${cost_ceiling:.6f}."
                ),
                request_attempted=False,
            ),
            latest,
            None,
            (),
        )

    observation = adaptive.request_search_hypotheses(
        company_key=company_key,
        company_name=company_name,
        baseline_payload=baseline,
        latest_payload=latest,
        ledger=ledger,
        api_key=api_key,
        model=model,
        reasoning_effort=str(
            adaptive._value(args, "search_llm_reasoning_effort", "low")
        ),
        max_output_tokens=int(adaptive._value(args, "search_llm_max_output_tokens", 500)),
        timeout_seconds=float(adaptive._value(args, "search_llm_timeout_seconds", 60.0)),
    )
    observation_payload = observation.to_json()
    observation_payload["pessimistic_reserved_cost_usd"] = round(reserved_cost, 8)
    if observation.status != "completed" or observation.hypotheses is None:
        return (
            _blocked_model_stage(
                name=stage_name,
                blocker="search_llm_provider_failed_closed",
                reason=(
                    f"{model} direct origin hypothesis request failed closed; "
                    "the next bounded recovery stage may still continue."
                ),
                request_attempted=observation.request_attempted,
            ),
            latest,
            observation_payload,
            (),
        )

    hypotheses = observation.hypotheses
    deferred_queries = tuple(hypotheses.queries)
    direct_rows = adaptive._hypothesis_rows(
        company_key=company_key,
        urls=hypotheses.urls,
        provider=provider_label,
        rationale=hypotheses.rationale,
    )
    if direct_rows:
        discovery = adaptive._run_atomic_with_rows(
            args,
            company_key=company_key,
            rows=direct_rows,
        )
    else:
        discovery = dict(latest)
        discovery["decision"] = "not_found"
        discovery["selected_url"] = None
        discovery["reason"] = (
            f"{model} returned no novel direct URL hypothesis; "
            "novel query hypotheses were deferred to Tavily."
        )

    fingerprint, progressed = ledger.record_state(discovery)
    discovery[f"{stage_name}_round"] = {
        "model": model,
        "queries_deferred": list(deferred_queries),
        "direct_url_hypotheses": list(hypotheses.urls),
        "provider_requests": 1,
        "candidate_rows": len(direct_rows),
        "state_fingerprint": fingerprint,
        "state_progressed": progressed,
        "no_repeat_guard_triggered": not progressed,
    }
    stage = stage_from_discovery(
        stage_name,
        discovery,
        provider_request_count=1,
    )
    return stage, discovery, observation_payload, deferred_queries


def _skipped_provider_tail(reason: str) -> list[RepairStage]:
    return [
        skipped_stage(ESCALATION_STAGE, reason),
        skipped_stage("tavily_repair", reason),
        skipped_stage("evidence_and_llm_repair", reason),
    ]


def run_default_repair_for_company(
    args: argparse.Namespace,
    company_key: str,
) -> dict[str, object]:
    stages: list[RepairStage] = []
    ledger = SearchProgressLedger()
    discovery_payloads: list[Mapping[str, object]] = []
    trace: dict[str, object] = {
        "finite_state_machine": True,
        "identical_retry_forbidden": True,
        "deterministic_before_provider": True,
        "provider_order": [
            "primary_direct_llm",
            "escalation_direct_llm",
            "tavily_residual_search",
            "deep_evidence",
        ],
        "primary_llm_role": "novel_direct_urls_and_deferred_search_queries",
        "escalation_llm_role": "novel_direct_urls_and_deferred_search_queries",
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
                skipped_stage("deterministic_symbol_brand", "Baseline selected a validated URL."),
                skipped_stage(PRIMARY_STAGE, "Baseline selected a validated URL."),
                *_skipped_provider_tail("Baseline selected a validated URL."),
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
                skipped_stage(PRIMARY_STAGE, "Deterministic validation selected a URL."),
                *_skipped_provider_tail("Deterministic validation selected a URL."),
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

    primary_payload: dict[str, object] | None = None
    escalation_payload: dict[str, object] | None = None
    deferred_queries: list[str] = []
    latest: Mapping[str, object] = deterministic

    if args.disable_llm:
        stages.extend(
            [
                skipped_stage(PRIMARY_STAGE, "Model hypotheses disabled by explicit runtime policy."),
                skipped_stage(ESCALATION_STAGE, "Model hypotheses disabled by explicit runtime policy."),
            ]
        )
    else:
        primary_model = str(adaptive._value(args, "search_llm_model", args.llm_model))
        primary_ceiling = float(
            adaptive._value(args, "max_search_llm_cost_usd_per_company", 0.01)
        )
        primary_stage, primary_discovery, primary_payload, primary_queries = (
            _run_direct_model_stage(
                args,
                company_key=company_key,
                company_name=company_name,
                baseline=baseline,
                latest=latest,
                ledger=ledger,
                stage_name=PRIMARY_STAGE,
                model=primary_model,
                cost_ceiling=primary_ceiling,
                provider_label="llm_primary_direct_url_hypothesis",
            )
        )
        stages.append(primary_stage)
        deferred_queries.extend(primary_queries)
        if primary_discovery is not latest:
            discovery_payloads.append(primary_discovery)
        latest = primary_discovery
        trace["primary_model"] = primary_model
        trace["primary_deferred_queries"] = list(primary_queries)

        if selected_url(latest):
            stages.extend(
                [
                    skipped_stage(ESCALATION_STAGE, "Primary model produced a validated direct URL."),
                    skipped_stage("tavily_repair", "Primary model produced a validated direct URL."),
                    skipped_stage("evidence_and_llm_repair", "Primary model produced a validated direct URL."),
                ]
            )
            return _complete(
                company_key=company_key,
                company_name=company_name,
                stages=stages,
                last_payload=latest,
                baseline=baseline,
                trace=trace,
                ledger=ledger,
                primary_observation=primary_payload,
            )

        escalation_model = str(
            adaptive._value(args, "search_llm_escalation_model", "gpt-5.5")
        )
        escalation_ceiling = float(
            adaptive._value(
                args,
                "max_search_llm_escalation_cost_usd_per_company",
                0.05,
            )
        )
        escalation_stage, escalation_discovery, escalation_payload, escalation_queries = (
            _run_direct_model_stage(
                args,
                company_key=company_key,
                company_name=company_name,
                baseline=baseline,
                latest=latest,
                ledger=ledger,
                stage_name=ESCALATION_STAGE,
                model=escalation_model,
                cost_ceiling=escalation_ceiling,
                provider_label="llm_escalation_direct_url_hypothesis",
            )
        )
        stages.append(escalation_stage)
        deferred_queries.extend(escalation_queries)
        if escalation_discovery is not latest:
            discovery_payloads.append(escalation_discovery)
        latest = escalation_discovery
        trace["escalation_model"] = escalation_model
        trace["escalation_deferred_queries"] = list(escalation_queries)

        if selected_url(latest):
            stages.extend(
                [
                    skipped_stage("tavily_repair", "Escalation model produced a validated direct URL."),
                    skipped_stage("evidence_and_llm_repair", "Escalation model produced a validated direct URL."),
                ]
            )
            return _complete(
                company_key=company_key,
                company_name=company_name,
                stages=stages,
                last_payload=latest,
                baseline=baseline,
                trace=trace,
                ledger=ledger,
                primary_observation=primary_payload,
                escalation_observation=escalation_payload,
            )

    # Tavily is a residual search stage only after both direct-model stages miss or
    # are explicitly disabled. Query hypotheses were already anti-repeat filtered
    # by the shared ledger when the model responses were validated.
    if args.disable_tavily:
        stages.extend(
            [
                blocked_stage(
                    "tavily_repair",
                    "tavily_disabled_diagnostic_override",
                    "Residual Tavily search disabled by explicit runtime policy.",
                ),
                skipped_stage(
                    "evidence_and_llm_repair",
                    "Deep evidence requires a provider-enriched residual candidate set after model-first misses.",
                ),
            ]
        )
        return _complete(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
            last_payload=latest,
            baseline=baseline,
            trace=trace,
            ledger=ledger,
            primary_observation=primary_payload,
            escalation_observation=escalation_payload,
        )

    tavily_key = str(os.getenv("TAVILY_API_KEY") or "").strip()
    if adaptive._missing_secret(tavily_key):
        stages.extend(
            [
                blocked_stage(
                    "tavily_repair",
                    "missing_tavily_api_key",
                    "Residual Tavily search requires a provider key.",
                ),
                skipped_stage(
                    "evidence_and_llm_repair",
                    "Deep evidence requires provider-enriched residual candidates.",
                ),
            ]
        )
        return _complete(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
            last_payload=latest,
            baseline=baseline,
            trace=trace,
            ledger=ledger,
            primary_observation=primary_payload,
            escalation_observation=escalation_payload,
        )

    max_adaptive_candidates = int(adaptive._value(args, "max_adaptive_candidates", 18))
    initial_limit = int(
        adaptive._value(
            args,
            "initial_search_query_limit",
            min(int(adaptive._value(args, "search_query_limit", 4)), 5),
        )
    )
    residual_query_limit = max(1, int(adaptive._value(args, "search_query_limit", 5)))
    unique_deferred = list(dict.fromkeys(deferred_queries))
    selected_deferred = unique_deferred[:residual_query_limit]
    remaining_slots = max(0, residual_query_limit - len(selected_deferred))
    deterministic_queries = ledger.novel_queries(
        initial_adaptive_queries(
            company_name=company_name,
            company_key=company_key,
            target_location=args.target_location,
            maximum=min(initial_limit, remaining_slots),
        )
    )
    initial_queries: Sequence[str] = tuple(selected_deferred) + tuple(deterministic_queries)
    initial_rows, initial_requests = adaptive._search_rows(
        args,
        company_key=company_key,
        queries=initial_queries,
        ledger=ledger,
        maximum_results=max_adaptive_candidates,
    )
    followup_limit = int(adaptive._value(args, "domain_followup_query_limit", 3))
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
        tavily = dict(latest)
        tavily["decision"] = "not_found"
        tavily["selected_url"] = None
        tavily["reason"] = "Residual Tavily search returned no novel origin URL candidate."
    discovery_payloads.append(tavily)
    tavily_fingerprint, tavily_progressed = ledger.record_state(tavily)
    tavily["adaptive_search_round"] = {
        "deferred_model_queries": list(selected_deferred),
        "deferred_model_queries_dropped_by_budget": list(
            unique_deferred[residual_query_limit:]
        ),
        "deterministic_queries": list(deterministic_queries),
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
        stages.append(
            skipped_stage(
                "evidence_and_llm_repair",
                "Residual Tavily search produced a deterministically validated URL.",
            )
        )
        return _complete(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
            last_payload=tavily,
            baseline=baseline,
            trace=trace,
            ledger=ledger,
            primary_observation=primary_payload,
            escalation_observation=escalation_payload,
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
        primary_observation=primary_payload,
        escalation_observation=escalation_payload,
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
        raise SystemExit("primary search LLM cost ceiling must not be negative")
    escalation_ceiling = float(
        adaptive._value(
            args,
            "max_search_llm_escalation_cost_usd_per_company",
            0.05,
        )
    )
    if escalation_ceiling < 0:
        raise SystemExit("search LLM escalation cost ceiling must not be negative")


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
