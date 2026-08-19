from pathlib import Path

import pytest

from src.search_intelligence.search_term_cycle_state_reconcile import (
    normalize_search_term,
    plan_cycle_state_reconcile,
)


ACTIVE_ML_FIRST = (
    "AI Engineer",
    "AI Platform Engineer",
    "AI Reliability Engineer",
    "Analytics Engineer",
    "Data Engineer",
    "Data Platform Engineer",
    "ML Engineer",
    "ML Platform Engineer",
    "ML Reliability Engineer",
    "MLOps Engineer",
    "Machine Learning",
    "Machine Learning Engineer",
)


def test_plan_replaces_stale_data_first_wave_with_active_ml_first_truth() -> None:
    current = (
        "Analytics Engineer",
        "Data Engineer",
        "Big Data",
        "Data Platform",
        "Data Warehouse",
        "ETL",
        "Python SQL",
    )

    plan = plan_cycle_state_reconcile(
        active_terms=ACTIVE_ML_FIRST,
        current_terms=current,
    )

    assert plan.retained_terms == ("Analytics Engineer", "Data Engineer")
    assert set(plan.removed_terms) == {
        "Big Data",
        "Data Platform",
        "Data Warehouse",
        "ETL",
        "Python SQL",
    }
    assert set(plan.added_terms) == set(ACTIVE_ML_FIRST) - {
        "Analytics Engineer",
        "Data Engineer",
    }
    assert plan.changed is True


def test_plan_preserves_retained_term_identity_and_canonicalizes_only_label() -> None:
    plan = plan_cycle_state_reconcile(
        active_terms=("ML Reliability Engineer", "Data Engineer"),
        current_terms=("  ml   reliability engineer  ", "Data Engineer"),
    )

    assert plan.removed_terms == ()
    assert plan.added_terms == ()
    assert plan.canonicalized_terms == (("ml reliability engineer", "ML Reliability Engineer"),)
    assert normalize_search_term(" ML  Reliability Engineer ") == "ml reliability engineer"


def test_duplicate_normalized_execution_rows_fail_closed() -> None:
    with pytest.raises(ValueError, match="duplicate normalized term"):
        plan_cycle_state_reconcile(
            active_terms=("ML Engineer",),
            current_terms=("ML Engineer", "ml engineer"),
        )


def test_empty_active_configuration_fails_closed() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        plan_cycle_state_reconcile(active_terms=(), current_terms=("ETL",))


def test_reconcile_cli_keeps_narrow_authority_boundary() -> None:
    text = Path("scripts/run_stepstone_cycle_state_reconcile.py").read_text(encoding="utf-8")

    assert 'APPROVAL_TOKEN = "RECONCILE-STEPSTONE-CYCLE-STATE-001"' in text
    assert 'if args.source_name != DEFAULT_SOURCE_NAME' in text
    assert 'if args.apply and args.approval_token != APPROVAL_TOKEN' in text
    assert "DELETE FROM search_term_cycle_state" in text
    assert "INSERT INTO search_term_cycle_state" in text
    assert "UPDATE search_term_cycle_state" in text
    assert "requests.get" not in text
    assert "openai" not in text.lower()
    assert '"provider_requests": 0' in text
    assert '"tavily_requests": 0' in text
    assert '"connector_mutation": False' in text
    assert '"scheduler_mutation": False' in text
    assert '"product_mutation": False' in text
