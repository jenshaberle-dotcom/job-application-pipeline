"""Read-only F5 application lifecycle projection for the local Control Center.

The projection consumes only the authoritative schema introduced by migration 112.
Communication evidence candidates can raise operator attention, but they never
advance ``authoritative_stage``. Raw mailbox content and Gmail credentials are not
owned by this public repository.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig


SCHEMA_VERSION = "job_application_pipeline.f5.application_tracking.v1"
TRACKING_VIEW = "gold_product_v1_application_tracking"
STAGES = ("prepared", "applied", "reply", "interview", "offer", "closed")


def _relation_exists(conn: psycopg.Connection[Any], relation_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT to_regclass(%s) IS NOT NULL AS present",
            (f"public.{relation_name}",),
        )
        row = cur.fetchone()
    if isinstance(row, Mapping):
        return bool(row.get("present"))
    return bool(row and row[0])


def _safe_evidence_summary(payload: object) -> dict[str, object]:
    """Expose bounded normalized evidence fields only, never arbitrary raw mail."""

    if not isinstance(payload, Mapping):
        return {}
    allowed = (
        "reason_code",
        "matched_terms",
        "evidence_span",
        "sender_domain",
        "subject_fingerprint",
        "thread_match_reason",
    )
    result: dict[str, object] = {}
    for key in allowed:
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, str):
            result[key] = value[:500]
        elif isinstance(value, (int, float, bool)) or value is None:
            result[key] = value
        elif isinstance(value, (list, tuple)):
            result[key] = [str(item)[:160] for item in value[:12]]
    return result


def build_application_tracking_payload(
    *,
    applications: list[Mapping[str, object]],
    candidates: list[Mapping[str, object]],
    available: bool = True,
) -> dict[str, object]:
    stage_counts = Counter(str(row.get("authoritative_stage") or "prepared") for row in applications)
    candidate_by_application: dict[int, list[dict[str, object]]] = {}
    unmatched_candidates: list[dict[str, object]] = []

    for row in candidates:
        item = {
            "candidate_id": row.get("candidate_id"),
            "matched_application_id": row.get("matched_application_id"),
            "match_status": row.get("match_status"),
            "candidate_class": row.get("candidate_class"),
            "source_kind": row.get("source_kind"),
            "source_thread_reference": row.get("source_thread_reference"),
            "source_message_reference": row.get("source_message_reference"),
            "confidence": row.get("confidence"),
            "ambiguity_reason": row.get("ambiguity_reason"),
            "review_status": row.get("review_status"),
            "created_at": row.get("created_at"),
            "evidence": _safe_evidence_summary(row.get("evidence_payload")),
            "authority": "evidence_only",
        }
        application_id = row.get("matched_application_id")
        if application_id is None:
            unmatched_candidates.append(item)
            continue
        try:
            key = int(application_id)
        except (TypeError, ValueError):
            unmatched_candidates.append(item)
            continue
        candidate_by_application.setdefault(key, []).append(item)

    rows: list[dict[str, object]] = []
    for row in applications:
        application_id = int(row["application_id"])
        stage = str(row.get("authoritative_stage") or "prepared")
        if stage not in STAGES:
            stage = "prepared"
        rows.append(
            {
                "application_id": application_id,
                "application_key": row.get("application_key"),
                "silver_job_id": row.get("silver_job_id"),
                "draft_request_id": row.get("draft_request_id"),
                "title": row.get("title"),
                "company_name": row.get("company_name"),
                "display_company_name": row.get("display_company_name"),
                "source_url": row.get("source_url"),
                "prepared_at": row.get("prepared_at"),
                "prepared_by": row.get("prepared_by"),
                "submission_id": row.get("submission_id"),
                "submitted_at": row.get("submitted_at"),
                "submission_channel": row.get("submission_channel"),
                "submission_authority_kind": row.get("submission_authority_kind"),
                "submission_authority_reference": row.get("submission_authority_reference"),
                "authoritative_stage": stage,
                "authoritative_event_count": int(row.get("authoritative_event_count") or 0),
                "latest_authoritative_event_at": row.get("latest_authoritative_event_at"),
                "attention_candidate_count": int(row.get("attention_candidate_count") or 0),
                "latest_candidate_at": row.get("latest_candidate_at"),
                "attention_status": row.get("attention_status") or "none",
                "evidence_candidates": candidate_by_application.get(application_id, []),
                "stage_authority": "application_submission_and_confirmed_lifecycle_events",
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "available": available,
        "summary": {
            "application_count": len(rows),
            "submitted_count": sum(1 for row in rows if row.get("submission_id") is not None),
            "attention_count": sum(
                1 for row in rows if int(row.get("attention_candidate_count") or 0) > 0
            ),
            "unmatched_candidate_count": len(unmatched_candidates),
            "stage_counts": {stage: int(stage_counts.get(stage, 0)) for stage in STAGES},
        },
        "applications": rows,
        "unmatched_evidence_candidates": unmatched_candidates,
        "boundaries": {
            "read_only_projection": True,
            "communication_candidate_is_not_lifecycle_authority": True,
            "gmail_credentials_present": False,
            "raw_mail_body_exposed": False,
            "email_send_authority": False,
            "automatic_application_submission": False,
        },
    }


def load_application_tracking_payload() -> dict[str, object]:
    """Load the local F5 tracking projection in an explicit read-only transaction."""

    with psycopg.connect(
        DatabaseConfig.from_environment().dsn(), row_factory=dict_row
    ) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        if not _relation_exists(conn, TRACKING_VIEW):
            return build_application_tracking_payload(
                applications=[], candidates=[], available=False
            )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    tracking.*,
                    silver.title,
                    silver.company_name,
                    silver.display_company_name,
                    silver.source_url
                FROM gold_product_v1_application_tracking tracking
                LEFT JOIN silver_jobs silver
                  ON silver.id = tracking.silver_job_id
                ORDER BY
                    coalesce(tracking.submitted_at, tracking.prepared_at) DESC,
                    tracking.application_id DESC
                """
            )
            applications = [dict(row) for row in cur.fetchall()]

            candidates: list[dict[str, object]] = []
            if _relation_exists(conn, "application_event_candidates"):
                cur.execute(
                    """
                    SELECT
                        id AS candidate_id,
                        matched_application_id,
                        match_status,
                        candidate_class,
                        source_kind,
                        source_thread_reference,
                        source_message_reference,
                        confidence,
                        ambiguity_reason,
                        evidence_payload,
                        review_status,
                        created_at
                    FROM application_event_candidates
                    WHERE review_status IN ('unreviewed', 'ambiguous', 'accepted_as_evidence')
                    ORDER BY created_at DESC, id DESC
                    """
                )
                candidates = [dict(row) for row in cur.fetchall()]

    return build_application_tracking_payload(
        applications=applications,
        candidates=candidates,
        available=True,
    )
