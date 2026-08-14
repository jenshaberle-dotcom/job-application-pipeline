"""Run the LLM-BOOST-001 canonical search-first origin recovery cascade.

The stable product order is:

1. deterministic baseline;
2. deterministic symbol/brand and operator URL hypotheses;
3. Tavily when current sanitized runtime telemetry proves the next requests are
   fundable and the provider/key are available;
4. GPT-5.6 Luna medium;
5. GPT-5.6 Terra medium;
6. GPT-5.6 Sol medium;
7. GPT-5.6 Luna max;
8. bounded deep evidence / adjudication.

Every provider/model result remains an untrusted hypothesis until the existing
deterministic origin validators accept it. One SearchProgressLedger spans the
whole case. No product write or source activation occurs here.
"""

from __future__ import annotations

import argparse
from copy import copy
import os
from typing import Mapping, Sequence

from scripts import run_origin_url_empirical_cascade as empirical
from scripts.run_origin_source_discovery_agent import load_local_env_file
from src.search_intelligence.llm_booster_policy import BOOSTER_CONTRACT_VERSION
from src.search_intelligence.origin_search_first_controller import (
    OriginSearchFirstPlan,
    build_origin_search_first_plan,
)

RESULT = empirical.RESULT
write_report = empirical.write_report
PRIMARY_STAGE = empirical.PRIMARY_STAGE
TERRA_STAGE = empirical.TERRA_STAGE
SOL_STAGE = empirical.SOL_STAGE
MAX_STAGE = empirical.MAX_STAGE
MODEL_STAGE_NAMES = empirical.MODEL_STAGE_NAMES


def build_parser() -> argparse.ArgumentParser:
    parser = empirical.build_parser()
    parser.add_argument(
        "--tavily-remaining-credits",
        type=int,
        default=None,
        help=(
            "Sanitized current non-PAYG Tavily credits supplied by the runtime "
            "provider boundary. Unknown telemetry skips Tavily and continues "
            "to Luna."
        ),
    )
    parser.add_argument(
        "--tavily-provider-unavailable",
        action="store_true",
        help="Mark current Tavily provider health unavailable without blocking LLMs.",
    )
    return parser


def _value(args: argparse.Namespace, name: str, default: object) -> object:
    return empirical._value(args, name, default)


def _complete(
    *,
    company_key: str,
    company_name: str,
    stages: list[empirical.RepairStage],
    last_payload: Mapping[str, object],
    baseline: Mapping[str, object],
    trace: Mapping[str, object],
    ledger: empirical.SearchProgressLedger,
    observations: Mapping[str, Mapping[str, object] | None],
    evidence_review: Mapping[str, object] | None = None,
    late_llm_observation: Mapping[str, object] | None = None,
) -> dict[str, object]:
    payload = empirical._complete(
        company_key=company_key,
        company_name=company_name,
        stages=stages,
        last_payload=last_payload,
        baseline=baseline,
        trace=trace,
        ledger=ledger,
        observations=observations,
        evidence_review=evidence_review,
        late_llm_observation=late_llm_observation,
    )
    legacy = payload.get("empirical_origin_cascade")
    if isinstance(legacy, dict):
        legacy["canonical"] = False
        legacy["superseded_by"] = BOOSTER_CONTRACT_VERSION
    payload["search_first_origin_cascade"] = {
        "canonical": True,
        "contract_version": BOOSTER_CONTRACT_VERSION,
        "provider_order": [
            "tavily_search",
            "luna_medium_direct_llm",
            "terra_medium_direct_llm",
            "sol_medium_direct_llm",
            "luna_max_direct_llm",
            "deep_evidence",
        ],
        "model_stage_order": list(MODEL_STAGE_NAMES),
        "pro_mode_enabled": False,
        "product_authority": False,
    }
    return payload


