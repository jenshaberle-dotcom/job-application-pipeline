"""Run the empirically validated canonical origin-URL recovery cascade.

Runtime evidence in job-pipeline-runtime#77 established a bounded production order
for the current portfolio:

1. deterministic baseline;
2. deterministic symbol/brand and operator URL hypotheses;
3. GPT-5.6 Luna with medium reasoning;
4. GPT-5.6 Terra with medium reasoning;
5. GPT-5.6 Sol with medium reasoning;
6. GPT-5.6 Luna with max reasoning;
7. residual Tavily only when explicitly enabled and operational;
8. deep evidence and optional late adjudication.

All model URLs remain untrusted hypotheses.  The unchanged deterministic
origin-discovery HTTP/company-identity/career-origin gates are the only authority
that may select them.  One SearchProgressLedger spans the full cascade so a model
or search provider cannot repeat an already-considered URL/query or turn an
unchanged state into an unbounded retry loop.

Pro mode is deliberately absent: the accepted residual evaluation rescued 0/3
post-max cases while materially increasing cost and latency.
"""

from __future__ import annotations

import argparse
from copy import copy
import os
from typing import Mapping, Sequence

from scripts import run_origin_url_adaptive_repair as adaptive
from scripts import run_origin_url_model_first_repair as model_first
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
    evidence_stage,
    selected_url,
    skipped_stage,
    stage_from_discovery,
)

RESULT = adaptive.RESULT
write_report = adaptive.write_report

PRIMARY_STAGE = "llm_search_hypothesis_repair"
TERRA_STAGE = "llm_search_hypothesis_escalation_repair"
SOL_STAGE = "llm_search_hypothesis_sol_repair"
MAX_STAGE = "llm_search_hypothesis_max_repair"
MODEL_STAGE_NAMES = (PRIMARY_STAGE, TERRA_STAGE, SOL_STAGE, MAX_STAGE)


def build_parser() -> argparse.ArgumentParser:
    parser = model_first.build_parser()
    parser.set_defaults(
        search_llm_model=os.getenv("ORIGIN_SEARCH_HYPOTHESIS_MODEL", "gpt-5.6-luna"),
        search_llm_escalation_model=os.getenv(
            "ORIGIN_SEARCH_HYPOTHESIS_TERRA_MODEL", "gpt-5.6-terra"
        ),
        search_llm_reasoning_effort="medium",
        search_llm_max_output_tokens=500,
        search_llm_timeout_seconds=90.0,
        max_search_llm_cost_usd_per_company=0.01,
        max_search_llm_escalation_cost_usd_per_company=0.02,
    )
    parser.add_argument(
        "--search-llm-sol-model",
        default=os.getenv("ORIGIN_SEARCH_HYPOTHESIS_SOL_MODEL", "gpt-5.6-sol"),
    )
    parser.add_argument(
        "--max-search-llm-sol-cost-usd-per-company",
        type=float,
        default=0.05,
    )
    parser.add_argument(
        "--search-llm-max-model",
        default=os.getenv("ORIGIN_SEARCH_HYPOTHESIS_MAX_MODEL", "gpt-5.6-luna"),
    )
    parser.add_argument(
        "--search-llm-max-reasoning-effort",
        default="max",
    )
    parser.add_argument(
        "--search-llm-max-output-tokens",
        type=int,
        default=6000,
    )
    parser.add_argument(
        "--search-llm-max-timeout-seconds",
        type=float,
        default=180.0,
    )
    parser.add_argument(
        "--max-search-llm-max-cost-usd-per-company",
        type=float,
        default=0.05,
    )
    return parser


def _value(args: argparse.Namespace, name: str, default: object) -> object:
    return adaptive._value(args, name, default)


