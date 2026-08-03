"""Reproduce a directed StepStone filter-order failure with an explicit analog.

Plan mode reads the latest production baseline in a read-only transaction and
ranks candidates under separate parser hypotheses. Live mode requires an
operator-selected analog and performs exactly nine page-one requests:
A0, A, B, C, A->B, B->A, C->B, B->C, A1.

Local artifacts only; no PostgreSQL writes, pagination, detail pages, candidate
creation, providers, source activation, scheduler mutation, or applications.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from scripts.activate_stepstone_baseline_runtime import connect
from scripts.run_stepstone_filter_matrix_probe import (
    RequestBudget,
    fetch_with_budget,
    summarize_probe,
)
from src.connectors.stepstone import USER_AGENT
from src.normalization.company_keys import normalize_company_key
from src.search_intelligence.stepstone_company_discovery_cycle import (
    build_not_query,
    company_not_alias,
)
from src.search_intelligence.stepstone_filter_failure_similarity import (
    SUPPORTED_HYPOTHESES,
    directed_pair_signature,
    rank_candidates_by_hypothesis,
)

APPROVAL_TOKEN = "run_stepstone_order_failure_repro_after_cooldown"
DEFAULT_SOURCE = "stepstone"
DEFAULT_PROFILE = "stepstone_data_engineer_hannover"
DEFAULT_SEARCH_TERM = "Machine Learning Engineer"
DEFAULT_LOCATION = "Hannover"
DEFAULT_SEED_A = "Technische Informationsbibliothek (TIB)"
DEFAULT_SEED_B = "HDI"
DEFAULT_COOLDOWN_HOURS = 24
DEFAULT_DELAY_SECONDS = 2.0
DEFAULT_MAX_REQUESTS = 9
USABLE_OUTCOMES = {
    "filter_effective_full_refill",
    "filter_effective_partial_refill",
}


def load_latest_baseline_candidates(
    *,
    source_name: str,
    search_profile_name: str,
    search_term: str,
    review_id: int | None,
) -> dict[str, Any]:
    with connect() as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            with conn.cursor() as cur:
                if review_id is None:
                    cur.execute(
                        """
                        SELECT id, created_at
                        FROM stepstone_company_discovery_cycle_reviews
                        WHERE source_name = %s
                          AND search_profile_name = %s
                          AND search_term = %s
                          AND action = 'run_production_baseline_census'
                        ORDER BY created_at DESC, id DESC
                        LIMIT 1
                        """,
                        (source_name, search_profile_name, search_term),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, created_at
                        FROM stepstone_company_discovery_cycle_reviews
                        WHERE id = %s
                          AND source_name = %s
                          AND search_profile_name = %s
                          AND search_term = %s
                          AND action = 'run_production_baseline_census'
                        """,
                        (review_id, source_name, search_profile_name, search_term),
                    )
                review = cur.fetchone()
                if review is None:
                    raise RuntimeError("No matching production baseline review exists")
                cur.execute(
                    """
                    SELECT company_key, company_name, evidence_count
                    FROM stepstone_company_discovery_cycle_items
                    WHERE review_id = %s
                      AND item_type = 'observed_company'
                    ORDER BY evidence_count DESC, company_key
                    """,
                    (int(review["id"]),),
                )
                rows = cur.fetchall()
                cur.execute(
                    """
                    SELECT id, baseline_observed_at, status, transport_status
                    FROM stepstone_filter_suppression_sets
                    WHERE baseline_review_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """,
                    (int(review["id"]),),
                )
                suppression = cur.fetchone()
    candidates = []
    for row in rows:
        key = str(row["company_key"] or "")
        name = str(row["company_name"] or "")
        candidates.append(
            {
                "company_key": key,
                "company_name": name,
                "filter_alias": company_not_alias(key, name),
                "evidence_count": int(row["evidence_count"] or 0),
            }
        )
    return {
        "review_id": int(review["id"]),
        "review_created_at": review["created_at"],
        "baseline_observed_at": (
            suppression["baseline_observed_at"]
            if suppression is not None
            else review["created_at"]
        ),
        "suppression_set": dict(suppression) if suppression is not None else None,
        "candidates": candidates,
    }


def find_candidate(
    candidates: list[dict[str, Any]],
    value: str,
    *,
    label: str,
) -> dict[str, Any]:
    target_key = normalize_company_key(value)
    target_text = value.casefold().strip()
    for candidate in candidates:
        texts = {
            str(candidate["company_name"]).casefold().strip(),
            str(candidate["filter_alias"]).casefold().strip(),
        }
        keys = {
            str(candidate["company_key"]),
            normalize_company_key(str(candidate["company_name"])),
            normalize_company_key(str(candidate["filter_alias"])),
        }
        if target_text in texts or target_key in keys:
            return candidate
    raise RuntimeError(f"{label} is not present in the selected baseline review: {value}")


def select_analog(
    *,
    candidates: list[dict[str, Any]],
    analog_alias: str | None,
    seed_keys: tuple[str, str],
) -> dict[str, Any] | None:
    if not analog_alias:
        return None
    analog = find_candidate(candidates, analog_alias, label="Analog alias")
    if str(analog["company_key"]) in set(seed_keys):
        raise RuntimeError("Analog alias must differ from seed A and seed B")
    return analog


