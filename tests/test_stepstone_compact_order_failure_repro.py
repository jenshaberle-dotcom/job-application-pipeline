from pathlib import Path

from scripts.run_stepstone_compact_order_failure_repro import (
    DEFAULT_MAX_REQUESTS,
    LOCKED_ANALOG,
    LOCKED_HYPOTHESIS,
    build_compact_request_plan,
    classify_compact_directed_pair,
)


RUNNER = Path("scripts/run_stepstone_compact_order_failure_repro.py")


def _candidate(key: str, alias: str) -> dict[str, object]:
    return {
        "company_key": key,
        "company_name": alias,
        "filter_alias": alias,
        "evidence_count": 1,
    }


def _summary(outcome: str, cards: int) -> dict[str, object]:
    return {
        "outcome": outcome,
        "parsed_card_count": cards,
        "leakage_count": 0,
    }


def test_compact_request_plan_is_exactly_eight_requests() -> None:
    plan = build_compact_request_plan(
        search_term="Machine Learning Engineer",
        seed_a=_candidate("tib", "Technische Informationsbibliothek (TIB)"),
        seed_b=_candidate("hdi", "HDI"),
        analog=_candidate("cg", "CompuGroup Medical SE & Co. KGaA"),
    )

    assert DEFAULT_MAX_REQUESTS == 8
    assert [item["label"] for item in plan] == [
        "a0_baseline",
        "single_a",
        "single_c",
        "seed_a_then_b",
        "seed_b_then_a",
        "analog_c_then_b",
        "analog_b_then_c",
        "a1_baseline_control",
    ]
    assert all(item["label"] != "single_b" for item in plan)


def test_compact_classifier_reproduces_directed_failure_without_single_b() -> None:
    result = classify_compact_directed_pair(
        single_left=_summary("filter_effective_full_refill", 25),
        forward=_summary("filter_effective_no_refill", 0),
        reverse=_summary("filter_effective_full_refill", 25),
    )

    assert result["result"] == "directed_forward_failure_reproduced"
    assert result["directed_forward_failure_reproduced"] is True
    assert result["right_alias_individual_probe_omitted"] is True
    assert result["right_alias_interpretable_via_reverse_pair"] is True


def test_experiment_contract_is_locked_to_one_hypothesis_and_analog() -> None:
    assert LOCKED_ANALOG == "CompuGroup Medical SE & Co. KGaA"
    assert LOCKED_HYPOTHESIS == "syntax_encoding_shape"


def test_runner_preserves_read_only_diagnostic_boundaries() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "DEFAULT_MAX_REQUESTS = 8" in source
    assert '"diagnostic_only": True' in source
    assert '"production_rule_adoption_allowed": False' in source
    assert '"no_database_write": True' in source
    assert '"no_pagination": True' in source
    assert '"no_detail_pages": True' in source
    assert '"no_source_activation": True' in source
    assert '"no_connector_execution": True' in source
    assert '"no_scheduler_change": True' in source
    assert "rule_or_workaround_adoption_allowed: false" in source