def _complete(
    *,
    company_key: str,
    company_name: str,
    stages: list[RepairStage],
    last_payload: Mapping[str, object],
    baseline: Mapping[str, object],
    trace: Mapping[str, object],
    ledger: SearchProgressLedger,
    observations: Mapping[str, Mapping[str, object] | None],
    evidence_review: Mapping[str, object] | None = None,
    late_llm_observation: Mapping[str, object] | None = None,
) -> dict[str, object]:
    payload = model_first._complete(
        company_key=company_key,
        company_name=company_name,
        stages=stages,
        last_payload=last_payload,
        baseline=baseline,
        trace=trace,
        ledger=ledger,
        primary_observation=observations.get(PRIMARY_STAGE),
        escalation_observation=observations.get(TERRA_STAGE),
        evidence_review=evidence_review,
        late_llm_observation=late_llm_observation,
    )
    if observations.get(SOL_STAGE) is not None:
        payload["search_llm_sol_observation"] = dict(observations[SOL_STAGE] or {})
    if observations.get(MAX_STAGE) is not None:
        payload["search_llm_max_observation"] = dict(observations[MAX_STAGE] or {})
    payload["empirical_origin_cascade"] = {
        "canonical": True,
        "pro_mode_enabled": False,
        "model_stage_order": list(MODEL_STAGE_NAMES),
        "model_config": {
            PRIMARY_STAGE: {
                "model": str(_value(args_for_payload := _PayloadArgs(payload), "primary_model", "gpt-5.6-luna")),
                "reasoning_effort": "medium",
            }
        } if False else trace.get("model_stage_config", {}),
    }
    return payload


class _PayloadArgs:
    """Never instantiated; keeps static analyzers from treating payload as argparse."""

    def __init__(self, _payload: Mapping[str, object]) -> None:
        self.primary_model = ""


def _finish_selected(
    *,
    company_key: str,
    company_name: str,
    stages: list[RepairStage],
    remaining_model_stages: Sequence[str],
    last_payload: Mapping[str, object],
    baseline: Mapping[str, object],
    trace: Mapping[str, object],
    ledger: SearchProgressLedger,
    observations: Mapping[str, Mapping[str, object] | None],
    reason: str,
) -> dict[str, object]:
    stages.extend(skipped_stage(name, reason) for name in remaining_model_stages)
    stages.extend(
        [
            skipped_stage("tavily_repair", reason),
            skipped_stage("evidence_and_llm_repair", reason),
        ]
    )
    return _complete(
        company_key=company_key,
        company_name=company_name,
        stages=stages,
        last_payload=last_payload,
        baseline=baseline,
        trace=trace,
        ledger=ledger,
        observations=observations,
    )


def _model_stage(
    args: argparse.Namespace,
    *,
    company_key: str,
    company_name: str,
    baseline: Mapping[str, object],
    latest: Mapping[str, object],
    ledger: SearchProgressLedger,
    stage_name: str,
    model: str,
    reasoning_effort: str,
    max_output_tokens: int,
    timeout_seconds: float,
    cost_ceiling: float,
    provider_label: str,
) -> tuple[
    RepairStage,
    Mapping[str, object],
    dict[str, object] | None,
    tuple[str, ...],
]:
    stage_args = copy(args)
    stage_args.search_llm_reasoning_effort = reasoning_effort
    stage_args.search_llm_max_output_tokens = max_output_tokens
    stage_args.search_llm_timeout_seconds = timeout_seconds
    return model_first._run_direct_model_stage(
        stage_args,
        company_key=company_key,
        company_name=company_name,
        baseline=baseline,
        latest=latest,
        ledger=ledger,
        stage_name=stage_name,
        model=model,
        cost_ceiling=cost_ceiling,
        provider_label=provider_label,
    )


