from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.run_stepstone_order_failure_repro_probe import (
    APPROVAL_TOKEN,
    build_request_plan,
    classify_directed_pair,
    enforce_execution_gate,
    select_analog,
)
from src.search_intelligence.stepstone_filter_failure_similarity import (
    HYPOTHESIS_ACRONYM_NAME,
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
        analog=_candidate("sva", "SVA System Vertrieb Alexander"),
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


def test_analog_selection_is_explicit_and_cannot_reuse_seed() -> None:
    candidates = [
        _candidate("tib", "Technische Informationsbibliothek (TIB)"),
        _candidate("hdi", "HDI"),
        _candidate("sva", "SVA System Vertrieb Alexander"),
    ]

    assert select_analog(
        candidates=candidates,
        analog_alias=None,
        seed_keys=("tib", "hdi"),
    ) is None
    selected = select_analog(
        candidates=candidates,
        analog_alias="SVA System Vertrieb Alexander",
        seed_keys=("tib", "hdi"),
    )
    assert selected is not None
    assert selected["company_key"] == "sva"

    with pytest.raises(RuntimeError, match="must differ"):
        select_analog(
            candidates=candidates,
            analog_alias="HDI",
            seed_keys=("tib", "hdi"),
        )


def test_execution_gate_requires_analog_hypothesis_token_and_cooldown() -> None:
    baseline = datetime(2026, 8, 3, 6, 53, tzinfo=UTC)
    before = datetime(2026, 8, 4, 6, 52, tzinfo=UTC)
    after = datetime(2026, 8, 4, 6, 54, tzinfo=UTC)
    analog = _candidate("sva", "SVA System Vertrieb Alexander")

    plan_gate = enforce_execution_gate(
        execute=False,
        approval_token=None,
        baseline_observed_at=baseline,
        cooldown_hours=24,
        analog=None,
        hypothesis=None,
        now=before,
    )
    assert plan_gate["execution_allowed_now"] is False

    with pytest.raises(SystemExit, match="explicit --analog-alias"):
        enforce_execution_gate(
            execute=True,
            approval_token=APPROVAL_TOKEN,
            baseline_observed_at=baseline,
            cooldown_hours=24,
            analog=None,
            hypothesis=HYPOTHESIS_ACRONYM_NAME,
            now=after,
        )

    with pytest.raises(SystemExit, match="explicit --analog-hypothesis"):
        enforce_execution_gate(
            execute=True,
            approval_token=APPROVAL_TOKEN,
            baseline_observed_at=baseline,
            cooldown_hours=24,
            analog=analog,
            hypothesis=None,
            now=after,
        )

    with pytest.raises(SystemExit, match="exact --approval-token"):
        enforce_execution_gate(
            execute=True,
            approval_token="wrong",
            baseline_observed_at=baseline,
            cooldown_hours=24,
            analog=analog,
            hypothesis=HYPOTHESIS_ACRONYM_NAME,
            now=after,
        )

    execute_gate = enforce_execution_gate(
        execute=True,
        approval_token=APPROVAL_TOKEN,
        baseline_observed_at=baseline,
        cooldown_hours=24,
        analog=analog,
        hypothesis=HYPOTHESIS_ACRONYM_NAME,
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


def test_runner_declares_read_only_manual_selection_and_no_production_adoption() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert 'conn.execute("SET TRANSACTION READ ONLY")' in source
    assert "DEFAULT_MAX_REQUESTS = 9" in source
    assert '"no_database_write": True' in source
    assert '"production_rule_adoption_allowed": False' in source
    assert '"automatic_analog_selection_allowed": False' in source
    assert 'parser.add_argument("--analog-alias")' in source
    assert 'parser.add_argument("--analog-hypothesis"' in source
    assert '"no_source_activation": True' in source
    assert '"no_scheduler_change": True' in source
    assert "rule_or_workaround_adoption_allowed: false" in source
