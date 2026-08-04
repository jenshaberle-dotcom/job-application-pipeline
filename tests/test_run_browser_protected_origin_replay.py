from __future__ import annotations

import json
from pathlib import Path
import socket

import pytest

from scripts.run_browser_protected_origin_replay import (
    build_blocked_replay_artifact,
    find_exact_blocked_observation,
    write_artifact,
)

EON_URL = (
    "https://www.eon.com/de/ueber-uns/karriere/"
    "unsere-gesellschaften/digital-technology.html"
)


def _origin_payload() -> dict[str, object]:
    return {
        "artifact_type": "origin_operator_attestation",
        "schema_version": "1.0",
        "review_output_only_not_pipeline_input": True,
        "provider_requests": 0,
        "pipeline_mutation": False,
        "source_activation_allowed": False,
        "origin_evidence": {
            "schema_version": "1.0",
            "evidence_id": "origin-operator-attestation-test",
            "company_key": "e_on_digital_technology",
            "normalized_url": EON_URL,
            "evidence_source": "operator_attestation",
            "observed_at": "2026-08-04T11:00:00Z",
            "expires_at": "2026-09-03T11:00:00Z",
            "verifier_identity": "operator:jens",
            "verifier_version": "operator-origin-attestation-writer/1.0",
            "requested_url": EON_URL,
            "final_url": EON_URL,
            "canonical_url": EON_URL,
            "page_title": "E.ON Digital Technology",
            "observed_entity_tokens": ["digital", "technology"],
            "observed_career_signals": ["karriere"],
            "content_sha256": "a" * 64,
            "screenshot_sha256": None,
            "operator_approval_token": "sha256:" + "b" * 64,
            "challenge_encountered": False,
            "automation_interacted_with_challenge": False,
            "automation_techniques": [],
        },
    }


def _collector_payload(
    *,
    url: str = EON_URL,
    title: str = "Just a moment...",
    reachable: bool = False,
    provider_requests: int = 0,
) -> dict[str, object]:
    return {
        "company_key": "e_on_digital_technology",
        "provider_requests": provider_requests,
        "default_repair": {
            "boundary": {
                "candidate_url_write": False,
                "connector_registration": False,
                "source_activation": False,
                "bronze_silver_write": False,
                "scheduler_change": False,
            },
            "stages": [{"provider_request_count": provider_requests}],
        },
        "alternatives": [
            {
                "url": url,
                "provider": "operator_supplied_unvalidated",
                "assessment": {
                    "final_url": url,
                    "probe": {
                        "status_code": 403,
                        "reachable": reachable,
                        "title": title,
                        "failure_class": "http_403_access_control_challenge",
                    },
                },
            }
        ],
    }


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _build(tmp_path: Path, **changes: object) -> dict[str, object]:
    origin_path = _write_json(tmp_path / "origin.json", _origin_payload())
    collector_payload = changes.pop("collector_payload", _collector_payload())
    assert isinstance(collector_payload, dict)
    collector_path = _write_json(
        tmp_path / "origin_url_default_repair_20260804T095656995956Z.json",
        collector_payload,
    )
    values: dict[str, object] = {
        "company_key": "e_on_digital_technology",
        "operator_url": EON_URL,
        "origin_artifact_path": origin_path,
        "collector_artifact_path": collector_path,
        "replay_at": "2026-08-04T11:30:00Z",
        "collector_observed_at": None,
        "collector_expires_at": None,
    }
    values.update(changes)
    return build_blocked_replay_artifact(**values)  # type: ignore[arg-type]


def test_combines_exact_origin_truth_with_blocked_collector_evidence(
    tmp_path: Path,
) -> None:
    payload = _build(tmp_path)

    replay = payload["architecture_replay"]
    collector = payload["collector_evidence"]
    assert isinstance(replay, dict)
    assert isinstance(collector, dict)
    assert replay["origin_truth_state"] == "verified"
    assert replay["collection_state"] == "blocked_by_access_control"
    assert replay["decision"] == "origin_verified_collection_blocked"
    assert replay["source_activation_allowed"] is False
    assert collector["status_code"] == 403
    assert collector["reachable"] is False
    assert collector["challenge_detected"] is True
    assert payload["provider_requests"] == 0
    assert payload["pipeline_mutation"] is False
    assert payload["review_output_only_not_pipeline_input"] is True


def test_recursive_match_does_not_depend_on_one_nesting_path() -> None:
    payload = {
        "outer": {
            "rows": [
                {
                    "candidate": {"requested_url": EON_URL},
                    "transport": {
                        "http_status": 403,
                        "reachable": False,
                        "diagnostics": ["access control challenge"],
                    },
                }
            ]
        }
    }

    match = find_exact_blocked_observation(payload, operator_url=EON_URL)

    assert match["status_code"] == 403
    assert match["reachable"] is False


def test_rejects_403_for_a_different_url(tmp_path: Path) -> None:
    collector = _collector_payload(url="https://www.eon.com/de/karriere.html")

    with pytest.raises(ValueError, match="exact-URL HTTP 403"):
        _build(tmp_path, collector_payload=collector)


def test_rejects_generic_403_without_challenge_evidence(tmp_path: Path) -> None:
    collector = _collector_payload(title="Ordinary corporate page")
    probe = collector["alternatives"][0]["assessment"]["probe"]  # type: ignore[index]
    assert isinstance(probe, dict)
    probe["failure_class"] = "http_error"

    with pytest.raises(ValueError, match="challenge/access-control"):
        _build(tmp_path, collector_payload=collector)


def test_rejects_reachable_403_as_inconsistent_evidence(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exact-URL HTTP 403"):
        _build(tmp_path, collector_payload=_collector_payload(reachable=True))


def test_rejects_collector_artifact_with_provider_requests(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="used provider requests"):
        _build(
            tmp_path,
            collector_payload=_collector_payload(provider_requests=1),
        )


def test_rejects_expired_origin_evidence(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="failed blocked-origin architecture replay"):
        _build(tmp_path, replay_at="2026-10-04T11:30:00Z")


def test_output_is_deterministic_for_identical_artifacts(tmp_path: Path) -> None:
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert first == second


def test_build_is_network_free(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    def forbidden_connection(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "create_connection", forbidden_connection)

    payload = _build(tmp_path)

    assert payload["provider_requests"] == 0
    assert payload["pipeline_mutation"] is False


def test_writer_refuses_overwrite(tmp_path: Path) -> None:
    payload = _build(tmp_path)
    output = tmp_path / "replay.json"

    write_artifact(payload, output)

    with pytest.raises(ValueError, match="refusing overwrite"):
        write_artifact(payload, output)
