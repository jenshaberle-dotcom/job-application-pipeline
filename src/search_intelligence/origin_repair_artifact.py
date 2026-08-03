"""Validate and reuse a completed origin-repair artifact without rerunning search."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

SUPPORTED_SCHEMAS = {
    "origin_url_default_repair.v2",
    "origin_url_default_repair.v3",
}


class ArtifactValidationError(ValueError):
    """Raised when a repair artifact cannot be trusted for downstream review."""


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ArtifactValidationError(f"{field} must be an object")
    return value


def _parse_timestamp(value: object) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ArtifactValidationError("generated_at_utc is missing")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ArtifactValidationError("generated_at_utc is invalid") from exc
    if parsed.tzinfo is None:
        raise ArtifactValidationError("generated_at_utc must be timezone-aware")
    return parsed.astimezone(UTC)


def _validated_https_url(value: object) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ArtifactValidationError("selected_url must be an absolute HTTPS URL")
    if parsed.username or parsed.password:
        raise ArtifactValidationError("selected_url must not contain credentials")
    return url


def load_validated_repair_payload(
    path: Path,
    *,
    company_key: str,
    max_age_hours: float = 24.0,
    now: datetime | None = None,
) -> dict[str, object]:
    """Return one selected company payload after strict artifact validation."""

    if max_age_hours <= 0:
        raise ArtifactValidationError("max_age_hours must be positive")
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise ArtifactValidationError(f"cannot read repair artifact: {path}") from exc
    try:
        document = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactValidationError("repair artifact is not valid UTF-8 JSON") from exc
    root = _mapping(document, field="artifact root")

    schema = str(root.get("schema_version") or "")
    if schema not in SUPPORTED_SCHEMAS:
        raise ArtifactValidationError(f"unsupported repair artifact schema: {schema!r}")
    if root.get("review_output_only_not_pipeline_input") is not True:
        raise ArtifactValidationError(
            "artifact must be marked review_output_only_not_pipeline_input"
        )

    generated_at = _parse_timestamp(root.get("generated_at_utc"))
    checked_at = (now or datetime.now(UTC)).astimezone(UTC)
    if generated_at > checked_at + timedelta(minutes=5):
        raise ArtifactValidationError("repair artifact timestamp is in the future")
    if checked_at - generated_at > timedelta(hours=max_age_hours):
        raise ArtifactValidationError(
            f"repair artifact is older than {max_age_hours:g} hours"
        )

    results = root.get("results")
    if not isinstance(results, list):
        raise ArtifactValidationError("artifact results must be an array")
    matches = [
        item
        for item in results
        if isinstance(item, Mapping)
        and str(item.get("company_key") or "") == company_key
    ]
    if len(matches) != 1:
        raise ArtifactValidationError(
            f"artifact must contain exactly one result for company_key={company_key!r}"
        )
    payload = dict(matches[0])
    repair = _mapping(payload.get("default_repair"), field="default_repair")

    final_state = str(repair.get("final_state") or "")
    if not final_state.startswith("selected_"):
        raise ArtifactValidationError(
            f"repair artifact is not selected: final_state={final_state!r}"
        )
    selected_url = _validated_https_url(repair.get("selected_url"))
    if str(payload.get("selected_url") or "") != selected_url:
        raise ArtifactValidationError(
            "top-level selected_url does not match default_repair.selected_url"
        )
    selected_stage = str(repair.get("selected_stage") or "")
    if not selected_stage or final_state != f"selected_{selected_stage}":
        raise ArtifactValidationError("selected stage and final state are inconsistent")
    if repair.get("operator_review_required") is True:
        raise ArtifactValidationError("selected artifact still requires operator review")
    if repair.get("repair_exhausted") is True:
        raise ArtifactValidationError("selected artifact cannot also be repair_exhausted")
    if repair.get("configuration_blocked") is True:
        raise ArtifactValidationError("selected artifact cannot be configuration_blocked")

    boundary = _mapping(repair.get("boundary"), field="default_repair.boundary")
    forbidden_true = (
        "candidate_url_write",
        "connector_registration",
        "source_activation",
        "bronze_silver_write",
        "scheduler_change",
    )
    for field in forbidden_true:
        if boundary.get(field) is not False:
            raise ArtifactValidationError(
                f"artifact boundary does not prove {field}=false"
            )

    adaptive = payload.get("adaptive_search")
    if isinstance(adaptive, Mapping) and adaptive.get("repeated_state_detected") is True:
        raise ArtifactValidationError("artifact reports a repeated discovery state")

    payload["artifact_reuse"] = {
        "validated": True,
        "artifact_path": str(path.resolve()),
        "artifact_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "schema_version": schema,
        "generated_at_utc": generated_at.isoformat(),
        "validated_at_utc": checked_at.isoformat(),
        "max_age_hours": max_age_hours,
        "company_key": company_key,
        "selected_url": selected_url,
        "selected_stage": selected_stage,
        "provider_rerun": False,
    }
    return payload


__all__ = [
    "ArtifactValidationError",
    "SUPPORTED_SCHEMAS",
    "load_validated_repair_payload",
]
