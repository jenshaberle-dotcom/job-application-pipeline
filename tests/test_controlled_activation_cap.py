from pathlib import Path

from src.connectors.base import SearchProfile
from src.ingest_jobs import select_profiles
from src.search_intelligence.connector_autonomy import ConnectorAutonomyPolicy
from src.search_intelligence.controlled_activation import (
    controlled_profile_name,
    decide_controlled_activation,
)


def active_a1_policy() -> ConnectorAutonomyPolicy:
    return ConnectorAutonomyPolicy(
        policy_key="validated_connector_a1",
        autonomy_level="a1_validated_connector_controlled_activation",
        status="approved",
        policy_version="test-a1",
        standing_authorization=True,
        require_connector_validation=True,
        require_exact_activation_readiness=True,
        allowed_activation_readiness="activation_readiness_supported",
        allow_connector_registration=True,
        allow_controlled_source_activation=True,
        allow_bounded_first_ingestion=True,
        allow_recurring_ingestion=False,
        allow_scheduler_mutation=False,
        allow_provider_requests=False,
        allow_ranking_mutation=False,
        allow_application_actions=False,
        approved_by="jens",
    )


def make_profile(name: str, source: str) -> SearchProfile:
    return SearchProfile(
        id=1,
        profile_name=name,
        source_name=source,
        search_location="Hannover",
        search_radius_km=50,
        offer_type=1,
        page_size=3,
    )


def test_exact_supported_a1_activation_is_allowed() -> None:
    decision = decide_controlled_activation(
        connector_validation_passed=True,
        final_approval_passed=True,
        candidate_status="discovery",
        active_profile_count=0,
        activation_readiness="activation_readiness_supported",
        policy=active_a1_policy(),
    )

    assert decision.allowed is True
    assert decision.status == "controlled_activation_apply_ready"


def test_activation_fails_closed_on_non_exact_readiness() -> None:
    decision = decide_controlled_activation(
        connector_validation_passed=True,
        final_approval_passed=True,
        candidate_status="discovery",
        active_profile_count=0,
        activation_readiness="activation_readiness_supported_with_manual_overlap_review",
        policy=active_a1_policy(),
    )

    assert decision.allowed is False
    assert decision.status == "controlled_activation_blocked_a1_or_readiness"


def test_activation_fails_closed_when_already_active() -> None:
    decision = decide_controlled_activation(
        connector_validation_passed=True,
        final_approval_passed=True,
        candidate_status="active_controlled",
        active_profile_count=1,
        activation_readiness="activation_readiness_supported",
        policy=active_a1_policy(),
    )

    assert decision.allowed is False
    assert decision.status == "controlled_activation_blocked_already_active"


def test_profile_name_is_deterministic() -> None:
    assert controlled_profile_name("computacenter") == (
        "computacenter_controlled_hannover_precision"
    )


def test_unscoped_ingestion_excludes_non_recurring_controlled_profile() -> None:
    scheduled = make_profile("scheduled_profile", "stepstone")
    controlled = make_profile(
        "accompio_controlled_hannover_precision",
        "accompio:discovery",
    )

    class FakeRepository:
        def load_active_search_profiles(self):
            return [scheduled, controlled]

        def load_recurring_search_profile_names(self):
            return [scheduled.profile_name]

    selected = select_profiles(
        repository=FakeRepository(),
        profile_name=None,
        source_filter=None,
    )

    assert [profile.profile_name for profile in selected] == [scheduled.profile_name]


def test_exact_profile_execution_can_select_controlled_non_recurring_profile() -> None:
    controlled = make_profile(
        "accompio_controlled_hannover_precision",
        "accompio:discovery",
    )

    class FakeRepository:
        def load_active_search_profiles(self):
            return [controlled]

        def load_recurring_search_profile_names(self):
            return []

    selected = select_profiles(
        repository=FakeRepository(),
        profile_name=controlled.profile_name,
        source_filter=None,
    )

    assert selected == [controlled]


def test_migration_preserves_existing_recurring_behavior_and_adds_boundary() -> None:
    migration = Path(
        "db/migrations/086_decouple_controlled_activation_from_recurring_ingestion.sql"
    ).read_text(encoding="utf-8")

    assert "recurring_ingestion_enabled BOOLEAN NOT NULL DEFAULT TRUE" in migration
    assert "WHERE is_active = TRUE" in migration
    assert "recurring_ingestion_enabled = TRUE" in migration
    assert "scheduler configuration" in migration


def test_activation_runner_reuses_fresh_s7u_and_never_starts_ingestion() -> None:
    source = Path(
        "scripts/run_validated_connector_controlled_activation.py"
    ).read_text(encoding="utf-8")

    assert "run_activation_readiness" in source
    assert "connector_validation_gate" in source
    assert "approve_connector_registration" in source
    assert "recurring_ingestion_enabled" in source
    assert "VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, FALSE)" in source
    assert "connector_autonomy_authorization_events" in source
    assert "controlled_source_activation" in source
    assert "status = 'active_controlled'" in source
    assert "python -m src.ingest_jobs --profile" in source
    assert "python -m src.run_silver_jobs --source" in source
    assert "JobIngestionRunner" not in source
    assert "subprocess" not in source
