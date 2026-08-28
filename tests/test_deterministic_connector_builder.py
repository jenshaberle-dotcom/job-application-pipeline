from __future__ import annotations

import pytest

from src.search_intelligence.deterministic_connector_builder import (
    ConnectorBuilderAssessment,
    LAYER_ORDER,
    LayerResult,
    LayerState,
    complete_after_failure,
    not_reached,
    passed,
    skipped,
    summarize_assessments,
)


def _ready_layers() -> tuple[LayerResult, ...]:
    return (
        passed("identity", "stable employer identity"),
        passed("origin", "authorized origin selected"),
        passed("origin_reachability", "origin fetched"),
        skipped("delegation", "same-origin inventory makes external delegation unnecessary"),
        skipped("provider", "generic server-rendered inventory is sufficient"),
        passed("inventory", "job inventory observed"),
        passed("detail", "concrete job detail reached"),
        passed("proof", "strict genuine-job proof passed"),
        passed("recipe", "all evidence-required layers satisfied"),
    )


def test_optional_layers_can_be_skipped_without_preventing_recipe_ready() -> None:
    assessment = ConnectorBuilderAssessment(
        candidate_id=1,
        company_key="example",
        company_name="Example GmbH",
        layers=_ready_layers(),
    )

    assert assessment.recipe_ready is True
    assert assessment.first_failure is None
    assert assessment.layers[3].state == LayerState.SKIPPED
    assert assessment.layers[3].required is False
    assert assessment.layers[4].state == LayerState.SKIPPED


def test_observed_optional_capability_can_pass_without_becoming_required() -> None:
    item = passed(
        "delegation",
        "external portal exists but same-origin detail path is already observed",
        required=False,
    )

    assert item.state == LayerState.PASS
    assert item.required is False


def test_only_required_layers_may_fail() -> None:
    with pytest.raises(ValueError, match="only evidence-required layers may FAIL"):
        LayerResult(
            "provider",
            LayerState.FAIL,
            False,
            "provider was optional",
        )


def test_required_layer_cannot_be_skipped() -> None:
    with pytest.raises(ValueError, match="SKIPPED requires evidence"):
        LayerResult(
            "origin",
            LayerState.SKIPPED,
            True,
            "invalid skip",
        )


def test_not_reached_keeps_necessity_undecided() -> None:
    item = not_reached("provider", "upstream evidence missing")

    assert item.state == LayerState.NOT_REACHED
    assert item.required is None


def test_complete_after_failure_does_not_invent_downstream_necessity() -> None:
    layers = complete_after_failure(
        (
            passed("identity", "stable employer identity"),
        ),
        failed_layer="origin",
        failure_reason="no authorized origin found",
    )

    assert tuple(item.layer for item in layers) == LAYER_ORDER
    assert layers[1].state == LayerState.FAIL
    assert layers[1].required is True
    assert all(item.state == LayerState.NOT_REACHED for item in layers[2:])
    assert all(item.required is None for item in layers[2:])


def test_summary_counts_first_required_failure_and_skips_separately() -> None:
    ready = ConnectorBuilderAssessment(
        candidate_id=1,
        company_key="ready",
        company_name="Ready GmbH",
        layers=_ready_layers(),
    )
    failed_layers = complete_after_failure(
        (passed("identity", "stable employer identity"),),
        failed_layer="origin",
        failure_reason="no authorized origin found",
    )
    blocked = ConnectorBuilderAssessment(
        candidate_id=2,
        company_key="blocked",
        company_name="Blocked GmbH",
        layers=failed_layers,
    )

    summary = summarize_assessments((ready, blocked))

    assert summary["candidate_count"] == 2
    assert summary["recipe_ready_count"] == 1
    assert summary["first_failure_counts"] == {"origin": 1}
    assert summary["layer_state_counts"]["provider"]["skipped"] == 1
    assert summary["layer_state_counts"]["provider"]["not_reached"] == 1
