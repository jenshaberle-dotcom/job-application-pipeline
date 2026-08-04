from __future__ import annotations

from pathlib import Path


MIGRATION = Path("db/migrations/085_create_validated_connector_autonomy_a1.sql")
DECISION_REGISTER = Path(
    "docs/reference/product-contract/PRODUCT_DECISION_REGISTER.md"
)
CURRENT_POLICY = Path("docs/current/connector_autonomy_policy.md")


def test_a1_migration_is_fail_closed_and_operator_approved() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "'validated_connector_a1'" in sql
    assert "'a1_validated_connector_controlled_activation'" in sql
    assert "'activation_readiness_supported'" in sql
    assert "'connector-autonomy-a1-2026-08-04'" in sql
    assert "'jens'" in sql
    assert "TIMESTAMPTZ '2026-08-04 20:10:00+02'" in sql
    assert "allow_recurring_ingestion = FALSE" in sql
    assert "allow_scheduler_mutation = FALSE" in sql
    assert "allow_provider_requests = FALSE" in sql
    assert "allow_ranking_mutation = FALSE" in sql
    assert "allow_application_actions = FALSE" in sql


def test_a1_policy_has_audit_and_pause_surfaces() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "status IN ('approved', 'paused', 'revoked')" in sql
    assert "connector_autonomy_authorization_events" in sql
    assert "gold_connector_autonomy_policy" in sql
    assert "paused_reason" in sql


def test_a1_decision_and_current_policy_are_documented() -> None:
    decision_register = DECISION_REGISTER.read_text(encoding="utf-8")
    policy = CURRENT_POLICY.read_text(encoding="utf-8")

    assert "`PD-076` | approved" in decision_register
    assert "Validated Connector Autonomy A1" in policy
    assert "activation_readiness_supported" in policy
    assert "scheduler integration or recurring execution" in policy
