from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import re
from typing import Any, Protocol


SCHEMA_VERSION = "jap.connector_work_item.v1"
_ALLOWED_SOURCE_ROLES = {"sensor", "employer_origin"}
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SearchProfileLike(Protocol):
    id: int
    profile_name: str
    source_name: str


def _bounded_text(value: object, *, field: str, maximum: int) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field}_required")
    if len(text) > maximum:
        raise ValueError(f"{field}_too_long")
    return text


def _normalize_scheduled_for(value: datetime | str) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError("scheduled_for_utc_invalid") from exc
    else:
        parsed = value

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("scheduled_for_utc_timezone_required")

    parsed = parsed.astimezone(UTC).replace(microsecond=0)
    return parsed.isoformat().replace("+00:00", "Z")


def deterministic_work_id(
    *,
    pipeline_sha: str,
    profile_id: int,
    source_name: str,
    scheduled_for_utc: str,
) -> str:
    canonical = json.dumps(
        {
            "pipeline_sha": pipeline_sha,
            "profile_id": profile_id,
            "source_name": source_name,
            "scheduled_for_utc": scheduled_for_utc,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True, slots=True)
class ConnectorWorkItem:
    schema_version: str
    work_id: str
    pipeline_sha: str
    profile_id: int
    profile_name: str
    source_name: str
    source_role: str
    scheduled_for_utc: str
    attempt: int = 0

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("connector_work_item_schema_version_changed")
        if _SHA256.fullmatch(self.work_id) is None:
            raise ValueError("work_id_invalid")
        if _SHA40.fullmatch(self.pipeline_sha) is None:
            raise ValueError("pipeline_sha_invalid")
        if self.profile_id < 1:
            raise ValueError("profile_id_invalid")

        profile_name = _bounded_text(
            self.profile_name,
            field="profile_name",
            maximum=256,
        )
        source_name = _bounded_text(
            self.source_name,
            field="source_name",
            maximum=512,
        )
        source_role = _bounded_text(
            self.source_role,
            field="source_role",
            maximum=64,
        )
        if source_role not in _ALLOWED_SOURCE_ROLES:
            raise ValueError("source_role_invalid")
        if not 0 <= self.attempt <= 10:
            raise ValueError("attempt_out_of_bounds")

        scheduled_for_utc = _normalize_scheduled_for(self.scheduled_for_utc)
        expected_work_id = deterministic_work_id(
            pipeline_sha=self.pipeline_sha,
            profile_id=self.profile_id,
            source_name=source_name,
            scheduled_for_utc=scheduled_for_utc,
        )
        if self.work_id != expected_work_id:
            raise ValueError("work_id_binding_mismatch")

        object.__setattr__(self, "profile_name", profile_name)
        object.__setattr__(self, "source_name", source_name)
        object.__setattr__(self, "source_role", source_role)
        object.__setattr__(self, "scheduled_for_utc", scheduled_for_utc)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "work_id": self.work_id,
            "pipeline_sha": self.pipeline_sha,
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "source_name": self.source_name,
            "source_role": self.source_role,
            "scheduled_for_utc": self.scheduled_for_utc,
            "attempt": self.attempt,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ConnectorWorkItem:
        expected = {
            "schema_version",
            "work_id",
            "pipeline_sha",
            "profile_id",
            "profile_name",
            "source_name",
            "source_role",
            "scheduled_for_utc",
            "attempt",
        }
        if set(value) != expected:
            raise ValueError("connector_work_item_fields_changed")
        return cls(
            schema_version=str(value["schema_version"]),
            work_id=str(value["work_id"]),
            pipeline_sha=str(value["pipeline_sha"]),
            profile_id=int(value["profile_id"]),
            profile_name=str(value["profile_name"]),
            source_name=str(value["source_name"]),
            source_role=str(value["source_role"]),
            scheduled_for_utc=str(value["scheduled_for_utc"]),
            attempt=int(value["attempt"]),
        )

    @classmethod
    def from_json(cls, value: str) -> ConnectorWorkItem:
        payload = json.loads(value)
        if not isinstance(payload, dict):
            raise ValueError("connector_work_item_root_not_object")
        return cls.from_dict(payload)


def build_connector_work_item(
    profile: SearchProfileLike,
    *,
    source_role: str,
    pipeline_sha: str,
    scheduled_for: datetime | str,
    attempt: int = 0,
) -> ConnectorWorkItem:
    normalized_sha = pipeline_sha.strip().lower()
    if _SHA40.fullmatch(normalized_sha) is None:
        raise ValueError("pipeline_sha_invalid")
    profile_id = int(profile.id)
    if profile_id < 1:
        raise ValueError("profile_id_invalid")
    profile_name = _bounded_text(
        profile.profile_name,
        field="profile_name",
        maximum=256,
    )
    source_name = _bounded_text(
        profile.source_name,
        field="source_name",
        maximum=512,
    )
    normalized_scheduled_for = _normalize_scheduled_for(scheduled_for)
    work_id = deterministic_work_id(
        pipeline_sha=normalized_sha,
        profile_id=profile_id,
        source_name=source_name,
        scheduled_for_utc=normalized_scheduled_for,
    )
    return ConnectorWorkItem(
        schema_version=SCHEMA_VERSION,
        work_id=work_id,
        pipeline_sha=normalized_sha,
        profile_id=profile_id,
        profile_name=profile_name,
        source_name=source_name,
        source_role=source_role,
        scheduled_for_utc=normalized_scheduled_for,
        attempt=attempt,
    )