def _finish_selected(
    *,
    company_key: str,
    company_name: str,
    stages: list[empirical.RepairStage],
    remaining_model_stages: Sequence[str],
    tavily_recorded: bool,
    last_payload: Mapping[str, object],
    baseline: Mapping[str, object],
    trace: Mapping[str, object],
    ledger: empirical.SearchProgressLedger,
    observations: Mapping[str, Mapping[str, object] | None],
    reason: str,
) -> dict[str, object]:
    if not tavily_recorded:
        stages.append(empirical.skipped_stage("tavily_repair", reason))
    stages.extend(empirical.skipped_stage(name, reason) for name in remaining_model_stages)
    stages.append(empirical.skipped_stage("evidence_and_llm_repair", reason))
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


def _search_plan(args: argparse.Namespace) -> OriginSearchFirstPlan:
    tavily_key = str(os.getenv("TAVILY_API_KEY") or "").strip()
    initial_limit = int(
        _value(
            args,
            "initial_search_query_limit",
            min(int(_value(args, "search_query_limit", 5)), 5),
        )
    )
    followup_limit = int(_value(args, "domain_followup_query_limit", 3))
    remaining_raw = _value(args, "tavily_remaining_credits", None)
    remaining = None if remaining_raw is None else int(remaining_raw)
    return build_origin_search_first_plan(
        search_depth=str(_value(args, "search_depth", "advanced")),
        remaining_credits=remaining,
        explicitly_disabled=bool(_value(args, "disable_tavily", False)),
        key_available=not empirical.adaptive._missing_secret(tavily_key),
        provider_available=not bool(
            _value(args, "tavily_provider_unavailable", False)
        ),
        initial_query_limit=initial_limit,
        followup_query_limit=followup_limit,
    )


def _run_tavily_stage(
    args: argparse.Namespace,
    *,
    company_key: str,
    company_name: str,
    latest: Mapping[str, object],
    ledger: empirical.SearchProgressLedger,
    plan: OriginSearchFirstPlan,
) -> tuple[empirical.RepairStage, Mapping[str, object], dict[str, object]]:
    max_candidates = int(_value(args, "max_adaptive_candidates", 18))
    configured_initial = int(
        _value(
            args,
            "initial_search_query_limit",
            min(int(_value(args, "search_query_limit", 5)), 5),
        )
    )
    initial_limit = min(configured_initial, plan.remaining_request_slots(0))
    initial_queries = ledger.novel_queries(
        empirical.initial_adaptive_queries(
            company_name=company_name,
            company_key=company_key,
            target_location=str(_value(args, "target_location", "Hannover")),
            maximum=initial_limit,
        )
    )
    initial_rows, initial_requests = empirical.adaptive._search_rows(
        args,
        company_key=company_key,
        queries=initial_queries,
        ledger=ledger,
        maximum_results=max_candidates,
    )

    slots = plan.remaining_request_slots(initial_requests)
    configured_followup = int(_value(args, "domain_followup_query_limit", 3))
    followup_limit = min(configured_followup, slots)
    followup_queries = ledger.novel_queries(
        empirical.domain_followup_queries(
            empirical.adaptive._domains_from_rows(initial_rows),
            maximum=followup_limit,
        )
    )
    followup_rows, followup_requests = empirical.adaptive._search_rows(
        args,
        company_key=company_key,
        queries=followup_queries,
        ledger=ledger,
        maximum_results=max(0, max_candidates - len(initial_rows)),
    )
    rows = empirical.adaptive._dedupe_rows(
        [*initial_rows, *followup_rows],
        maximum=max_candidates,
    )
    if rows:
        discovery = empirical.adaptive._run_atomic_with_rows(
            args,
            company_key=company_key,
            rows=rows,
        )
    else:
        discovery = dict(latest)
        discovery["decision"] = "not_found"
        discovery["selected_url"] = None
        discovery["reason"] = "Search-first Tavily returned no novel origin candidate."

    request_count = initial_requests + followup_requests
    fingerprint, progressed = ledger.record_state(discovery)
    round_trace = {
        "budget": plan.to_json(),
        "initial_queries": list(initial_queries),
        "domain_followup_queries": list(followup_queries),
        "provider_requests": request_count,
        "credit_cost_per_request": plan.tavily_budget.next_request_credits,
        "credits_consumed": request_count * plan.tavily_budget.next_request_credits,
        "candidate_rows": len(rows),
        "state_fingerprint": fingerprint,
        "state_progressed": progressed,
        "same_query_retry": False,
    }
    discovery["search_first_tavily_round"] = round_trace
    stage = empirical.stage_from_discovery(
        "tavily_repair",
        discovery,
        provider_request_count=request_count,
    )
    return stage, discovery, round_trace


