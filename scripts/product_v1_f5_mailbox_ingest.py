"""Bounded normalized-mailbox ingestion for F5 application tracking.

This public module never accesses Gmail. A private runtime bridge may pass only
bounded normalized evidence plus hashed message/thread references. Clear
deterministic application evidence can discover an application even when no JAP
job exists. The write creates application/evidence observation truth only; it does
not create submission authority or authoritative lifecycle events.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Mapping

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig
from src.search_intelligence.application_event_classifier import (
    ClassificationResult,
    classify_application_evidence,
)


_DISCOVERY_CLASSES = frozenset(
    {
        "application_acknowledgement",
        "interview_invitation",
        "assessment_request",
        "offer_signal",
        "rejection",
        "withdrawal_confirmation",
    }
)


class MailboxIngestError(RuntimeError):
    """Fail closed when normalized mailbox evidence violates the public contract."""


@dataclass(frozen=True)
class NormalizedMailboxObservation:
    mailbox_account_fingerprint: str
    thread_reference: str
    message_reference: str
    observed_at: datetime
    subject: str
    text_excerpt: str
    sender_domain: str | None
    employer_name: str | None
    job_title: str | None
    source_url: str | None


def _text(value: object, *, limit: int, required: bool = False) -> str | None:
    text = str(value or "").strip()
    if not text:
        if required:
            raise MailboxIngestError("required_text_missing")
        return None
    if len(text) > limit:
        raise MailboxIngestError("bounded_text_too_long")
    return text


def _parse_time(value: object) -> datetime:
    raw = _text(value, limit=80, required=True)
    assert raw is not None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MailboxIngestError("invalid_observed_at") from exc
    if parsed.tzinfo is None:
        raise MailboxIngestError("observed_at_timezone_required")
    parsed = parsed.astimezone(timezone.utc)
    if parsed > datetime.now(timezone.utc):
        raise MailboxIngestError("observed_at_in_future")
    return parsed


def parse_normalized_mailbox_observation(
    payload: Mapping[str, object],
) -> NormalizedMailboxObservation:
    if str(payload.get("source_kind") or "") != "gmail":
        raise MailboxIngestError("source_kind_must_be_gmail")
    if "raw_body" in payload or "headers" in payload or "access_token" in payload:
        raise MailboxIngestError("raw_or_secret_mail_material_forbidden")

    return NormalizedMailboxObservation(
        mailbox_account_fingerprint=_text(
            payload.get("mailbox_account_fingerprint"), limit=128, required=True
        ) or "",
        thread_reference=_text(
            payload.get("thread_reference"), limit=160, required=True
        ) or "",
        message_reference=_text(
            payload.get("message_reference"), limit=160, required=True
        ) or "",
        observed_at=_parse_time(payload.get("observed_at")),
        subject=_text(payload.get("subject"), limit=400) or "",
        text_excerpt=_text(payload.get("text_excerpt"), limit=1200) or "",
        sender_domain=_text(payload.get("sender_domain"), limit=255),
        employer_name=_text(payload.get("employer_name"), limit=300),
        job_title=_text(payload.get("job_title"), limit=500),
        source_url=_text(payload.get("source_url"), limit=1200),
    )


def _normalized(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def canonical_sha256(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def mailbox_application_key(observation: NormalizedMailboxObservation) -> str:
    employer = _normalized(observation.employer_name)
    title = _normalized(observation.job_title)
    identity: dict[str, object] = {
        "mailbox_account_fingerprint": observation.mailbox_account_fingerprint,
    }
    if employer and title:
        identity.update({"employer": employer, "title": title})
    else:
        identity["thread_reference"] = observation.thread_reference
    return "mailbox-application:" + canonical_sha256(identity)


def evidence_fingerprint(
    observation: NormalizedMailboxObservation, classification: ClassificationResult
) -> str:
    return canonical_sha256(
        {
            "mailbox_account_fingerprint": observation.mailbox_account_fingerprint,
            "message_reference": observation.message_reference,
            "candidate_class": classification.candidate_class,
            "reason_code": classification.reason_code,
        }
    )


def should_discover_application(classification: ClassificationResult) -> bool:
    return (
        classification.deterministic
        and classification.candidate_class in _DISCOVERY_CLASSES
        and classification.confidence is not None
        and classification.confidence >= 0.95
        and classification.reason_code.startswith("deterministic_")
    )


def _identity_snapshot(observation: NormalizedMailboxObservation) -> dict[str, object]:
    return {
        "job_title": observation.job_title,
        "employer_name": observation.employer_name,
        "sender_domain": observation.sender_domain,
        "application_url": observation.source_url,
        "identity_source": "gmail_normalized_observation",
    }


def ingest_normalized_mailbox_observation(
    observation: NormalizedMailboxObservation,
) -> dict[str, object]:
    classification = classify_application_evidence(
        subject=observation.subject,
        text_excerpt=observation.text_excerpt,
        sender_domain=observation.sender_domain,
    )
    discovery_allowed = should_discover_application(classification)
    application_key = mailbox_application_key(observation)
    evidence_hash = evidence_fingerprint(observation, classification)
    snapshot = _identity_snapshot(observation)
    snapshot_sha = canonical_sha256(snapshot)

    with psycopg.connect(
        DatabaseConfig.from_environment().dsn(), row_factory=dict_row
    ) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                application_id: int | None = None
                if discovery_allowed:
                    provenance = {
                        "discovery": "mailbox_observed",
                        "mailbox_account_fingerprint": observation.mailbox_account_fingerprint,
                        "thread_reference": observation.thread_reference,
                        "email_action": False,
                        "application_submission_action": False,
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
                        VALUES (%s, NULL, NULL, 'mailbox_observed', %s, NULL, NULL,
                                %s::jsonb, %s, %s::jsonb)
                        ON CONFLICT (application_key) DO NOTHING
                        RETURNING id
                        """,
                        (
                            application_key,
                            observation.observed_at,
                            json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
                            snapshot_sha,
                            json.dumps(provenance, ensure_ascii=False, sort_keys=True),
                        ),
                    )
                    inserted = cur.fetchone()
                    if inserted is not None:
                        application_id = int(inserted["id"])
                    else:
                        cur.execute(
                            "SELECT id FROM applications WHERE application_key = %s FOR SHARE",
                            (application_key,),
                        )
                        existing = cur.fetchone()
                        if existing is None:
                            raise MailboxIngestError("application_missing_after_conflict")
                        application_id = int(existing["id"])

                match_status = "exact" if application_id is not None else "unmatched"
                ambiguity_reason = None if application_id is not None else "no_safe_application_identity"
                evidence_payload = classification.as_payload()
                evidence_payload.update(
                    {
                        "sender_domain": observation.sender_domain,
                        "subject_fingerprint": canonical_sha256(
                            {"subject": _normalized(observation.subject)}
                        ),
                        "thread_match_reason": (
                            "mailbox_application_identity"
                            if application_id is not None
                            else "not_discovered"
                        ),
                    }
                )
                cur.execute(
                    """
                    INSERT INTO application_event_candidates (
                        matched_application_id,
                        match_status,
                        candidate_class,
                        source_kind,
                        source_thread_reference,
                        source_message_reference,
                        evidence_fingerprint,
                        confidence,
                        ambiguity_reason,
                        evidence_payload,
                        review_status,
                        observed_at
                    )
                    VALUES (%s, %s, %s, 'gmail', %s, %s, %s, %s, %s,
                            %s::jsonb, %s, %s)
                    ON CONFLICT (source_kind, evidence_fingerprint, candidate_class)
                    DO NOTHING
                    RETURNING id
                    """,
                    (
                        application_id,
                        match_status,
                        classification.candidate_class,
                        observation.thread_reference,
                        observation.message_reference,
                        evidence_hash,
                        classification.confidence,
                        ambiguity_reason,
                        json.dumps(evidence_payload, ensure_ascii=False, sort_keys=True),
                        "unreviewed" if application_id is not None else "ambiguous",
                        observation.observed_at,
                    ),
                )
                candidate = cur.fetchone()

    return {
        "application_key": application_key if application_id is not None else None,
        "application_id": application_id,
        "application_discovered": application_id is not None,
        "candidate_recorded": candidate is not None,
        "candidate_class": classification.candidate_class,
        "confidence": classification.confidence,
        "match_status": match_status,
        "observed_at": observation.observed_at.isoformat(),
        "authoritative_state_mutation": False,
        "application_submission_action": False,
        "email_action": False,
    }
