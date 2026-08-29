from __future__ import annotations

import pytest

from scripts.run_deterministic_connector_builder_layer_audit_v4 import (
    _promote_inventory_failure,
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
        skipped("delegation", "not required"),
        skipped("provider", "not yet required"),
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


def test_workday_overlay_promotes_only_downstream_layers_after_inventory_failure() -> None:
    baseline = _inventory_failure()
    job = AcquiredJobPage(
        requested_url="https://acme.wd5.myworkdayjobs.com/en-US/acme/job/Berlin/X_JR1",
        final_url="https://acme.wd5.myworkdayjobs.com/en-US/acme/job/Berlin/X_JR1",
        status_code=200,
        title="Platform Engineer",
        html_bytes=500,
        proof_kind="job_url_and_job_content",
        discovery_source="workday_cxs_inventory_detail",
        anchor_text="",
    )

    promoted = _promote_inventory_failure(
        baseline,
        job=job,
        observed_root="https://jobs.acme.example/",
        requests=[{"method": "GET"}, {"method": "POST"}, {"method": "GET"}],
    )

    assert promoted.recipe_ready is True
    assert promoted.first_failure is None
    assert promoted.layers[:4] == baseline.layers[:4]
    assert promoted.layers[4].layer == "provider"
    assert promoted.layers[4].state.value == "pass"
    assert promoted.layers[4].evidence["provider"] == "workday"
    assert promoted.layers[5].evidence["discovery_source"] == "workday_cxs_inventory_detail"
    assert promoted.layers[7].evidence["proof_kind"] == "job_url_and_job_content"
    assert promoted.layers[8].evidence["materialization_performed"] is False


def test_workday_overlay_refuses_to_rewrite_non_inventory_failure() -> None:
    prefix = [passed("identity", "identity")]
    baseline = ConnectorBuilderAssessment(
        2,
        "acme",
        "Acme GmbH",
        complete_after_failure(
            prefix,
            failed_layer="origin",
            failure_reason="no origin",
        ),
    )
    job = AcquiredJobPage(
        requested_url="https://acme.wd5.myworkdayjobs.com/en-US/acme/job/Berlin/X_JR1",
        final_url="https://acme.wd5.myworkdayjobs.com/en-US/acme/job/Berlin/X_JR1",
        status_code=200,
        title="Platform Engineer",
        html_bytes=500,
        proof_kind="job_url_and_job_content",
        discovery_source="workday_cxs_inventory_detail",
        anchor_text="",
    )

    with pytest.raises(ValueError, match="first-failure mismatch"):
        _promote_inventory_failure(
            baseline,
            job=job,
            observed_root="https://jobs.acme.example/",
            requests=[],
        )
