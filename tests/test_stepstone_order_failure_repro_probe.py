from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.run_stepstone_order_failure_repro_probe import (
    APPROVAL_TOKEN,
    build_request_plan,
    classify_directed_pair,
    enforce_execution_gate,
)


RUNNER = Path("scripts/run_stepstone_order_failure_repro_probe.py")


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


def test_request_plan_is_fixed_nine_request_seed_and_analog_matrix() -> None:
    plan = build_request_plan(
        search_term="Machine Learning Engineer",
        seed_a=_candidate("tib", "Technische Informationsbibliothek (TIB)"),
        seed_b=_candidate("hdi", "HDI"),
        analog=_candidate("luh", "Leibniz Universität Hannover (LUH)"),
    )

    assert [item["label"] for item in plan] == [
        "a0_baseline",
        "single_a",
        "single_b",
        "single_c",
        "seed_a_then_b",
        "seed_b_then_a",
        "analog_c_then_b",
        "analog_b_then_c",
        "a1_baseline_control",
    ]
    assert len(plan) == 9
    assert plan[4]["aliases"] == [
        "Technische Informationsbibliothek (TIB)",
        "HDI",
    ]
    assert plan[5]["aliases"] == [
        "HDI",
        "Technische Informationsbibliothek (TIB)",
    ]


def test_execution_gate_is_baseline_relative_and_exact_token_gated() -> None:
    baseline = datetime(2026, 8, 3, 6, 53, tzinfo=UTC)
    before = datetime(2026, 8, 4, 6, 52, tzinfo=UTC)
    after = datetime(2026, 8, 4, 6, 54, tzinfo=UTC)

    plan_gate = enforce_execution_gate(
        execute=False,
        approval_token=None,
        baseline_observed_at=baseline,
        cooldown_hours=24,
        now=before,
    )
    assert plan_gate["execution_allowed_now"] is False

    with pytest.raises(SystemExit, match="exact --approval-token"):
        enforce_execution_gate(
            execute=True,
            approval_token="wrong",
            baseline_observed_at=baseline,
            cooldown_hours=24,
            now=after,
        )

    execute_gate = enforce_execution_gate(
        execute=True,
        approval_token=APPROVAL_TOKEN,
        baseline_observed_at=baseline,
        cooldown_hours=24,
        now=after,
    )
    assert execute_gate["execution_allowed_now"] is True


def test_classifies_known_directed_zero_nonzero_failure() -> None:
    result = classify_directed_pair(
        single_left=_summary("filter_effective_full_refill", 25),
        single_right=_summary("filter_effective_full_refill", 25),
        forward=_summary("filter_effective_no_refill", 0),
        reverse=_summary("filter_effective_full_refill", 25),
    )

    assert result["result"] == "directed_forward_failure_reproduced"
    assert result["directed_forward_failure_reproduced"] is True


def test_runner_declares_read_only_and_no_production_adoption() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert 'conn.execute("SET TRANSACTION READ ONLY")' in source
    assert "DEFAULT_MAX_REQUESTS = 9" in source
    assert '"no_database_write": True' in source
    assert '"production_rule_adoption_allowed": False' in source
    assert '"no_source_activation": True' in source
    assert '"no_scheduler_change": True' in source
    assert "rule_or_workaround_adoption_allowed: false" in source
