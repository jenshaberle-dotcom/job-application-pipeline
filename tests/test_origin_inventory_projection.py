from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any

from scripts import run_origin_inventory_projection as runner
from src.search_intelligence.origin_inventory_projection import (
    CURRENT_OBSERVATION_QUERY,
    READ_ONLY_BOUNDARY,
    project_origin_observations,
    read_current_origin_observations,
)


AS_OF = date(2026, 8, 1)


def observation(
    *,
    observed: int,
    relevant: int,
    keys: list[str],
    currently_live: bool | None,
    confidence: float = 0.9,
) -> dict[str, object]:
    return {
        "reachable": True,
        "observed_job_count": observed,
        "relevant_job_count": relevant,
        "relevant_job_keys": keys,
        "failed_reobservation_attempt": 0,
        "new_external_job_event": False,
        "external_job_signal": {
            "currently_live": currently_live,
            "confidence": confidence,
            "observation_count": 1,
            "origin_miss_count": 0,
        },
    }


def row(
    candidate_id: int,
    *,
    value: dict[str, object] | None,
    company_key: str = "example",
    company_name: str = "Example SE",
    gate_status: str = "passed",
    decision: str = "continue",
    source_type: str = "employer_origin_career_site",
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "company_key": company_key,
        "company_name": company_name,
        "candidate_url": f"https://example.test/{candidate_id}",
        "source_family_candidate": "example_family",
        "source_target_candidate": "example",
        "source_type_candidate": source_type,
        "candidate_status": "candidate",
        "risk_level": "low",
        "gate_name": "origin_inventory_observation",
        "gate_status": gate_status,
        "decision": decision,
        "evidence": (
            {} if value is None else {"origin_inventory_observation": value}
        ),
        "reviewed_at": "2026-08-01T10:00:00+00:00",
    }


def test_confirmed_origin_is_projected_from_approved_observation() -> None:
    projected = project_origin_observations(
        [row(1, value=observation(observed=1, relevant=1, keys=["J1"], currently_live=True))],
        as_of=AS_OF,
    )

    company = projected.companies[0]
    assert company.status == "resolved"
    assert company.resolution is not None
    assert company.resolution["status"] == "confirmed_origin"
    assert company.resolution["selected_candidate_ids"] == ["1"]


def test_explicit_zero_job_observation_remains_dormant() -> None:
    projected = project_origin_observations(
        [row(1, value=observation(observed=0, relevant=0, keys=[], currently_live=False))],
        as_of=AS_OF,
    )

    resolution = projected.companies[0].resolution
    assert resolution is not None
    assert resolution["status"] == "dormant_origin_candidate"
    assert resolution["selected_candidate_ids"] == []
    assert resolution["reobservation"]["mode"] == "scheduled"


def test_missing_observation_is_needs_inspection_not_guessed() -> None:
    projected = project_origin_observations([row(1, value=None)], as_of=AS_OF)

    company = projected.companies[0]
    assert company.status == "needs_inspection"
    assert company.resolution is None
    assert [issue.code for issue in company.issues] == [
        "missing_origin_inventory_observation"
    ]


def test_contradictory_external_signals_block_company_projection() -> None:
    projected = project_origin_observations(
        [
            row(1, value=observation(observed=1, relevant=1, keys=["J1"], currently_live=True)),
            row(2, value=observation(observed=0, relevant=0, keys=[], currently_live=False)),
        ],
        as_of=AS_OF,
    )

    company = projected.companies[0]
    assert company.status == "needs_inspection"
    assert company.resolution is None
    assert "contradictory_company_observation" in {
        issue.code for issue in company.issues
    }


class FakeCursor:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.statements: list[str] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, statement: str) -> None:
        self.statements.append(statement)

    def fetchall(self) -> list[dict[str, object]]:
        return self.rows


class FakeConnection:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.cursor_instance = FakeCursor(rows)
        self.rollback_count = 0

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def rollback(self) -> None:
        self.rollback_count += 1


def test_database_reader_is_read_only_and_rolls_back() -> None:
    connection = FakeConnection([row(1, value=None)])

    observed = read_current_origin_observations(connection)

    assert len(observed) == 1
    assert connection.cursor_instance.statements[0] == "SET TRANSACTION READ ONLY"
    assert connection.cursor_instance.statements[1] == CURRENT_OBSERVATION_QUERY
    assert connection.rollback_count == 1
    assert READ_ONLY_BOUNDARY["no_database_write"] is True
    assert READ_ONLY_BOUNDARY["no_candidate_or_gate_mutation"] is True


def test_runner_writes_deterministic_review_artifact(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    connection = FakeConnection(
        [row(1, value=observation(observed=1, relevant=1, keys=["J1"], currently_live=True))]
    )
    output = tmp_path / "projection.json"
    monkeypatch.setattr(runner.psycopg, "connect", lambda **_: connection)
    monkeypatch.setattr(runner, "get_database_config", lambda: {})

    assert runner.run(argparse.Namespace(output=output, as_of=AS_OF)) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "origin_inventory_projection.v1"
    assert payload["resolved_company_count"] == 1
    assert payload["companies"][0]["resolution"]["status"] == "confirmed_origin"
    assert payload["boundary"]["review_output_only_not_pipeline_input"] is True
