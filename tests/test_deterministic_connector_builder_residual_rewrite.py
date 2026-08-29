from __future__ import annotations

import pytest

from src.search_intelligence.deterministic_connector_builder import (
    ConnectorBuilderAssessment,
    complete_after_failure,
    failed,
    not_reached,
    passed,
    rewrite_residual_suffix,
    skipped,
)


def _inventory_failure() -> ConnectorBuilderAssessment:
    prefix = [
        passed("identity", "identity"),
        passed("origin", "origin"),
        passed("origin_reachability", "reachable"),
        skipped("delegation", "not required"),
        skipped("provider", "not required"),
    ]
    return ConnectorBuilderAssessment(
        1,
        "acme",
        "Acme GmbH",
        complete_after_failure(
            prefix,
            failed_layer="inventory",
            failure_reason="no executable inventory path",
        ),
    )


def test_residual_rewrite_preserves_prefix_and_may_advance_failure() -> None:
    baseline = _inventory_failure()

    rewritten = rewrite_residual_suffix(
        baseline,
        expected_first_failure="inventory",
        rewrite_from_layer="provider",
        replacement_suffix=(
            passed("provider", "provider observed", required=False),
            passed("inventory", "inventory reached"),
            failed("detail", "detail not yet resolved"),
            not_reached("proof", "blocked by detail", blocked_by="detail"),
            not_reached("recipe", "blocked by detail", blocked_by="detail"),
        ),
    )

    assert rewritten.layers[:4] == baseline.layers[:4]
    assert rewritten.first_failure is not None
    assert rewritten.first_failure.layer == "detail"


def test_residual_rewrite_can_promote_to_ready() -> None:
    baseline = _inventory_failure()

    rewritten = rewrite_residual_suffix(
        baseline,
        expected_first_failure="inventory",
        rewrite_from_layer="provider",
        replacement_suffix=(
            passed("provider", "provider observed", required=False),
            passed("inventory", "inventory reached"),
            passed("detail", "detail reached"),
            passed("proof", "strict proof passed"),
            passed("recipe", "recipe compile-ready", materialization_performed=False),
        ),
    )

    assert rewritten.layers[:4] == baseline.layers[:4]
    assert rewritten.first_failure is None
    assert rewritten.recipe_ready is True


def test_residual_rewrite_rejects_wrong_first_failure() -> None:
    baseline = _inventory_failure()

    with pytest.raises(ValueError, match="first-failure mismatch"):
        rewrite_residual_suffix(
            baseline,
            expected_first_failure="detail",
            rewrite_from_layer="detail",
            replacement_suffix=(
                passed("detail", "detail"),
                passed("proof", "proof"),
                passed("recipe", "recipe"),
            ),
        )


def test_residual_rewrite_rejects_start_after_failure() -> None:
    baseline = _inventory_failure()

    with pytest.raises(ValueError, match="start at or before"):
        rewrite_residual_suffix(
            baseline,
            expected_first_failure="inventory",
            rewrite_from_layer="detail",
            replacement_suffix=(
                passed("detail", "detail"),
                passed("proof", "proof"),
                passed("recipe", "recipe"),
            ),
        )


def test_residual_rewrite_rejects_noncanonical_suffix() -> None:
    baseline = _inventory_failure()

    with pytest.raises(ValueError, match="suffix mismatch"):
        rewrite_residual_suffix(
            baseline,
            expected_first_failure="inventory",
            rewrite_from_layer="provider",
            replacement_suffix=(
                passed("provider", "provider"),
                passed("detail", "detail"),
                passed("proof", "proof"),
                passed("recipe", "recipe"),
            ),
        )


def test_residual_rewrite_rejects_earlier_regression() -> None:
    baseline = _inventory_failure()

    with pytest.raises(ValueError, match="introduced an earlier first failure"):
        rewrite_residual_suffix(
            baseline,
            expected_first_failure="inventory",
            rewrite_from_layer="delegation",
            replacement_suffix=(
                failed("delegation", "regression"),
                skipped("provider", "not required"),
                passed("inventory", "inventory"),
                passed("detail", "detail"),
                passed("proof", "proof"),
                passed("recipe", "recipe"),
            ),
        )
