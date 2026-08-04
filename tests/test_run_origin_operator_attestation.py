from __future__ import annotations

import json
from pathlib import Path
import socket

import pytest

from scripts.run_origin_operator_attestation import (
    build_operator_attestation_artifact,
    write_artifact,
)

EON_URL = (
    "https://www.eon.com/de/ueber-uns/karriere/"
    "unsere-gesellschaften/digital-technology.html"
)


def _content(tmp_path: Path, text: str | None = None) -> Path:
    path = tmp_path / "eon-digital-technology.html"
    path.write_text(
        text
        or (
            "<html><title>E.ON Digital Technology Careers</title>"
            "<body>Digital Technology Karriere Jobs bei E.ON.</body></html>"
        ),
        encoding="utf-8",
    )
    return path


def _build(tmp_path: Path, **changes: object) -> dict[str, object]:
    content_path = changes.pop("content_path", None)
    if content_path is None:
        content_path = _content(tmp_path)

    values: dict[str, object] = {
        "company_key": "e_on_digital_technology",
        "operator_url": EON_URL,
        "reviewer_identity": "operator:jens",
        "approval_token": "approved-after-manual-review",
        "page_title": "E.ON Digital Technology Careers",
        "entity_tokens": ("digital", "technology"),
        "career_signals": ("karriere", "jobs"),
        "content_path": content_path,
        "screenshot_path": None,
        "observed_at": "2026-08-04T10:00:00+00:00",
        "expires_at": "2026-09-03T10:00:00+00:00",
    }
    values.update(changes)
    return build_operator_attestation_artifact(**values)  # type: ignore[arg-type]


def test_builds_review_only_unknown_collection_artifact(tmp_path: Path) -> None:
    payload = _build(tmp_path)

    evidence = payload["origin_evidence"]
    replay = payload["architecture_replay"]
    assert isinstance(evidence, dict)
    assert isinstance(replay, dict)
    assert payload["review_output_only_not_pipeline_input"] is True
    assert payload["provider_requests"] == 0
    assert payload["pipeline_mutation"] is False
    assert payload["source_activation_allowed"] is False
    assert replay["decision"] == "origin_verified_collection_unknown"
    assert replay["origin_truth_state"] == "verified"
    assert replay["collection_state"] == "unknown"
    assert replay["source_activation_allowed"] is False
    assert evidence["normalized_url"] == EON_URL
    assert str(evidence["operator_approval_token"]).startswith("sha256:")
    assert "approved-after-manual-review" not in json.dumps(payload)


def test_artifact_id_is_deterministic_for_same_evidence(tmp_path: Path) -> None:
    first = _build(tmp_path)
    second = _build(tmp_path)

    first_evidence = first["origin_evidence"]
    second_evidence = second["origin_evidence"]
    assert isinstance(first_evidence, dict)
    assert isinstance(second_evidence, dict)
    assert first_evidence["evidence_id"] == second_evidence["evidence_id"]
    assert first == second


def test_rejects_challenge_page_content(tmp_path: Path) -> None:
    content = _content(
        tmp_path,
        "<html><title>Just a moment...</title><body>Verify you are human</body></html>",
    )

    with pytest.raises(ValueError, match="challenge marker"):
        _build(tmp_path, content_path=content, page_title="Just a moment...")


def test_rejects_parent_brand_only_content(tmp_path: Path) -> None:
    content = _content(
        tmp_path,
        "<html><title>E.ON Careers</title><body>E.ON Karriere Jobs</body></html>",
    )

    with pytest.raises(ValueError, match="entity tokens"):
        _build(tmp_path, content_path=content, page_title="E.ON Careers")


def test_rejects_non_https_operator_url(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="valid HTTPS"):
        _build(tmp_path, operator_url="http://www.eon.com/de/karriere")


def test_rejects_invalid_expiry(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="later than"):
        _build(
            tmp_path,
            observed_at="2026-08-04T10:00:00+00:00",
            expires_at="2026-08-04T09:00:00+00:00",
        )


def test_optional_screenshot_is_hashed_without_embedding_bytes(tmp_path: Path) -> None:
    screenshot = tmp_path / "eon.png"
    screenshot.write_bytes(b"not-a-real-image-but-bounded-test-evidence")

    payload = _build(tmp_path, screenshot_path=screenshot)

    local = payload["local_evidence"]
    evidence = payload["origin_evidence"]
    assert isinstance(local, dict)
    assert isinstance(evidence, dict)
    assert local["screenshot_file_name"] == "eon.png"
    assert len(str(local["screenshot_sha256"])) == 64
    assert evidence["screenshot_sha256"] == local["screenshot_sha256"]
    assert "not-a-real-image" not in json.dumps(payload)


def test_writer_refuses_to_overwrite_existing_evidence(tmp_path: Path) -> None:
    payload = _build(tmp_path)
    output = tmp_path / "attestation.json"

    write_artifact(payload, output)

    with pytest.raises(ValueError, match="refusing overwrite"):
        write_artifact(payload, output)


def test_writer_output_round_trips(tmp_path: Path) -> None:
    payload = _build(tmp_path)
    output = write_artifact(payload, tmp_path / "attestation.json")

    assert json.loads(output.read_text(encoding="utf-8")) == payload


def test_build_remains_network_free(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    def forbidden_connection(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "create_connection", forbidden_connection)

    payload = _build(tmp_path)

    assert payload["provider_requests"] == 0
    assert payload["pipeline_mutation"] is False