def _model_stage(
    args: argparse.Namespace,
    *,
    company_key: str,
    company_name: str,
    baseline: Mapping[str, object],
    latest: Mapping[str, object],
    ledger: empirical.SearchProgressLedger,
    spec: Mapping[str, object],
):  # type: ignore[no-untyped-def]
    stage_args = copy(args)
    return empirical._model_stage(
        stage_args,
        company_key=company_key,
        company_name=company_name,
        baseline=baseline,
        latest=latest,
        ledger=ledger,
        stage_name=str(spec["stage"]),
        model=str(spec["model"]),
        reasoning_effort=str(spec["reasoning"]),
        max_output_tokens=int(spec["max_output_tokens"]),
        timeout_seconds=float(spec["timeout"]),
        cost_ceiling=float(spec["ceiling"]),
        provider_label=str(spec["provider"]),
    )


def run_default_repair_for_company(
    args: argparse.Namespace,
    company_key: str,
) -> dict[str, object]:
    stages: list[empirical.RepairStage] = []
    ledger = empirical.SearchProgressLedger()
    discovery_payloads: list[Mapping[str, object]] = []
    observations: dict[str, Mapping[str, object] | None] = {}
    specs = empirical._model_specs(args)
    trace: dict[str, object] = {
        "finite_state_machine": True,
        "identical_retry_forbidden": True,
        "deterministic_before_provider": True,
        "provider_order": [
            "tavily_search",
            "luna_medium_direct_llm",
            "terra_medium_direct_llm",
            "sol_medium_direct_llm",
            "luna_max_direct_llm",
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

    baseline = empirical.adaptive.run_atomic_origin_discovery(
        empirical.adaptive._origin_args(args, providers=["none"]),
        company_key,
    )
    discovery_payloads.append(baseline)
    baseline_fingerprint, _ = ledger.record_state(baseline)
    trace["baseline_fingerprint"] = baseline_fingerprint
    stages.append(empirical.stage_from_discovery("deterministic_baseline", baseline))
    company_name = str(baseline.get("company_name") or company_key)

    if empirical.selected_url(baseline):
        stages.append(
            empirical.skipped_stage(
                "deterministic_symbol_brand",
                "Baseline selected a validated URL.",
            )
        )
        return _finish_selected(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
            remaining_model_stages=MODEL_STAGE_NAMES,
            tavily_recorded=False,
            last_payload=baseline,
            baseline=baseline,
            trace=trace,
            ledger=ledger,
            observations=observations,
            reason="Baseline selected a validated URL.",
        )

    deterministic_limit = int(_value(args, "max_brand_host_hypotheses", 6))
    direct_urls = ledger.novel_urls(
        empirical.deterministic_brand_url_hypotheses(
            company_name=company_name,
            company_key=company_key,
            maximum=deterministic_limit,
        )
    )
    operator_urls = ledger.novel_urls(
        str(item) for item in (_value(args, "operator_url", []) or [])
    )
    direct_rows = empirical.adaptive._hypothesis_rows(
        company_key=company_key,
        urls=direct_urls,
        provider="deterministic_symbol_brand",
        rationale="symbol-aware high-value career host hypothesis",
    )
    direct_rows.extend(
        empirical.adaptive._hypothesis_rows(
            company_key=company_key,
            urls=operator_urls,
            provider="operator_supplied_unvalidated",
            rationale="operator hint; still requires deterministic validation",
        )
    )
    if direct_rows:
        deterministic = empirical.adaptive._run_atomic_with_rows(
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
    stages.append(
        empirical.stage_from_discovery("deterministic_symbol_brand", deterministic)
    )
    trace["deterministic_symbol_brand_round"] = deterministic[
        "deterministic_symbol_brand_round"
    ]

    if empirical.selected_url(deterministic):
        return _finish_selected(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
            remaining_model_stages=MODEL_STAGE_NAMES,
            tavily_recorded=False,
            last_payload=deterministic,
            baseline=baseline,
            trace=trace,
            ledger=ledger,
            observations=observations,
            reason="Deterministic validation selected a URL.",
        )

    latest: Mapping[str, object] = deterministic
    plan = _search_plan(args)
    trace["search_first_plan"] = plan.to_json()
    if plan.tavily_search_allowed:
        tavily_stage, tavily, tavily_trace = _run_tavily_stage(
            args,
            company_key=company_key,
            company_name=company_name,
            latest=latest,
            ledger=ledger,
            plan=plan,
        )
        stages.append(tavily_stage)
        discovery_payloads.append(tavily)
        trace["search_first_tavily_round"] = tavily_trace
        latest = tavily
        if empirical.selected_url(tavily):
            return _finish_selected(
                company_key=company_key,
                company_name=company_name,
                stages=stages,
                remaining_model_stages=MODEL_STAGE_NAMES,
                tavily_recorded=True,
                last_payload=tavily,
                baseline=baseline,
                trace=trace,
                ledger=ledger,
                observations=observations,
                reason="Tavily produced a deterministically validated URL.",
            )
    else:
        stages.append(empirical.skipped_stage("tavily_repair", plan.tavily_budget.reason))

    if bool(_value(args, "disable_llm", False)):
        stages.extend(
            empirical.skipped_stage(
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
                spec=spec,
            )
            stages.append(stage)
            observations[stage_name] = observation
            trace[f"{stage_name}_deferred_queries_unexecuted"] = list(queries)
            if discovery is not latest:
                discovery_payloads.append(discovery)
            latest = discovery
            if empirical.selected_url(latest):
                remaining = [str(item["stage"]) for item in specs[index + 1 :]]
                return _finish_selected(
                    company_key=company_key,
                    company_name=company_name,
                    stages=stages,
                    remaining_model_stages=remaining,
                    tavily_recorded=True,
                    last_payload=latest,
                    baseline=baseline,
                    trace=trace,
                    ledger=ledger,
                    observations=observations,
                    reason=(
                        f"{spec['model']} produced a deterministically validated "
                        "direct URL."
                    ),
                )

    merged = empirical.adaptive._merge_payloads(discovery_payloads)
    evidence_payload, late_observation, recommended_url, evidence_blocker = (
        empirical.adaptive._deep_evidence_and_late_llm_repair(
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
        empirical.evidence_stage(
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


run_empirical_repair_for_company = run_default_repair_for_company


def _validate_args(args: argparse.Namespace) -> None:
    empirical._validate_args(args)
    remaining = _value(args, "tavily_remaining_credits", None)
    if remaining is not None and int(remaining) < 0:
        raise SystemExit("--tavily-remaining-credits must not be negative")


def run(args: argparse.Namespace) -> int:
    _validate_args(args)
    payloads = [run_default_repair_for_company(args, key) for key in args.company_key]
    for payload in payloads:
        repair = payload.get("default_repair")
        repair_map = repair if isinstance(repair, Mapping) else {}
        print(
            "origin_url_search_first_repair: "
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