def selected_hypothesis_evidence(
    *,
    rankings: dict[str, list[dict[str, Any]]],
    hypothesis: str | None,
    analog: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if hypothesis is None or analog is None:
        return None
    for item in rankings[hypothesis]:
        if str(item["company_key"]) == str(analog["company_key"]):
            return item
    raise RuntimeError("Selected analog is missing from hypothesis ranking")


def build_request_plan(
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
        ("single_b", [b]),
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


def enforce_execution_gate(
    *,
    execute: bool,
    approval_token: str | None,
    baseline_observed_at: datetime,
    cooldown_hours: int,
    analog: dict[str, Any] | None,
    hypothesis: str | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    not_before = baseline_observed_at.astimezone(UTC) + timedelta(hours=cooldown_hours)
    reference = (now or datetime.now(UTC)).astimezone(UTC)
    allowed = reference >= not_before
    if execute and analog is None:
        raise SystemExit("Live probe blocked: explicit --analog-alias is required.")
    if execute and hypothesis is None:
        raise SystemExit("Live probe blocked: explicit --analog-hypothesis is required.")
    if execute and approval_token != APPROVAL_TOKEN:
        raise SystemExit("Live probe blocked: exact --approval-token is required.")
    if execute and not allowed:
        raise SystemExit(
            "Live probe blocked by baseline-relative cooldown until "
            f"{not_before.isoformat()} (now={reference.isoformat()})."
        )
    return {
        "execute": execute,
        "now": reference,
        "not_before": not_before,
        "execution_allowed_now": allowed,
        "explicit_analog_required": True,
        "explicit_hypothesis_required": True,
    }


def classify_directed_pair(
    *,
    single_left: dict[str, Any],
    single_right: dict[str, Any],
    forward: dict[str, Any],
    reverse: dict[str, Any],
) -> dict[str, Any]:
    values = (single_left, single_right, forward, reverse)
    if any(item["outcome"] == "indeterminate_page_type" for item in values):
        result = "indeterminate_page_type"
    elif not all(
        item["outcome"] in USABLE_OUTCOMES
        for item in (single_left, single_right)
    ):
        result = "individual_alias_precondition_failed"
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
        "single_right_cards": single_right["parsed_card_count"],
        "forward_cards": forward["parsed_card_count"],
        "reverse_cards": reverse["parsed_card_count"],
        "forward_leakage": forward["leakage_count"],
        "reverse_leakage": reverse["leakage_count"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-name", default=DEFAULT_SOURCE)
    parser.add_argument("--search-profile-name", default=DEFAULT_PROFILE)
    parser.add_argument("--search-term", default=DEFAULT_SEARCH_TERM)
    parser.add_argument("--location", default=DEFAULT_LOCATION)
    parser.add_argument("--review-id", type=int)
    parser.add_argument("--seed-a", default=DEFAULT_SEED_A)
    parser.add_argument("--seed-b", default=DEFAULT_SEED_B)
    parser.add_argument("--analog-alias")
    parser.add_argument("--analog-hypothesis", choices=SUPPORTED_HYPOTHESES)
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


def main() -> None:
    args = build_parser().parse_args()
    if args.cooldown_hours < 1:
        raise SystemExit("--cooldown-hours must be at least 1")
    if args.delay_seconds < 0:
        raise SystemExit("--delay-seconds must be non-negative")
    if args.max_requests != DEFAULT_MAX_REQUESTS:
        raise SystemExit(
            f"--max-requests must equal {DEFAULT_MAX_REQUESTS} for this fixed probe"
        )
    if bool(args.analog_alias) != bool(args.analog_hypothesis):
        raise SystemExit(
            "--analog-alias and --analog-hypothesis must be supplied together."
        )

    baseline = load_latest_baseline_candidates(
        source_name=args.source_name,
        search_profile_name=args.search_profile_name,
        search_term=args.search_term,
        review_id=args.review_id,
    )
    candidates = list(baseline["candidates"])
    seed_a = find_candidate(candidates, args.seed_a, label="Seed A")
    seed_b = find_candidate(candidates, args.seed_b, label="Seed B")
    excluded_keys = (str(seed_a["company_key"]), str(seed_b["company_key"]))
    rankings = rank_candidates_by_hypothesis(
        seed_alias=str(seed_a["filter_alias"]),
        candidates=candidates,
        excluded_company_keys=excluded_keys,
    )
    analog = select_analog(
        candidates=candidates,
        analog_alias=args.analog_alias,
        seed_keys=excluded_keys,
    )
    analog_evidence = selected_hypothesis_evidence(
        rankings=rankings,
        hypothesis=args.analog_hypothesis,
        analog=analog,
    )
    critical_matches = [
        item
        for ranking in rankings.values()
        for item in ranking
        if item["critical_signature"]["all_match"]
    ]
    critical_match_keys = sorted(
        {str(item["company_key"]) for item in critical_matches}
    )
    gate = enforce_execution_gate(
        execute=args.execute,
        approval_token=args.approval_token,
        baseline_observed_at=baseline["baseline_observed_at"],
        cooldown_hours=args.cooldown_hours,
        analog=analog,
        hypothesis=args.analog_hypothesis,
    )
    request_plan = (
        build_request_plan(
            search_term=args.search_term,
            seed_a=seed_a,
            seed_b=seed_b,
            analog=analog,
        )
        if analog is not None
        else []
    )
    plan = {
        "schema_version": "pipeline.stepstone.order_failure_repro_plan.v2",
        "created_at": datetime.now(UTC).isoformat(),
        "scope": {
            "source_name": args.source_name,
            "search_profile_name": args.search_profile_name,
            "search_term": args.search_term,
            "location": args.location,
        },
        "baseline": baseline,
        "seed": {
            "a": seed_a,
            "b": seed_b,
            "a_then_b_signature": directed_pair_signature(
                str(seed_a["filter_alias"]),
                str(seed_b["filter_alias"]),
            ),
            "b_then_a_signature": directed_pair_signature(
                str(seed_b["filter_alias"]),
                str(seed_a["filter_alias"]),
            ),
        },
        "selection_status": (
            "operator_selected" if analog is not None else "operator_decision_required"
        ),
        "selected_analog": analog,
        "selected_hypothesis": args.analog_hypothesis,
        "selected_hypothesis_evidence": analog_evidence,
        "critical_signature_match_company_keys": critical_match_keys,
        "hypothesis_rankings": {
            hypothesis: values[:5]
            for hypothesis, values in rankings.items()
        },
        "request_plan": request_plan,
        "execution_gate": gate,
        "boundaries": {
            "page_one_only": True,
            "fixed_request_count": DEFAULT_MAX_REQUESTS,
            "diagnostic_only": True,
            "production_rule_adoption_allowed": False,
            "automatic_analog_selection_allowed": False,
            "database_transaction": "read_only",
            "no_database_write": True,
            "no_pagination": True,
            "no_detail_pages": True,
            "no_candidate_creation": True,
            "no_provider_call": True,
            "no_source_activation": True,
            "no_scheduler_change": True,
            "no_application_action": True,
        },
    }

    print("StepStone directed order-failure reproduction plan")
    print(f"baseline_review_id: {baseline['review_id']}")
    print(f"baseline_observed_at: {baseline['baseline_observed_at'].isoformat()}")
    print(f"not_before: {gate['not_before'].isoformat()}")
    print(f"execution_allowed_now: {str(gate['execution_allowed_now']).lower()}")
    print(f"seed_pair: {seed_a['filter_alias']} -> {seed_b['filter_alias']}")
    print(f"critical_signature_match_count: {len(critical_match_keys)}")
    print(f"selection_status: {plan['selection_status']}")
    for hypothesis in SUPPORTED_HYPOTHESES:
        print(f"hypothesis_leaders[{hypothesis}]:")
        for item in rankings[hypothesis][:3]:
            print(
                f"- {item['filter_alias']} | score={item['similarity_score']} | "
                f"class={item['similarity_class']} | "
                f"critical_signature={str(item['critical_signature']['all_match']).lower()}"
            )
    if analog is not None and analog_evidence is not None:
        print(
            "selected_analog: "
            f"{analog['filter_alias']} | hypothesis={args.analog_hypothesis} | "
            f"score={analog_evidence['similarity_score']} | "
            f"class={analog_evidence['similarity_class']}"
        )
    else:
        print("selected_analog: none")
    if not args.execute:
        print("requests: 0/9")
        print("RESULT: STEPSTONE_ORDER_FAILURE_REPRO_PLAN_COMPLETED")
        return

    if analog is None:
        raise AssertionError("Execution gate must require an analog")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = args.artifact_dir / f"stepstone_order_failure_repro_{stamp}"
    artifact_dir.mkdir(parents=True, exist_ok=False)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT.replace("connector", "order-failure-reproduction"),
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
    seed_diagnosis = classify_directed_pair(
        single_left=summaries["single_a"],
        single_right=summaries["single_b"],
        forward=summaries["seed_a_then_b"],
        reverse=summaries["seed_b_then_a"],
    )
    analog_diagnosis = classify_directed_pair(
        single_left=summaries["single_c"],
        single_right=summaries["single_b"],
        forward=summaries["analog_c_then_b"],
        reverse=summaries["analog_b_then_c"],
    )
    if seed_diagnosis["directed_forward_failure_reproduced"]:
        conclusion = (
            "structural_analog_reproduced_directed_failure"
            if analog_diagnosis["directed_forward_failure_reproduced"]
            else "seed_reproduced_but_selected_analog_did_not"
        )
    else:
        conclusion = "seed_not_reproduced_in_current_observation_window"
    payload = {
        **plan,
        "schema_version": "pipeline.stepstone.order_failure_repro_probe.v2",
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
    print("RESULT: STEPSTONE_ORDER_FAILURE_REPRO_PROBE_COMPLETED")


if __name__ == "__main__":
    main()
