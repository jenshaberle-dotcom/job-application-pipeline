"""Read-only F5 mailbox-first application lifecycle projection.

Applications may be discovered from mailbox evidence even when JAP has never seen
that job. ``authoritative_stage`` remains audit/correction truth; ``observed_stage``
is the automatically tracked mailbox state derived by the DB view from exact,
deterministic, high-confidence evidence. Raw mailbox content and Gmail credentials
remain outside this public repository.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig


SCHEMA_VERSION = "job_application_pipeline.f5.application_tracking.v2"
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


def _column_exists(
    conn: psycopg.Connection[Any], relation_name: str, column_name: str
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                  AND column_name = %s
            ) AS present
            """,
            (relation_name, column_name),
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


def _snapshot_text(snapshot: object, *keys: str) -> str | None:
    if not isinstance(snapshot, Mapping):
        return None
    for key in keys:
        value = snapshot.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _stage(value: object, *, fallback: str = "prepared") -> str:
    text = str(value or "").strip()
    return text if text in STAGES else fallback


def build_application_tracking_payload(
    *,
    applications: list[Mapping[str, object]],
    candidates: list[Mapping[str, object]],
    available: bool = True,
) -> dict[str, object]:
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
            "observed_at": row.get("observed_at") or row.get("created_at"),
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
    stage_counts: Counter[str] = Counter()
    mailbox_discovered_count = 0
    observed_count = 0

    for row in applications:
        application_id = int(row["application_id"])
        authoritative_stage = _stage(row.get("authoritative_stage"))
        observed_raw = row.get("observed_stage")
        observed_stage = _stage(observed_raw) if observed_raw else None
        effective_stage = _stage(
            row.get("effective_stage"),
            fallback=observed_stage or authoritative_stage,
        )
        stage_counts[effective_stage] += 1

        discovery_kind = str(row.get("discovery_kind") or "jap_prepared")
        if discovery_kind == "mailbox_observed":
            mailbox_discovered_count += 1
        if observed_stage is not None:
            observed_count += 1

        snapshot = row.get("job_identity_snapshot")
        silver_job_id = row.get("silver_job_id")
        title = row.get("title") or _snapshot_text(snapshot, "title", "job_title", "position")
        company_name = row.get("company_name") or _snapshot_text(
            snapshot, "company_name", "employer_name", "company"
        )
        display_company_name = row.get("display_company_name") or company_name
        source_url = row.get("source_url") or _snapshot_text(
            snapshot, "source_url", "job_url", "application_url"
        )

        rows.append(
            {
                "application_id": application_id,
                "application_key": row.get("application_key"),
                "silver_job_id": silver_job_id,
                "job_link_status": "linked" if silver_job_id is not None else "external",
                "draft_request_id": row.get("draft_request_id"),
                "discovery_kind": discovery_kind,
                "discovered_at": row.get("discovered_at") or row.get("prepared_at"),
                "title": title,
                "company_name": company_name,
                "display_company_name": display_company_name,
                "source_url": source_url,
                "prepared_at": row.get("prepared_at"),
                "prepared_by": row.get("prepared_by"),
                "submission_id": row.get("submission_id"),
                "submitted_at": row.get("submitted_at"),
                "submission_channel": row.get("submission_channel"),
                "submission_authority_kind": row.get("submission_authority_kind"),
                "submission_authority_reference": row.get("submission_authority_reference"),
                "authoritative_stage": authoritative_stage,
                "observed_stage": observed_stage,
                "observed_event_class": row.get("observed_event_class"),
                "observed_at": row.get("observed_at"),
                "observed_confidence": row.get("observed_confidence"),
                "effective_stage": effective_stage,
                "effective_stage_basis": row.get("effective_stage_basis")
                or ("mailbox_observed" if observed_stage else "authoritative_fallback"),
                "authoritative_event_count": int(
                    row.get("authoritative_event_count") or 0
                ),
                "latest_authoritative_event_at": row.get(
                    "latest_authoritative_event_at"
                ),
                "attention_candidate_count": int(
                    row.get("attention_candidate_count") or 0
                ),
                "latest_candidate_at": row.get("latest_candidate_at"),
                "attention_status": row.get("attention_status") or "none",
                "evidence_candidates": candidate_by_application.get(application_id, []),
                "stage_authority": (
                    "mailbox_observed_with_separate_authoritative_correction"
                ),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "available": available,
        "summary": {
            "application_count": len(rows),
            "submitted_count": sum(
                1 for row in rows if row.get("submission_id") is not None
            ),
            "mailbox_discovered_count": mailbox_discovered_count,
            "observed_status_count": observed_count,
            "attention_count": sum(
                1
                for row in rows
                if int(row.get("attention_candidate_count") or 0) > 0
            ),
            "unmatched_candidate_count": len(unmatched_candidates),
            "stage_counts": {
                stage: int(stage_counts.get(stage, 0)) for stage in STAGES
            },
        },
        "applications": rows,
        "unmatched_evidence_candidates": unmatched_candidates,
        "boundaries": {
            "read_only_projection": True,
            "mailbox_observed_status_is_separate_from_authoritative_history": True,
            "unknown_job_application_supported": True,
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
                    silver.company_name AS display_company_name,
                    silver.source_url
                FROM gold_product_v1_application_tracking tracking
                LEFT JOIN silver_jobs silver
                  ON silver.id = tracking.silver_job_id
                ORDER BY
                    coalesce(
                        tracking.observed_at,
                        tracking.submitted_at,
                        tracking.discovered_at,
                        tracking.prepared_at
                    ) DESC,
                    tracking.application_id DESC
                """
            )
            applications = [dict(row) for row in cur.fetchall()]

            candidates: list[dict[str, object]] = []
            if _relation_exists(conn, "application_event_candidates"):
                active_filter = (
                    "AND is_active"
                    if _column_exists(conn, "application_event_candidates", "is_active")
                    else ""
                )
                cur.execute(
                    f"""
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
                        observed_at,
                        created_at
                    FROM application_event_candidates
                    WHERE review_status IN (
                        'unreviewed', 'ambiguous', 'accepted_as_evidence'
                    )
                    {active_filter}
                    ORDER BY observed_at DESC, id DESC
                    """
                )
                candidates = [dict(row) for row in cur.fetchall()]

    return build_application_tracking_payload(
        applications=applications,
        candidates=candidates,
        available=True,
    )