def _model_specs(args: argparse.Namespace) -> tuple[dict[str, object], ...]:
    medium_effort = str(_value(args, "search_llm_reasoning_effort", "medium") or "medium")
    medium_output = int(_value(args, "search_llm_max_output_tokens", 500))
    medium_timeout = float(_value(args, "search_llm_timeout_seconds", 90.0))
    return (
        {
            "stage": PRIMARY_STAGE,
            "model": str(_value(args, "search_llm_model", "gpt-5.6-luna")),
            "reasoning": medium_effort,
            "max_output_tokens": medium_output,
            "timeout": medium_timeout,
            "ceiling": float(_value(args, "max_search_llm_cost_usd_per_company", 0.01)),
            "provider": "llm_primary_direct_url_hypothesis",
        },
        {
            "stage": TERRA_STAGE,
            "model": str(_value(args, "search_llm_escalation_model", "gpt-5.6-terra")),
            "reasoning": medium_effort,
            "max_output_tokens": medium_output,
            "timeout": medium_timeout,
            "ceiling": float(
                _value(args, "max_search_llm_escalation_cost_usd_per_company", 0.02)
            ),
            "provider": "llm_terra_direct_url_hypothesis",
        },
        {
            "stage": SOL_STAGE,
            "model": str(_value(args, "search_llm_sol_model", "gpt-5.6-sol")),
            "reasoning": medium_effort,
            "max_output_tokens": medium_output,
            "timeout": medium_timeout,
            "ceiling": float(_value(args, "max_search_llm_sol_cost_usd_per_company", 0.05)),
            "provider": "llm_sol_direct_url_hypothesis",
        },
        {
            "stage": MAX_STAGE,
            "model": str(_value(args, "search_llm_max_model", "gpt-5.6-luna")),
            "reasoning": str(_value(args, "search_llm_max_reasoning_effort", "max") or "max"),
            "max_output_tokens": int(_value(args, "search_llm_max_output_tokens", 6000)),
            "timeout": float(_value(args, "search_llm_max_timeout_seconds", 180.0)),
            "ceiling": float(_value(args, "max_search_llm_max_cost_usd_per_company", 0.05)),
            "provider": "llm_max_direct_url_hypothesis",
        },
    )


