from __future__ import annotations

import json
from pathlib import Path


POLICY = Path("config/connector_fleet_policy.json")


def _policy() -> dict[str, object]:
    return json.loads(POLICY.read_text(encoding="utf-8"))


def test_connector_fleet_policy_closes_candidate_to_recurring_monitoring_loop() -> None:
    policy = _policy()
    lifecycle = policy["lifecycle"]
    assert lifecycle["accepted_candidate_requires_connector_disposition"] is True
    assert lifecycle["active_controlled_requires_recurring_monitoring_admission"] is True
    assert lifecycle["bespoke_connector_per_employer_required"] is False


def test_connector_fleet_default_schedule_is_staggered_and_bounded() -> None:
    policy = _policy()
    scheduling = policy["scheduling"]
    assert scheduling["default_cadence_minutes"] == 24 * 60
    assert scheduling["recent_yield_window_minutes"] == 7 * 24 * 60
    assert scheduling["deterministic_slot_strategy"] == "sha256_source_profile_mod_cadence"
    assert scheduling["max_global_concurrency"] == 5
    assert scheduling["default_provider_or_host_concurrency"] <= scheduling["max_global_concurrency"]
    assert scheduling["retry"]["max_attempts_per_due_run"] == 3


def test_connector_fleet_traffic_light_keeps_technical_health_separate_from_yield() -> None:
    policy = _policy()
    health = policy["health"]
    assert health["green"]["technical_state"] == "current"
    assert health["green"]["minimum_relevant_current_job_observations_in_window"] == 1
    assert health["yellow"]["technical_state"] == "current"
    assert health["yellow"]["maximum_relevant_current_job_observations_in_window"] == 0
    assert "latest_due_execution_failed" in health["red_reasons"]
    assert "overdue_beyond_cadence_plus_grace" in health["red_reasons"]
    assert health["non_operational_lifecycle_state"] == "neutral"
    assert policy["yield"]["raw_loaded_count_is_not_relevance_authority"] is True


def test_connector_fleet_authority_is_shared_across_classic_and_cloud() -> None:
    authority = _policy()["authority"]
    assert authority["product_semantics_repository"] == "jenshaberle-dotcom/job-application-pipeline"
    assert authority["classic_execution_repository"] == "jenshaberle-dotcom/job-pipeline-runtime"
    assert authority["cloud_adaptation_repository"] == "jenshaberle-dotcom/jap-cloud-based"
    assert authority["classic_execution_admission"] == "RCC"
