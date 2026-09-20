from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json

import pytest

from src.ingestion.connector_work_item import (
    ConnectorWorkItem,
    SCHEMA_VERSION,
    build_connector_work_item,
)


PIPELINE_SHA = "a" * 40


@dataclass
class Profile:
    id: int = 42
    profile_name: str = "hdi"
    source_name: str = "generic_origin:hdi"


def test_work_item_is_deterministic_for_same_scheduler_slot() -> None:
    slot = datetime(2026, 9, 20, 18, 0, tzinfo=UTC)
    first = build_connector_work_item(
        Profile(),
        source_role="employer_origin",
        pipeline_sha=PIPELINE_SHA,
        scheduled_for=slot,
    )
    second = build_connector_work_item(
        Profile(),
        source_role="employer_origin",
        pipeline_sha=PIPELINE_SHA,
        scheduled_for=slot,
    )

    assert first == second
    assert first.schema_version == SCHEMA_VERSION
    assert len(first.work_id) == 64


def test_work_item_changes_when_scheduler_slot_changes() -> None:
    first = build_connector_work_item(
        Profile(),
        source_role="employer_origin",
        pipeline_sha=PIPELINE_SHA,
        scheduled_for="2026-09-20T18:00:00Z",
    )
    second = build_connector_work_item(
        Profile(),
        source_role="employer_origin",
        pipeline_sha=PIPELINE_SHA,
        scheduled_for="2026-09-20T19:00:00Z",
    )

    assert first.work_id != second.work_id


def test_json_round_trip_preserves_exact_binding() -> None:
    item = build_connector_work_item(
        Profile(),
        source_role="employer_origin",
        pipeline_sha=PIPELINE_SHA,
        scheduled_for="2026-09-20T18:00:00+00:00",
    )

    restored = ConnectorWorkItem.from_json(item.to_json())

    assert restored == item
    assert json.loads(restored.to_json())["source_name"] == "generic_origin:hdi"


def test_tampered_work_id_fails_closed() -> None:
    item = build_connector_work_item(
        Profile(),
        source_role="employer_origin",
        pipeline_sha=PIPELINE_SHA,
        scheduled_for="2026-09-20T18:00:00Z",
    )
    payload = item.to_dict()
    payload["work_id"] = "0" * 64

    with pytest.raises(ValueError, match="work_id_binding_mismatch"):
        ConnectorWorkItem.from_dict(payload)


@pytest.mark.parametrize("role", ["unknown", "", "provider"])
def test_unknown_source_role_is_rejected(role: str) -> None:
    with pytest.raises(ValueError):
        build_connector_work_item(
            Profile(),
            source_role=role,
            pipeline_sha=PIPELINE_SHA,
            scheduled_for="2026-09-20T18:00:00Z",
        )


def test_naive_scheduler_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="scheduled_for_utc_timezone_required"):
        build_connector_work_item(
            Profile(),
            source_role="employer_origin",
            pipeline_sha=PIPELINE_SHA,
            scheduled_for=datetime(2026, 9, 20, 18, 0),
        )
