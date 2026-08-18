from __future__ import annotations

from src.search_intelligence.llm_booster_policy import (
    BoosterSurface,
    build_booster_replay_decision,
    booster_input_fingerprint,
)


def test_product_v1_booster_surfaces_have_canonical_replay_identities() -> None:
    assert BoosterSurface.PRODUCT_V1_ASSESSMENT.value == "product_v1_assessment"
    assert BoosterSurface.PRODUCT_V1_RANKING.value == "product_v1_ranking"
    assert BoosterSurface.PRODUCT_V1_APPLICATION.value == "product_v1_application"


def test_replay_fingerprint_is_stable_across_scope_order_and_duplicates() -> None:
    first = booster_input_fingerprint(
        surface=BoosterSurface.PRODUCT_V1_ASSESSMENT,
        source_identity="silver_job:42",
        normalized_input_hash="abc123",
        unresolved_scope=("weekly_hours", "work_model", "weekly_hours"),
    )
    reordered = booster_input_fingerprint(
        surface=BoosterSurface.PRODUCT_V1_ASSESSMENT,
        source_identity="silver_job:42",
        normalized_input_hash="abc123",
        unresolved_scope=("work_model", "weekly_hours"),
    )

    assert first == reordered
    assert len(first) == 64


def test_replay_fingerprint_changes_for_material_surface_input_or_source_delta() -> None:
    baseline = booster_input_fingerprint(
        surface=BoosterSurface.PRODUCT_V1_RANKING,
        source_identity="silver_job:42",
        normalized_input_hash="abc123",
        unresolved_scope=("reliability_focus",),
    )
    changed_input = booster_input_fingerprint(
        surface=BoosterSurface.PRODUCT_V1_RANKING,
        source_identity="silver_job:42",
        normalized_input_hash="def456",
        unresolved_scope=("reliability_focus",),
    )
    changed_source = booster_input_fingerprint(
        surface=BoosterSurface.PRODUCT_V1_RANKING,
        source_identity="silver_job:43",
        normalized_input_hash="abc123",
        unresolved_scope=("reliability_focus",),
    )
    changed_surface = booster_input_fingerprint(
        surface=BoosterSurface.PRODUCT_V1_APPLICATION,
        source_identity="silver_job:42",
        normalized_input_hash="abc123",
        unresolved_scope=("reliability_focus",),
    )

    assert len({baseline, changed_input, changed_source, changed_surface}) == 4


def test_exact_terminal_replay_is_provider_ineligible_with_zero_side_effects() -> None:
    fingerprint = booster_input_fingerprint(
        surface=BoosterSurface.PRODUCT_V1_APPLICATION,
        source_identity="silver_job:42",
        normalized_input_hash="manifest123",
        unresolved_scope=("draft_for_review",),
    )

    decision = build_booster_replay_decision(
        surface=BoosterSurface.PRODUCT_V1_APPLICATION,
        source_identity="silver_job:42",
        normalized_input_hash="manifest123",
        unresolved_scope=("draft_for_review",),
        prior_terminal_input_fingerprints=(fingerprint,),
    )

    assert decision.input_fingerprint == fingerprint
    assert decision.provider_eligible is False
    assert decision.replay_suppressed is True
    assert decision.reason_code == "unchanged_terminal_booster_input_fingerprint"
    assert decision.provider_requests == 0
    assert decision.llm_requests == 0
    assert decision.database_requests == 0
    assert decision.product_writes == 0
    assert decision.product_authority is False


def test_changed_input_remains_provider_eligible_after_prior_terminal_result() -> None:
    previous = booster_input_fingerprint(
        surface=BoosterSurface.PRODUCT_V1_ASSESSMENT,
        source_identity="silver_job:42",
        normalized_input_hash="old",
        unresolved_scope=("work_model",),
    )

    decision = build_booster_replay_decision(
        surface=BoosterSurface.PRODUCT_V1_ASSESSMENT,
        source_identity="silver_job:42",
        normalized_input_hash="new",
        unresolved_scope=("work_model",),
        prior_terminal_input_fingerprints=(previous,),
    )

    assert decision.provider_eligible is True
    assert decision.replay_suppressed is False
    assert decision.reason_code == "new_or_changed_booster_input_fingerprint"
    assert decision.provider_requests == 0
    assert decision.product_authority is False
