"""Explicit local operator actions for F5 application tracking.

This module records truth the operator says already happened. It never submits an
application to an employer and has no network, browser, provider, or email action.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig


ALLOWED_SUBMISSION_CHANNELS = frozenset(
    {"employer_portal", "email", "external_platform", "manual_other"}
)
ACTION_NAME = "record_operator_confirmed_submission"


class ApplicationActionError(RuntimeError):
    """Fail-closed operator-action validation error."""


@dataclass(frozen=True)
class SubmissionRecordRequest:
    silver_job_id: int
    submitted_at: datetime
    submission_channel: str
    authority_reference: str
    confirmed_by: str = "local_operator"


def parse_submission_record_request(payload: Mapping[str, object]) -> SubmissionRecordRequest:
    if str(payload.get("action") or "") != ACTION_NAME:
        raise ApplicationActionError("unsupported_application_action")

    try:
        silver_job_id = int(payload.get("silver_job_id") or 0)
    except (TypeError, ValueError) as exc:
        raise ApplicationActionError("invalid_silver_job_id") from exc
    if silver_job_id < 1:
        raise ApplicationActionError("invalid_silver_job_id")

    submitted_raw = str(payload.get("submitted_at") or "").strip()
    if not submitted_raw:
        raise ApplicationActionError("submitted_at_required")
    try:
        submitted_at = datetime.fromisoformat(submitted_raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApplicationActionError("invalid_submitted_at") from exc
    if submitted_at.tzinfo is None:
        raise ApplicationActionError("submitted_at_timezone_required")
    submitted_at = submitted_at.astimezone(timezone.utc)
    if submitted_at > datetime.now(timezone.utc):
        raise ApplicationActionError("submitted_at_in_future")

    channel = str(payload.get("submission_channel") or "").strip()
    if channel not in ALLOWED_SUBMISSION_CHANNELS:
        raise ApplicationActionError("invalid_submission_channel")

    authority_reference = str(payload.get("authority_reference") or "").strip()
    if not authority_reference or len(authority_reference) > 240:
        raise ApplicationActionError("invalid_authority_reference")

    confirmed_by = str(payload.get("confirmed_by") or "local_operator").strip()
    if confirmed_by != "local_operator":
        raise ApplicationActionError("confirmed_by_must_be_local_operator")

    return SubmissionRecordRequest(
        silver_job_id=silver_job_id,
        submitted_at=submitted_at,
        submission_channel=channel,
        authority_reference=authority_reference,
        confirmed_by=confirmed_by,
    )


def build_job_identity_snapshot(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "silver_job_id": int(row["id"]),
        "canonical_job_key": row.get("canonical_job_key"),
        "source_system": row.get("source_system"),
        "source_job_id": row.get("source_job_id"),
        "source_url": row.get("source_url"),
        "title": row.get("title"),
        "company_name": row.get("company_name"),
        "company_key": row.get("company_key"),
        "location_raw": row.get("location_raw"),
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


def submission_idempotency_key(
    *, application_key: str, request: SubmissionRecordRequest
) -> str:
    identity = {
        "application_key": application_key,
        "submitted_at": request.submitted_at.isoformat(),
        "submission_channel": request.submission_channel,
        "authority_reference": request.authority_reference,
        "authority_kind": "operator_confirmation",
        "confirmed_by": request.confirmed_by,
    }
    return "operator-submission:" + canonical_sha256(identity)


def _same_submission(
    existing: Mapping[str, object], request: SubmissionRecordRequest, idempotency_key: str
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


def record_operator_confirmed_submission(
    request: SubmissionRecordRequest,
) -> dict[str, object]:
    """Record an already-submitted application after explicit operator confirmation."""

    application_key = application_key_for_job(request.silver_job_id)
    with psycopg.connect(
        DatabaseConfig.from_environment().dsn(), row_factory=dict_row
    ) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id, canonical_job_key, source_system, source_job_id,
                        source_url, title, company_name, company_key, location_raw
                    FROM silver_jobs
                    WHERE id = %s
                    FOR SHARE
                    """,
                    (request.silver_job_id,),
                )
                silver = cur.fetchone()
                if silver is None:
                    raise ApplicationActionError("silver_job_not_found")

                snapshot = build_job_identity_snapshot(silver)
                snapshot_sha = canonical_sha256(snapshot)
                provenance = {
                    "authority": "explicit_operator_confirmation",
                    "action": ACTION_NAME,
                    "recorded_locally": True,
                    "external_submission_action": False,
                }

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

                cur.execute(
                    """
                    INSERT INTO applications (
                        application_key,
                        silver_job_id,
                        draft_request_id,
                        prepared_by,
                        job_identity_snapshot,
                        job_identity_sha256,
                        provenance
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s::jsonb)
                    ON CONFLICT (application_key) DO NOTHING
                    RETURNING id
                    """,
                    (
                        application_key,
                        request.silver_job_id,
                        draft_request_id,
                        request.confirmed_by,
                        json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
                        snapshot_sha,
                        json.dumps(provenance, ensure_ascii=False, sort_keys=True),
                    ),
                )
                inserted = cur.fetchone()

                cur.execute(
                    """
                    SELECT id, silver_job_id, job_identity_sha256
                    FROM applications
                    WHERE application_key = %s
                    FOR UPDATE
                    """,
                    (application_key,),
                )
                application = cur.fetchone()
                if application is None:
                    raise ApplicationActionError("application_record_missing_after_insert")
                if int(application["silver_job_id"]) != request.silver_job_id:
                    raise ApplicationActionError("application_identity_conflict")
                if application["job_identity_sha256"] != snapshot_sha:
                    raise ApplicationActionError("application_job_identity_changed")

                application_id = int(application["id"])
                idempotency_key = submission_idempotency_key(
                    application_key=application_key, request=request
                )
                submission_snapshot = {
                    "silver_job_id": request.silver_job_id,
                    "job_identity_sha256": snapshot_sha,
                    "submitted_at": request.submitted_at.isoformat(),
                    "submission_channel": request.submission_channel,
                    "authority_reference": request.authority_reference,
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
                            submission_snapshot, ensure_ascii=False, sort_keys=True
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
        "authoritative_stage": "applied",
        "external_submission_action": False,
    }