def run_default_repair_for_company(
    args: argparse.Namespace,
    company_key: str,
) -> dict[str, object]:
    stages: list[RepairStage] = []
    ledger = SearchProgressLedger()
    discovery_payloads: list[Mapping[str, object]] = []
    observations: dict[str, Mapping[str, object] | None] = {}
    deferred_queries: list[str] = []
    specs = _model_specs(args)
    trace: dict[str, object] = {
        "finite_state_machine": True,
        "identical_retry_forbidden": True,
        "deterministic_before_provider": True,
        "provider_order": [
            "luna_medium_direct_llm",
            "terra_medium_direct_llm",
            "sol_medium_direct_llm",
            "luna_max_direct_llm",
            "tavily_residual_search",
            "deep_evidence",
        ],
        "model_stage_config": {
            str(spec["stage"]): {
                "model": spec["model"],
                "reasoning_effort": spec["reasoning"],
                "max_output_tokens": spec["max_output_tokens"],
                "cost_ceiling_usd": spec["ceiling"],
            }
            for spec in specs
        },
        "late_llm_role": "observed_evidence_adjudication_only",
        "pro_mode_enabled": False,
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
        stages.append(
            skipped_stage(
                "deterministic_symbol_brand",
                "Baseline selected a validated URL.",
            )
        )
        return _finish_selected(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
            remaining_model_stages=MODEL_STAGE_NAMES,
            last_payload=baseline,
            baseline=baseline,
            trace=trace,
            ledger=ledger,
            observations=observations,
            reason="Baseline selected a validated URL.",
        )

    deterministic_limit = int(_value(args, "max_brand_host_hypotheses", 6))
    direct_urls = ledger.novel_urls(
        deterministic_brand_url_hypotheses(
            company_name=company_name,
            company_key=company_key,
            maximum=deterministic_limit,
        )
    )
    operator_urls = ledger.novel_urls(
        str(item) for item in (_value(args, "operator_url", []) or [])
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
        deterministic["decision"] = "not_found"
        deterministic["selected_url"] = None
        deterministic["reason"] = "No novel deterministic brand-host hypothesis."
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
        return _finish_selected(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
            remaining_model_stages=MODEL_STAGE_NAMES,
            last_payload=deterministic,
            baseline=baseline,
            trace=trace,
            ledger=ledger,
            observations=observations,
            reason="Deterministic validation selected a URL.",
        )

    latest: Mapping[str, object] = deterministic
    if bool(_value(args, "disable_llm", False)):
        stages.extend(
            skipped_stage(
                str(spec["stage"]),
                "Model hypotheses disabled by explicit runtime policy.",
            )
            for spec in specs
        )
    else:
        for index, spec in enumerate(specs):
            stage_name = str(spec["stage"])
            stage, discovery, observation, queries = _model_stage(
                args,
                company_key=company_key,
                company_name=company_name,
                baseline=baseline,
                latest=latest,
                ledger=ledger,
                stage_name=stage_name,
                model=str(spec["model"]),
                reasoning_effort=str(spec["reasoning"]),
                max_output_tokens=int(spec["max_output_tokens"]),
                timeout_seconds=float(spec["timeout"]),
                cost_ceiling=float(spec["ceiling"]),
                provider_label=str(spec["provider"]),
            )
            stages.append(stage)
            observations[stage_name] = observation
            deferred_queries.extend(queries)
            trace[f"{stage_name}_deferred_queries"] = list(queries)
            if discovery is not latest:
                discovery_payloads.append(discovery)
            latest = discovery
            if selected_url(latest):
                remaining = [str(item["stage"]) for item in specs[index + 1 :]]
                return _finish_selected(
                    company_key=company_key,
                    company_name=company_name,
                    stages=stages,
                    remaining_model_stages=remaining,
                    last_payload=latest,
                    baseline=baseline,
                    trace=trace,
                    ledger=ledger,
                    observations=observations,
                    reason=f"{spec['model']} produced a deterministically validated direct URL.",
                )

    if bool(_value(args, "disable_tavily", False)):
        stages.extend(
            [
                blocked_stage(
                    "tavily_repair",
                    "tavily_disabled_diagnostic_override",
                    "Residual Tavily search disabled by explicit runtime policy.",
                ),
                skipped_stage(
                    "evidence_and_llm_repair",
                    "Deep evidence requires a provider-enriched residual candidate set after model misses.",
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
            observations=observations,
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
            observations=observations,
        )

    max_adaptive_candidates = int(_value(args, "max_adaptive_candidates", 18))
    initial_limit = int(
        _value(
            args,
            "initial_search_query_limit",
            min(int(_value(args, "search_query_limit", 5)), 5),
        )
    )
    residual_query_limit = max(1, int(_value(args, "search_query_limit", 5)))
    unique_deferred = list(dict.fromkeys(deferred_queries))
    selected_deferred = unique_deferred[:residual_query_limit]
    remaining_slots = max(0, residual_query_limit - len(selected_deferred))
    deterministic_queries = ledger.novel_queries(
        initial_adaptive_queries(
            company_name=company_name,
            company_key=company_key,
            target_location=str(_value(args, "target_location", "Hannover")),
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
    followup_limit = int(_value(args, "domain_followup_query_limit", 3))
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
            observations=observations,
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
        observations=observations,
        evidence_review=evidence_payload,
        late_llm_observation=late_observation,
    )


def _validate_args(args: argparse.Namespace) -> None:
    model_first._validate_args(args)
    for name in (
        "max_search_llm_sol_cost_usd_per_company",
        "max_search_llm_max_cost_usd_per_company",
    ):
        if float(_value(args, name, 0.0)) < 0:
            raise SystemExit(f"{name.replace('_', '-')} must not be negative")
    if int(_value(args, "search_llm_max_output_tokens", 6000)) < 1:
        raise SystemExit("--search-llm-max-output-tokens must be positive")
    if float(_value(args, "search_llm_max_timeout_seconds", 180.0)) <= 0:
        raise SystemExit("--search-llm-max-timeout-seconds must be positive")


def run(args: argparse.Namespace) -> int:
    _validate_args(args)
    payloads = [run_default_repair_for_company(args, key) for key in args.company_key]
    for payload in payloads:
        repair = payload.get("default_repair")
        repair_map = repair if isinstance(repair, Mapping) else {}
        print(
            "origin_url_empirical_cascade: "
            f"company_key={payload.get('company_key')} "
            f"final_state={repair_map.get('final_state')} "
            f"selected_url={repair_map.get('selected_url') or '<none>'} "
            f"selected_stage={repair_map.get('selected_stage') or '<none>'}"
        )
        for stage in repair_map.get("stages", []):
            if not isinstance(stage, Mapping):
                continue
            print(
                "  stage: "
                f"name={stage.get('name')} attempted={stage.get('attempted')} "
                f"status={stage.get('status')} decision={stage.get('decision')} "
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
