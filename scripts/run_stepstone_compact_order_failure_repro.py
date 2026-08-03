"""Run the compact one-shot StepStone directed-order reproduction experiment.

Plan mode performs no network request. Live mode performs exactly eight
page-one requests: A0, A, C, A->B, B->A, C->B, B->C, A1.

Seed B is not fetched alone because a usable reverse pair proves that B can
participate in an interpretable expression in the same observation window. The
experiment is diagnostic-only and cannot activate production behavior.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from scripts.run_stepstone_filter_matrix_probe import (
    RequestBudget,
    fetch_with_budget,
    summarize_probe,
)
from scripts.run_stepstone_order_failure_repro_probe import (
    enforce_execution_gate,
    find_candidate,
    load_latest_baseline_candidates,
)
from src.connectors.stepstone import USER_AGENT
from src.search_intelligence.stepstone_company_discovery_cycle import build_not_query
from src.search_intelligence.stepstone_filter_failure_similarity import (
    rank_candidates_by_hypothesis,
)

DEFAULT_SOURCE = "stepstone"
DEFAULT_PROFILE = "stepstone_data_engineer_hannover"
DEFAULT_SEARCH_TERM = "Machine Learning Engineer"
DEFAULT_LOCATION = "Hannover"
DEFAULT_SEED_A = "Technische Informationsbibliothek (TIB)"
DEFAULT_SEED_B = "HDI"
LOCKED_ANALOG = "CompuGroup Medical SE & Co. KGaA"
LOCKED_HYPOTHESIS = "syntax_encoding_shape"
DEFAULT_COOLDOWN_HOURS = 24
DEFAULT_DELAY_SECONDS = 2.0
DEFAULT_MAX_REQUESTS = 8
USABLE_OUTCOMES = {
    "filter_effective_full_refill",
    "filter_effective_partial_refill",
}


def build_compact_request_plan(
    *,
    search_term: str,
    seed_a: dict[str, Any],
    seed_b: dict[str, Any],
    analog: dict[str, Any],
) -> list[dict[str, Any]]:
    a = str(seed_a["filter_alias"])
    b = str(seed_b["filter_alias"])
    c = str(analog["filter_alias"])
    definitions = [
        ("a0_baseline", []),
        ("single_a", [a]),
        ("single_c", [c]),
        ("seed_a_then_b", [a, b]),
        ("seed_b_then_a", [b, a]),
        ("analog_c_then_b", [c, b]),
        ("analog_b_then_c", [b, c]),
        ("a1_baseline_control", []),
    ]
    return [
        {
            "label": label,
            "aliases": aliases,
            "query": build_not_query(search_term, aliases),
        }
        for label, aliases in definitions
    ]


def classify_compact_directed_pair(
    *,
    single_left: dict[str, Any],
    forward: dict[str, Any],
    reverse: dict[str, Any],
) -> dict[str, Any]:
    values = (single_left, forward, reverse)
    if any(item["outcome"] == "indeterminate_page_type" for item in values):
        result = "indeterminate_page_type"
    elif single_left["outcome"] not in USABLE_OUTCOMES:
        result = "individual_left_alias_precondition_failed"
    elif forward["outcome"] not in USABLE_OUTCOMES and reverse["outcome"] in USABLE_OUTCOMES:
        result = "directed_forward_failure_reproduced"
    elif forward["outcome"] in USABLE_OUTCOMES and reverse["outcome"] not in USABLE_OUTCOMES:
        result = "directed_reverse_failure_observed"
    elif forward["outcome"] in USABLE_OUTCOMES and reverse["outcome"] in USABLE_OUTCOMES:
        result = "both_orders_usable"
    else:
        result = "both_orders_failed"
    return {
        "result": result,
        "directed_forward_failure_reproduced": (
            result == "directed_forward_failure_reproduced"
        ),
        "single_left_cards": single_left["parsed_card_count"],
        "forward_cards": forward["parsed_card_count"],
        "reverse_cards": reverse["parsed_card_count"],
        "forward_leakage": forward["leakage_count"],
        "reverse_leakage": reverse["leakage_count"],
        "right_alias_individual_probe_omitted": True,
        "right_alias_interpretable_via_reverse_pair": (
            reverse["outcome"] in USABLE_OUTCOMES
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-name", default=DEFAULT_SOURCE)
    parser.add_argument("--search-profile-name", default=DEFAULT_PROFILE)
    parser.add_argument("--search-term", default=DEFAULT_SEARCH_TERM)
    parser.add_argument("--location", default=DEFAULT_LOCATION)
    parser.add_argument("--review-id", type=int)
    parser.add_argument("--cooldown-hours", type=int, default=DEFAULT_COOLDOWN_HOURS)
    parser.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument("--max-requests", type=int, default=DEFAULT_MAX_REQUESTS)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    return parser


def _load_experiment(args: argparse.Namespace) -> dict[str, Any]:
    baseline = load_latest_baseline_candidates(
        source_name=args.source_name,
        search_profile_name=args.search_profile_name,
        search_term=args.search_term,
        review_id=args.review_id,
    )
    candidates = list(baseline["candidates"])
    seed_a = find_candidate(candidates, DEFAULT_SEED_A, label="Seed A")
    seed_b = find_candidate(candidates, DEFAULT_SEED_B, label="Seed B")
    analog = find_candidate(candidates, LOCKED_ANALOG, label="Locked analog")
    seed_keys = {str(seed_a["company_key"]), str(seed_b["company_key"])}
    if str(analog["company_key"]) in seed_keys:
        raise RuntimeError("Locked analog must differ from both seed aliases")

    rankings = rank_candidates_by_hypothesis(
        seed_alias=str(seed_a["filter_alias"]),
        candidates=candidates,
        excluded_company_keys=tuple(seed_keys),
    )
    locked_ranking = rankings[LOCKED_HYPOTHESIS]
    analog_rank = next(
        (
            index
            for index, item in enumerate(locked_ranking, start=1)
            if str(item["company_key"]) == str(analog["company_key"])
        ),
        None,
    )
    if analog_rank is None:
        raise RuntimeError("Locked analog is missing from the locked hypothesis ranking")
    analog_evidence = locked_ranking[analog_rank - 1]
    return {
        "baseline": baseline,
        "seed_a": seed_a,
        "seed_b": seed_b,
        "analog": analog,
        "analog_rank": analog_rank,
        "analog_evidence": analog_evidence,
    }


def main() -> None:
    args = build_parser().parse_args()
    if args.cooldown_hours < 1:
        raise SystemExit("--cooldown-hours must be at least 1")
    if args.delay_seconds < 0:
        raise SystemExit("--delay-seconds must be non-negative")
    if args.max_requests != DEFAULT_MAX_REQUESTS:
        raise SystemExit(
            f"--max-requests must equal {DEFAULT_MAX_REQUESTS} for this fixed experiment"
        )

    experiment = _load_experiment(args)
    baseline = experiment["baseline"]
    seed_a = experiment["seed_a"]
    seed_b = experiment["seed_b"]
    analog = experiment["analog"]
    analog_evidence = experiment["analog_evidence"]
    analog_rank = int(experiment["analog_rank"])

    gate = enforce_execution_gate(
        execute=args.execute,
        approval_token=args.approval_token,
        baseline_observed_at=baseline["baseline_observed_at"],
        cooldown_hours=args.cooldown_hours,
        analog=analog,
        hypothesis=LOCKED_HYPOTHESIS,
    )
    request_plan = build_compact_request_plan(
        search_term=args.search_term,
        seed_a=seed_a,
        seed_b=seed_b,
        analog=analog,
    )
    plan = {
        "schema_version": "pipeline.stepstone.compact_order_failure_repro_plan.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "scope": {
            "source_name": args.source_name,
            "search_profile_name": args.search_profile_name,
            "search_term": args.search_term,
            "location": args.location,
        },
        "baseline": baseline,
        "seed_a": seed_a,
        "seed_b": seed_b,
        "locked_analog": analog,
        "locked_hypothesis": LOCKED_HYPOTHESIS,
        "locked_hypothesis_rank": analog_rank,
        "locked_hypothesis_evidence": analog_evidence,
        "request_plan": request_plan,
        "execution_gate": gate,
        "request_reduction": {
            "previous_matrix_requests": 9,
            "compact_matrix_requests": 8,
            "omitted_probe": "single_b",
            "rationale": (
                "A usable reverse pair proves that seed B participates in an "
                "interpretable expression in the same observation window."
            ),
        },
        "boundaries": {
            "page_one_only": True,
            "fixed_request_count": DEFAULT_MAX_REQUESTS,
            "diagnostic_only": True,
            "production_rule_adoption_allowed": False,
            "database_transaction": "read_only",
            "no_database_write": True,
            "no_pagination": True,
            "no_detail_pages": True,
            "no_candidate_creation": True,
            "no_provider_call": True,
            "no_source_activation": True,
            "no_connector_execution": True,
            "no_scheduler_change": True,
            "no_application_action": True,
        },
    }

    print("StepStone compact directed order-failure reproduction")
    print(f"baseline_review_id: {baseline['review_id']}")
    print(f"baseline_observed_at: {baseline['baseline_observed_at'].isoformat()}")
    print(f"not_before: {gate['not_before'].isoformat()}")
    print(f"execution_allowed_now: {str(gate['execution_allowed_now']).lower()}")
    print(f"seed_pair: {seed_a['filter_alias']} -> {seed_b['filter_alias']}")
    print(f"locked_analog: {analog['filter_alias']}")
    print(f"locked_hypothesis: {LOCKED_HYPOTHESIS}")
    print(
        "locked_hypothesis_score: "
        f"{analog_evidence['similarity_score']} | "
        f"class={analog_evidence['similarity_class']} | rank={analog_rank}"
    )
    print("request_matrix: A0, A, C, A->B, B->A, C->B, B->C, A1")
    if not args.execute:
        print("requests: 0/8")
        print("RESULT: STEPSTONE_COMPACT_ORDER_FAILURE_REPRO_PLAN_COMPLETED")
        return

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = args.artifact_dir / f"stepstone_compact_order_failure_repro_{stamp}"
    artifact_dir.mkdir(parents=True, exist_ok=False)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT.replace(
                "connector",
                "compact-order-failure-reproduction",
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
        }
    )
    budget = RequestBudget(DEFAULT_MAX_REQUESTS)
    pages: dict[str, dict[str, Any]] = {}
    for item in request_plan:
        pages[str(item["label"])] = fetch_with_budget(
            budget=budget,
            session=session,
            label=str(item["label"]),
            query=str(item["query"]),
            location=args.location,
            artifact_dir=artifact_dir,
            delay_seconds=args.delay_seconds,
        )

    a0 = pages["a0_baseline"]
    candidate_by_alias = {
        str(seed_a["filter_alias"]): seed_a,
        str(seed_b["filter_alias"]): seed_b,
        str(analog["filter_alias"]): analog,
    }
    summaries: dict[str, dict[str, Any]] = {}
    for item in request_plan[1:-1]:
        selected = [candidate_by_alias[str(alias)] for alias in item["aliases"]]
        summaries[str(item["label"])] = summarize_probe(
            page=pages[str(item["label"])],
            candidates=selected,
            baseline=a0,
        )

    seed_diagnosis = classify_compact_directed_pair(
        single_left=summaries["single_a"],
        forward=summaries["seed_a_then_b"],
        reverse=summaries["seed_b_then_a"],
    )
    analog_diagnosis = classify_compact_directed_pair(
        single_left=summaries["single_c"],
        forward=summaries["analog_c_then_b"],
        reverse=summaries["analog_b_then_c"],
    )
    if seed_diagnosis["directed_forward_failure_reproduced"]:
        conclusion = (
            "syntax_encoding_analog_reproduced_directed_failure"
            if analog_diagnosis["directed_forward_failure_reproduced"]
            else "seed_reproduced_but_syntax_encoding_analog_did_not"
        )
    else:
        conclusion = "seed_not_reproduced_in_current_observation_window"

    payload = {
        **plan,
        "schema_version": "pipeline.stepstone.compact_order_failure_repro_probe.v1",
        "artifact_dir": str(artifact_dir),
        "request_count": budget.used,
        "pages": pages,
        "summaries": summaries,
        "diagnosis": {
            "seed_pair": seed_diagnosis,
            "analog_pair": analog_diagnosis,
            "conclusion": conclusion,
            "rule_or_workaround_adoption_allowed": False,
        },
        "baseline_control": {
            "a0_cards": pages["a0_baseline"]["parsed_card_count"],
            "a1_cards": pages["a1_baseline_control"]["parsed_card_count"],
            "a0_a1_job_overlap_count": len(
                {str(card["job_key"]) for card in pages["a0_baseline"]["cards"]}
                & {
                    str(card["job_key"])
                    for card in pages["a1_baseline_control"]["cards"]
                }
            ),
        },
    }
    result_path = artifact_dir / "result.json"
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    print(f"artifact: {result_path}")
    print(f"requests: {budget.used}/{budget.maximum}")
    print(f"seed_result: {seed_diagnosis['result']}")
    print(f"analog_result: {analog_diagnosis['result']}")
    print(f"conclusion: {conclusion}")
    print("rule_or_workaround_adoption_allowed: false")
    print("RESULT: STEPSTONE_COMPACT_ORDER_FAILURE_REPRO_PROBE_COMPLETED")


if __name__ == "__main__":
    main()
