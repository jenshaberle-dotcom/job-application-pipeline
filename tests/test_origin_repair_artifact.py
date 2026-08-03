from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import pytest

from src.search_intelligence.origin_repair_artifact import (
    ArtifactValidationError,
    load_validated_repair_payload,
)

NOW = datetime(2026, 8, 3, 18, 0, tzinfo=UTC)


def _document(*, generated_at: datetime = NOW) -> dict[str, object]:
    selected_url = "https://career.1and1.org/"
    return {
        "schema_version": "origin_url_default_repair.v2",
        "generated_at_utc": generated_at.isoformat(),
        "review_output_only_not_pipeline_input": True,
        "results": [
            {
                "company_key": "1_1",
                "company_name": "1&1",
                "decision": "origin_url_candidate_selected",
                "selected_url": selected_url,
                "confidence_score": 1.0,
                "reason": "validated deterministic symbol-brand host",
                "default_repair": {
                    "company_key": "1_1",
                    "company_name": "1&1",
                    "final_state": "selected_deterministic_symbol_brand",
                    "selected_url": selected_url,
                    "recommended_url": None,
                    "selected_stage": "deterministic_symbol_brand",
                    "operator_review_required": False,
                    "repair_exhausted": False,
                    "configuration_blocked": False,
                    "stages": [],
                    "boundary": {
                        "candidate_url_write": False,
                        "connector_registration": False,
                        "source_activation": False,
                        "bronze_silver_write": False,
                        "scheduler_change": False,
                    },
                },
                "adaptive_search": {
                    "repeated_state_detected": False,
                    "attempted_queries": [],
                    "attempted_urls": [selected_url],
                },
            }
        ],
    }


def _write(path: Path, document: dict[str, object]) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")


def test_selected_fresh_artifact_is_reusable_without_provider_rerun(tmp_path) -> None:
    path = tmp_path / "repair.json"
    _write(path, _document())

    payload = load_validated_repair_payload(
        path,
        company_key="1_1",
        max_age_hours=24,
        now=NOW + timedelta(hours=1),
    )

    assert payload["selected_url"] == "https://career.1and1.org/"
    provenance = payload["artifact_reuse"]
    assert isinstance(provenance, dict)
    assert provenance["validated"] is True
    assert provenance["provider_rerun"] is False
    assert provenance["selected_stage"] == "deterministic_symbol_brand"
    assert len(str(provenance["artifact_sha256"])) == 64


def test_artifact_selected_url_mismatch_fails_closed(tmp_path) -> None:
    path = tmp_path / "repair.json"
    document = _document()
    result = document["results"][0]  # type: ignore[index]
    result["selected_url"] = "https://wrong.example/"  # type: ignore[index]
    _write(path, document)

    with pytest.raises(ArtifactValidationError, match="does not match"):
        load_validated_repair_payload(path, company_key="1_1", now=NOW)


def test_stale_artifact_fails_closed(tmp_path) -> None:
    path = tmp_path / "repair.json"
    _write(path, _document(generated_at=NOW - timedelta(hours=25)))

    with pytest.raises(ArtifactValidationError, match="older than"):
        load_validated_repair_payload(
            path,
            company_key="1_1",
            max_age_hours=24,
            now=NOW,
        )


def test_repeated_state_artifact_fails_closed(tmp_path) -> None:
    path = tmp_path / "repair.json"
    document = _document()
    result = document["results"][0]  # type: ignore[index]
    result["adaptive_search"]["repeated_state_detected"] = True  # type: ignore[index]
    _write(path, document)

    with pytest.raises(ArtifactValidationError, match="repeated discovery state"):
        load_validated_repair_payload(path, company_key="1_1", now=NOW)
