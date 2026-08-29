from __future__ import annotations

import argparse

import pytest

from scripts.run_deterministic_connector_builder_layer_audit_v5 import (
    _portal_overlay,
    _promote_inventory_failure_via_portal,
)
from src.connectors.employer_origin_acquisition import AcquiredJobPage
from src.search_intelligence.deterministic_connector_builder import (
    ConnectorBuilderAssessment,
    complete_after_failure,
    passed,
    skipped,
)


def _inventory_failure() -> ConnectorBuilderAssessment:
    prefix = [
        passed("identity", "identity"),
        passed("origin", "origin"),
        passed("origin_reachability", "reachable"),
        skipped("delegation", "not required on baseline"),
        skipped("provider", "provider not required on baseline"),
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


def _job() -> AcquiredJobPage:
    return AcquiredJobPage(
        requested_url="https://karriere.example.com/jobs/platform-engineer-123",
        final_url="https://karriere.example.com/jobs/platform-engineer-123",
        status_code=200,
        title="Platform Engineer",
        html_bytes=600,
        proof_kind="job_url_and_job_content",
        discovery_source="anchor_detail",
        anchor_text="Platform Engineer",
    )


def test_portal_overlay_promotes_inventory_residual_and_rewrites_delegation() -> None:
    baseline = _inventory_failure()

    promoted = _promote_inventory_failure_via_portal(
        baseline,
        job=_job(),
        observed_portal="https://karriere.example.com/",
        requests=[
            {"method": "GET"},
            {"method": "GET"},
            {"method": "GET"},
        ],
    )

    assert promoted.recipe_ready is True
    assert promoted.first_failure is None
    assert promoted.layers[:3] == baseline.layers[:3]
    assert promoted.layers[3].layer == "delegation"
    assert promoted.layers[3].state.value == "pass"
    assert promoted.layers[3].evidence["carrier"] == "explicit_portal_cta"
    assert promoted.layers[4] == baseline.layers[4]
    assert promoted.layers[5].evidence["discovery_source"] == "anchor_detail"
    assert promoted.layers[7].evidence["proof_kind"] == "job_url_and_job_content"
    assert promoted.layers[8].evidence["materialization_performed"] is False


def test_portal_promotion_refuses_non_inventory_residual() -> None:
    baseline = ConnectorBuilderAssessment(
        2,
        "acme",
        "Acme GmbH",
        complete_after_failure(
            [passed("identity", "identity")],
            failed_layer="origin",
            failure_reason="no origin",
        ),
    )

    with pytest.raises(ValueError, match="first-failure mismatch"):
        _promote_inventory_failure_via_portal(
            baseline,
            job=_job(),
            observed_portal="https://karriere.example.com/",
            requests=[],
        )


def test_portal_overlay_is_not_attempted_after_non_inventory_result() -> None:
    baseline = ConnectorBuilderAssessment(
        3,
        "acme",
        "Acme GmbH",
        complete_after_failure(
            [passed("identity", "identity")],
            failed_layer="origin",
            failure_reason="no origin",
        ),
    )

    result, evidence = _portal_overlay({}, argparse.Namespace(), baseline)

    assert result is baseline
    assert evidence is None
