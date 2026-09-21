"""Explicit local operator actions for F5 application tracking.

This module records truth the operator says already happened. It never submits an
application to an employer and has no network, browser, provider, or email action.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
import hashlib
import json
from typing import Mapping
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig


ALLOWED_SUBMISSION_CHANNELS = frozenset(
    {"employer_portal", "email", "external_platform", "manual_other"}
)
ACTION_NAME = "record_operator_confirmed_submission"
REMOVE_ACTION_NAME = "remove_operator_submission_confirmation"
CORRECT_TITLE_ACTION_NAME = "correct_application_job_title"
LOCAL_OPERATOR_AUTHORITY_REFERENCE = "operator_confirmation:local_ui"


class ApplicationActionError(RuntimeError):
    """Fail-closed operator-action validation error."""


@dataclass(frozen=True)
class SubmissionRemovalRequest:
    application_id: int
    confirmed_by: str = "local_operator"


@dataclass(frozen=True)
class ApplicationTitleCorrectionRequest:
    application_id: int
    job_title: str
    expected_employer_name: str
    confirmed_by: str = "local_operator"


@dataclass(frozen=True)
class SubmissionRecordRequest:
    silver_job_id: int | None
    submitted_at: datetime
    submission_channel: str
    authority_reference: str
    employer_name: str | None = None
    job_title: str | None = None
    source_url: str | None = None
    submitted_precision: str = "datetime"
    confirmed_by: str = "local_operator"
    operator_reference: str | None = None

    @property
    def is_external_job(self) -> bool:
        return self.silver_job_id is None


def _bounded_text(
    value: object,
    *,
    name: str,
    limit: int,
    required: bool = False,
) -> str | None:
    text = str(value or "").strip()
    if not text:
        if required:
            raise ApplicationActionError(f"{name}_required")
        return None
    if len(text) > limit:
        raise ApplicationActionError(f"{name}_too_long")
    return text


def _normalize_url(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise ApplicationActionError("invalid_source_url") from exc
    if parts.scheme.casefold() not in {"http", "https"} or not parts.netloc:
        raise ApplicationActionError("invalid_source_url")
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            parts.path or "/",
            parts.query,
            "",
        )
    )


def _parse_submission_time(payload: Mapping[str, object]) -> tuple[datetime, str]:
    submitted_on = str(payload.get("submitted_on") or "").strip()
    submitted_at_raw = str(payload.get("submitted_at") or "").strip()

    if submitted_on:
        if submitted_at_raw:
            raise ApplicationActionError("submission_date_and_time_are_mutually_exclusive")
        try:
            submitted_date = date.fromisoformat(submitted_on)
        except ValueError as exc:
            raise ApplicationActionError("invalid_submitted_on") from exc
        if submitted_date > datetime.now(timezone.utc).date():
            raise ApplicationActionError("submitted_on_in_future")
        return (
            datetime.combine(submitted_date, time(hour=12), tzinfo=timezone.utc),
            "date",
        )

    if not submitted_at_raw:
        raise ApplicationActionError("submitted_on_required")
    try:
        submitted_at = datetime.fromisoformat(submitted_at_raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApplicationActionError("invalid_submitted_at") from exc
    if submitted_at.tzinfo is None:
        raise ApplicationActionError("submitted_at_timezone_required")
    submitted_at = submitted_at.astimezone(timezone.utc)
    if submitted_at > datetime.now(timezone.utc):
        raise ApplicationActionError("submitted_at_in_future")
    return submitted_at, "datetime"


def parse_submission_record_request(
    payload: Mapping[str, object],
) -> SubmissionRecordRequest | SubmissionRemovalRequest | ApplicationTitleCorrectionRequest:
    action = str(payload.get("action") or "")
    if action == REMOVE_ACTION_NAME:
        return parse_submission_removal_request(payload)
    if action == CORRECT_TITLE_ACTION_NAME:
        return parse_application_title_correction_request(payload)
    if action != ACTION_NAME:
        raise ApplicationActionError("unsupported_application_action")

    raw_silver_job_id = payload.get("silver_job_id")
    silver_job_id: int | None
    if raw_silver_job_id in (None, ""):
        silver_job_id = None
    else:
        try:
            silver_job_id = int(raw_silver_job_id)
        except (TypeError, ValueError) as exc:
            raise ApplicationActionError("invalid_silver_job_id") from exc
        if silver_job_id < 1:
            raise ApplicationActionError("invalid_silver_job_id")

    employer_name = _bounded_text(
        payload.get("employer_name"),
        name="employer_name",
        limit=300,
        required=silver_job_id is None,
    )
    job_title = _bounded_text(
        payload.get("job_title"),
        name="job_title",
        limit=500,
        required=silver_job_id is None,
    )
    source_url = _normalize_url(
        _bounded_text(payload.get("source_url"), name="source_url", limit=1200)
    )

    if silver_job_id is not None and any(
        value is not None for value in (employer_name, job_title, source_url)
    ):
        raise ApplicationActionError("external_identity_not_allowed_for_silver_job")

    submitted_at, submitted_precision = _parse_submission_time(payload)

    channel = str(payload.get("submission_channel") or "").strip()
    if channel not in ALLOWED_SUBMISSION_CHANNELS:
        raise ApplicationActionError("invalid_submission_channel")

    operator_reference = _bounded_text(
        payload.get("authority_reference"),
        name="authority_reference",
        limit=240,
    )
    authority_reference = LOCAL_OPERATOR_AUTHORITY_REFERENCE

    confirmed_by = str(payload.get("confirmed_by") or "local_operator").strip()
    if confirmed_by != "local_operator":
        raise ApplicationActionError("confirmed_by_must_be_local_operator")

    return SubmissionRecordRequest(
        silver_job_id=silver_job_id,
        employer_name=employer_name,
        job_title=job_title,
        source_url=source_url,
        submitted_at=submitted_at,
        submitted_precision=submitted_precision,
        submission_channel=channel,
        authority_reference=authority_reference,
        confirmed_by=confirmed_by,
        operator_reference=operator_reference,
    )


def parse_submission_removal_request(
    payload: Mapping[str, object],
) -> SubmissionRemovalRequest:
    if str(payload.get("action") or "") != REMOVE_ACTION_NAME:
        raise ApplicationActionError("unsupported_application_action")
    if set(payload) - {"action", "application_id", "confirmed_by"}:
        raise ApplicationActionError("unexpected_application_removal_fields")
    try:
        application_id = int(payload.get("application_id") or 0)
    except (TypeError, ValueError) as exc:
        raise ApplicationActionError("invalid_application_id") from exc
    if application_id < 1:
        raise ApplicationActionError("invalid_application_id")
    confirmed_by = str(payload.get("confirmed_by") or "local_operator").strip()
    if confirmed_by != "local_operator":
        raise ApplicationActionError("confirmed_by_must_be_local_operator")
    return SubmissionRemovalRequest(
        application_id=application_id,
        confirmed_by=confirmed_by,
    )


def parse_application_title_correction_request(
    payload: Mapping[str, object],
) -> ApplicationTitleCorrectionRequest:
    if str(payload.get("action") or "") != CORRECT_TITLE_ACTION_NAME:
        raise ApplicationActionError("unsupported_application_action")
    if set(payload) - {
        "action",
        "application_id",
        "job_title",
        "expected_employer_name",
        "confirmed_by",
    }:
        raise ApplicationActionError("unexpected_application_title_correction_fields")
    try:
        application_id = int(payload.get("application_id") or 0)
    except (TypeError, ValueError) as exc:
        raise ApplicationActionError("invalid_application_id") from exc
    if application_id < 1:
        raise ApplicationActionError("invalid_application_id")
    job_title = _bounded_text(
        payload.get("job_title"),
        name="job_title",
        limit=500,
        required=True,
    )
    expected_employer_name = _bounded_text(
        payload.get("expected_employer_name"),
        name="expected_employer_name",
        limit=300,
        required=True,
    )
    confirmed_by = str(payload.get("confirmed_by") or "local_operator").strip()
    if confirmed_by != "local_operator":
        raise ApplicationActionError("confirmed_by_must_be_local_operator")
    return ApplicationTitleCorrectionRequest(
        application_id=application_id,
        job_title=str(job_title),
        expected_employer_name=str(expected_employer_name),
        confirmed_by=confirmed_by,
    )


def _normalized_identity_text(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def build_job_identity_snapshot(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "silver_job_id": int(row["id"]),
        "source_name": row.get("source_name"),
        "external_job_id": row.get("external_job_id"),
        "source_url": row.get("source_url"),
        "title": row.get("title"),
        "company_name": row.get("company_name"),
        "city": row.get("city"),
        "postal_code": row.get("postal_code"),
        "country": row.get("country"),
        "publication_date": row.get("publication_date"),
        "identity_source": "silver_job",
    }


def build_manual_external_identity_snapshot(
    request: SubmissionRecordRequest,
) -> dict[str, object]:
    if not request.is_external_job or not request.employer_name or not request.job_title:
        raise ApplicationActionError("manual_external_identity_incomplete")
    return {
        "title": request.job_title,
        "company_name": request.employer_name,
        "source_url": request.source_url,
        "identity_source": "manual_operator",
    }


def canonical_sha256(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def application_key_for_job(silver_job_id: int) -> str:
    return f"silver-job:{silver_job_id}"


def application_key_for_manual_external(
    request: SubmissionRecordRequest,
) -> str:
    snapshot = build_manual_external_identity_snapshot(request)
    return "manual-external:" + canonical_sha256(
        {
            "company_name": " ".join(str(snapshot["company_name"]).casefold().split()),
            "job_title": " ".join(str(snapshot["title"]).casefold().split()),
            "source_url": snapshot.get("source_url"),
            "submitted_on": request.submitted_at.date().isoformat(),
        }
    )


def submission_idempotency_key(
    *, application_key: str, request: SubmissionRecordRequest
) -> str:
    identity = {
        "application_key": application_key,
        "submitted_at": request.submitted_at.isoformat(),
        "submitted_precision": request.submitted_precision,
        "submission_channel": request.submission_channel,
        "authority_reference": request.authority_reference,
        "authority_kind": "operator_confirmation",
        "confirmed_by": request.confirmed_by,
    }
    return "operator-submission:" + canonical_sha256(identity)


def _same_submission(
    existing: Mapping[str, object],
    request: SubmissionRecordRequest,
    idempotency_key: str,
) -> bool:
    existing_at = existing.get("submitted_at")
    if isinstance(existing_at, datetime):
        existing_at = existing_at.astimezone(timezone.utc)
    return (
        existing_at == request.submitted_at
        and existing.get("submission_channel") == request.submission_channel
        and existing.get("authority_kind") == "operator_confirmation"
        and existing.get("authority_reference") == request.authority_reference
        and existing.get("confirmed_by") == request.confirmed_by
        and existing.get("idempotency_key") == idempotency_key
    )


def _load_silver_identity(cur: object, silver_job_id: int) -> Mapping[str, object]:
    cur.execute(
        """
        SELECT
            id, source_name, external_job_id, source_url, title, company_name,
            city, postal_code, country, publication_date
        FROM silver_jobs
        WHERE id = %s
        FOR SHARE
        """,
        (silver_job_id,),
    )
    silver = cur.fetchone()
    if silver is None:
        raise ApplicationActionError("silver_job_not_found")
    return silver


def correct_application_job_title(
    request: ApplicationTitleCorrectionRequest,
) -> dict[str, object]:
    """Fill one missing mailbox application title under explicit operator authority.

    This action never links a Silver job and never changes submission/lifecycle/evidence
    truth. It only fills a previously missing title and records the correction in
    application provenance.
    """

    with psycopg.connect(
        DatabaseConfig.from_environment().dsn(), row_factory=dict_row
    ) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        discovery_kind,
                        job_identity_snapshot,
                        job_identity_sha256,
                        provenance
                    FROM applications
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (request.application_id,),
                )
                application = cur.fetchone()
                if application is None:
                    raise ApplicationActionError("application_not_found")
                if application.get("discovery_kind") != "mailbox_observed":
                    raise ApplicationActionError(
                        "title_correction_requires_mailbox_observed_application"
                    )

                snapshot = application.get("job_identity_snapshot")
                if not isinstance(snapshot, Mapping):
                    raise ApplicationActionError("application_identity_snapshot_invalid")
                current_snapshot = dict(snapshot)
                employer = (
                    current_snapshot.get("employer_name")
                    or current_snapshot.get("company_name")
                    or current_snapshot.get("company")
                )
                if _normalized_identity_text(employer) != _normalized_identity_text(
                    request.expected_employer_name
                ):
                    raise ApplicationActionError("application_employer_mismatch")

                existing_title = (
                    current_snapshot.get("job_title")
                    or current_snapshot.get("title")
                    or current_snapshot.get("position")
                )
                if str(existing_title or "").strip():
                    if _normalized_identity_text(existing_title) == _normalized_identity_text(
                        request.job_title
                    ):
                        return {
                            "status": "already_correct",
                            "application_id": request.application_id,
                            "job_title": str(existing_title).strip(),
                            "database_writes": 0,
                            "authoritative_lifecycle_mutations": 0,
                            "external_submission_action": False,
                        }
                    raise ApplicationActionError("application_job_title_already_present")

                new_snapshot = dict(current_snapshot)
                new_snapshot["job_title"] = request.job_title
                new_sha = canonical_sha256(new_snapshot)

                provenance = application.get("provenance")
                provenance_map = dict(provenance) if isinstance(provenance, Mapping) else {}
                history_raw = provenance_map.get("identity_corrections")
                history = list(history_raw) if isinstance(history_raw, list) else []
                history.append(
                    {
                        "field": "job_title",
                        "authority": "explicit_operator_confirmation",
                        "confirmed_by": request.confirmed_by,
                        "previous_job_identity_sha256": application.get(
                            "job_identity_sha256"
                        ),
                        "new_job_identity_sha256": new_sha,
                        "new_value": request.job_title,
                        "recorded_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                provenance_map["identity_corrections"] = history

                cur.execute(
                    """
                    UPDATE applications
                    SET
                        job_identity_snapshot = %s,
                        job_identity_sha256 = %s,
                        provenance = %s
                    WHERE id = %s
                    """,
                    (
                        json.dumps(new_snapshot, ensure_ascii=False),
                        new_sha,
                        json.dumps(provenance_map, ensure_ascii=False),
                        request.application_id,
                    ),
                )
                if cur.rowcount != 1:
                    raise ApplicationActionError("application_title_correction_failed")

    return {
        "status": "corrected",
        "application_id": request.application_id,
        "job_title": request.job_title,
        "database_writes": 1,
        "authoritative_lifecycle_mutations": 0,
        "external_submission_action": False,
    }


def remove_operator_submission_confirmation(
    request: SubmissionRemovalRequest,
) -> dict[str, object]:
    """Undo a mistaken local operator submission without deleting external truth.

    The operator-owned submission row may be removed only while no authoritative
    lifecycle event depends on it. The application identity itself is deleted
    only when that identity was created by this same local manual action and no
    communication evidence is attached. Mailbox/evidence truth is never deleted.
    """

    with psycopg.connect(
        DatabaseConfig.from_environment().dsn(), row_factory=dict_row
    ) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        application.id,
                        application.discovery_kind,
                        application.provenance,
                        submission.id AS submission_id,
                        submission.authority_kind,
                        submission.confirmed_by
                    FROM applications application
                    LEFT JOIN application_submissions submission
                      ON submission.application_id = application.id
                    WHERE application.id = %s
                    FOR UPDATE OF application
                    """,
                    (request.application_id,),
                )
                application = cur.fetchone()
                if application is None:
                    return {
                        "status": "already_removed",
                        "application_id": request.application_id,
                        "submission_removed": False,
                        "application_deleted": False,
                        "candidate_evidence_retained": 0,
                        "authoritative_lifecycle_mutations": 0,
                    }

                submission_id = application.get("submission_id")
                if submission_id is None:
                    raise ApplicationActionError(
                        "operator_submission_confirmation_not_present"
                    )
                if application.get("authority_kind") != "operator_confirmation":
                    raise ApplicationActionError(
                        "submission_not_operator_confirmation"
                    )
                if application.get("confirmed_by") != request.confirmed_by:
                    raise ApplicationActionError(
                        "submission_confirmation_owner_mismatch"
                    )

                cur.execute(
                    """
                    SELECT count(*)::integer AS count
                    FROM application_lifecycle_events
                    WHERE submission_id = %s
                    """,
                    (submission_id,),
                )
                lifecycle_count = int(cur.fetchone()["count"])
                if lifecycle_count:
                    raise ApplicationActionError(
                        "authoritative_lifecycle_history_present"
                    )

                cur.execute(
                    """
                    SELECT count(*)::integer AS count
                    FROM application_event_candidates
                    WHERE matched_application_id = %s
                    """,
                    (request.application_id,),
                )
                candidate_count = int(cur.fetchone()["count"])

                provenance = application.get("provenance")
                provenance_map = provenance if isinstance(provenance, Mapping) else {}
                manual_identity_owned = (
                    provenance_map.get("action") == ACTION_NAME
                    and provenance_map.get("recorded_locally") is True
                )

                cur.execute(
                    "DELETE FROM application_submissions WHERE id = %s",
                    (submission_id,),
                )
                submission_removed = cur.rowcount == 1
                if not submission_removed:
                    raise ApplicationActionError(
                        "operator_submission_removal_failed"
                    )

                application_deleted = False
                if manual_identity_owned and candidate_count == 0:
                    cur.execute(
                        "DELETE FROM applications WHERE id = %s",
                        (request.application_id,),
                    )
                    application_deleted = cur.rowcount == 1
                    if not application_deleted:
                        raise ApplicationActionError(
                            "manual_application_identity_removal_failed"
                        )

    return {
        "status": (
            "removed"
            if application_deleted
            else "submission_removed_application_retained"
        ),
        "application_id": request.application_id,
        "submission_removed": True,
        "application_deleted": application_deleted,
        "candidate_evidence_retained": candidate_count,
        "authoritative_lifecycle_mutations": 0,
        "external_submission_action": False,
    }


def record_operator_confirmed_submission(
    request: SubmissionRecordRequest
    | SubmissionRemovalRequest
    | ApplicationTitleCorrectionRequest,
) -> dict[str, object]:
    """Apply one bounded local operator application action.

    The legacy public entrypoint name remains stable so the Control Center HTTP
    surface does not need a second write path.
    """

    if isinstance(request, SubmissionRemovalRequest):
        return remove_operator_submission_confirmation(request)
    if isinstance(request, ApplicationTitleCorrectionRequest):
        return correct_application_job_title(request)

    with psycopg.connect(
        DatabaseConfig.from_environment().dsn(), row_factory=dict_row
    ) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                if request.silver_job_id is not None:
                    silver = _load_silver_identity(cur, request.silver_job_id)
                    snapshot = build_job_identity_snapshot(silver)
                    application_key = application_key_for_job(request.silver_job_id)
                    discovery_kind = "jap_prepared"

                    cur.execute(
                        """
                        SELECT id
                        FROM application_draft_requests
                        WHERE silver_job_id = %s
                          AND status = 'approved_by_operator'
                        ORDER BY updated_at DESC, id DESC
                        LIMIT 1
                        """,
                        (request.silver_job_id,),
                    )
                    draft = cur.fetchone()
                    draft_request_id = int(draft["id"]) if draft else None
                else:
                    snapshot = build_manual_external_identity_snapshot(request)
                    application_key = application_key_for_manual_external(request)
                    discovery_kind = "manual_external"
                    draft_request_id = None

                snapshot_sha = canonical_sha256(snapshot)
                provenance = {
                    "authority": "explicit_operator_confirmation",
                    "action": ACTION_NAME,
                    "recorded_locally": True,
                    "external_submission_action": False,
                    "submitted_precision": request.submitted_precision,
                    "manual_external_job": request.is_external_job,
                    "operator_reference_present": request.operator_reference is not None,
                }

                cur.execute(
                    """
                    INSERT INTO applications (
                        application_key,
                        silver_job_id,
                        draft_request_id,
                        discovery_kind,
                        discovered_at,
                        prepared_at,
                        prepared_by,
                        job_identity_snapshot,
                        job_identity_sha256,
                        provenance
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb)
                    ON CONFLICT (application_key) DO NOTHING
                    RETURNING id
                    """,
                    (
                        application_key,
                        request.silver_job_id,
                        draft_request_id,
                        discovery_kind,
                        request.submitted_at,
                        request.submitted_at,
                        request.confirmed_by,
                        json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
                        snapshot_sha,
                        json.dumps(provenance, ensure_ascii=False, sort_keys=True),
                    ),
                )
                inserted = cur.fetchone()

                cur.execute(
                    """
                    SELECT id, silver_job_id, job_identity_sha256, discovery_kind
                    FROM applications
                    WHERE application_key = %s
                    FOR UPDATE
                    """,
                    (application_key,),
                )
                application = cur.fetchone()
                if application is None:
                    raise ApplicationActionError("application_record_missing_after_insert")
                if request.silver_job_id is None:
                    if application["silver_job_id"] is not None:
                        raise ApplicationActionError("application_identity_conflict")
                elif int(application["silver_job_id"]) != request.silver_job_id:
                    raise ApplicationActionError("application_identity_conflict")
                if application["job_identity_sha256"] != snapshot_sha:
                    raise ApplicationActionError("application_job_identity_changed")
                if str(application["discovery_kind"]) != discovery_kind:
                    raise ApplicationActionError("application_discovery_kind_changed")

                application_id = int(application["id"])
                idempotency_key = submission_idempotency_key(
                    application_key=application_key,
                    request=request,
                )
                submission_snapshot = {
                    "silver_job_id": request.silver_job_id,
                    "job_identity_sha256": snapshot_sha,
                    "submitted_at": request.submitted_at.isoformat(),
                    "submitted_precision": request.submitted_precision,
                    "submission_channel": request.submission_channel,
                    "authority_reference": request.authority_reference,
                    "operator_reference": request.operator_reference,
                    "authority_kind": "operator_confirmation",
                }

                cur.execute(
                    """
                    SELECT
                        id, submitted_at, submission_channel, authority_kind,
                        authority_reference, confirmed_by, idempotency_key
                    FROM application_submissions
                    WHERE application_id = %s
                    FOR UPDATE
                    """,
                    (application_id,),
                )
                existing = cur.fetchone()
                if existing is not None:
                    if not _same_submission(existing, request, idempotency_key):
                        raise ApplicationActionError("application_submission_already_recorded")
                    return {
                        "status": "already_recorded",
                        "application_id": application_id,
                        "submission_id": int(existing["id"]),
                        "silver_job_id": request.silver_job_id,
                        "discovery_kind": discovery_kind,
                        "authoritative_stage": "applied",
                        "external_submission_action": False,
                    }

                cur.execute(
                    """
                    INSERT INTO application_submissions (
                        application_id,
                        submitted_at,
                        submission_channel,
                        authority_kind,
                        authority_reference,
                        confirmed_by,
                        submission_snapshot,
                        idempotency_key
                    )
                    VALUES (%s, %s, %s, 'operator_confirmation', %s, %s, %s::jsonb, %s)
                    RETURNING id
                    """,
                    (
                        application_id,
                        request.submitted_at,
                        request.submission_channel,
                        request.authority_reference,
                        request.confirmed_by,
                        json.dumps(
                            submission_snapshot,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        idempotency_key,
                    ),
                )
                submission = cur.fetchone()
                if submission is None:
                    raise ApplicationActionError("submission_insert_failed")

    return {
        "status": "recorded",
        "application_created": inserted is not None,
        "application_id": application_id,
        "submission_id": int(submission["id"]),
        "silver_job_id": request.silver_job_id,
        "discovery_kind": discovery_kind,
        "authoritative_stage": "applied",
        "external_submission_action": False,
    }
