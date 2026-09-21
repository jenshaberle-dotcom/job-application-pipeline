"""Bounded normalized-mailbox ingestion for F5 application tracking.

This public module never accesses Gmail. A private runtime bridge may pass only
bounded normalized evidence plus hashed message/thread references. Clear
deterministic application evidence can discover an application even when no JAP
job exists. The write creates application/evidence observation truth only; it does
not create submission authority or authoritative lifecycle events.
"""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Mapping

from src.search_intelligence.application_event_classifier import (
    ClassificationResult,
    classify_application_evidence,
)
from src.search_intelligence.application_identity_matching import (
    ExistingApplicationIdentity,
    match_existing_application_identity,
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
_PERSISTENCE_CLASSES = frozenset(
    {
        "application_acknowledgement",
        "recruiter_contact",
        "interview_invitation",
        "assessment_request",
        "offer_signal",
        "rejection",
        "withdrawal_confirmation",
        "ambiguous",
    }
)
_ALLOWED_MAIL_DIRECTIONS = frozenset({"inbound", "outbound"})
_ALLOWED_GMAIL_SEARCH_SIGNALS = frozenset(
    {
        "rejection",
        "offer_signal",
        "interview_invitation",
        "assessment_request",
        "withdrawal_confirmation",
    }
)
_UNSOLICITED_APPLICATION_SUBJECT = re.compile(
    r"^(?:(?:re|aw|wg|fwd?):\s*)*(?:initiativbewerbung\b|unsolicited\s+application\b)",
    re.I,
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
    mail_direction: str = "inbound"
    counterparty_domain: str | None = None
    employer_evidence_source: str | None = None
    gmail_search_signals: tuple[str, ...] = ()


def _text(value: object, *, limit: int, required: bool = False) -> str | None:
    text = str(value or "").strip()
    if not text:
        if required:
            raise MailboxIngestError("required_text_missing")
        return None
    if len(text) > limit:
        raise MailboxIngestError("bounded_text_too_long")
    return text


def _domain(value: object, *, required: bool = False) -> str | None:
    domain = _text(value, limit=255, required=required)
    if domain is None:
        return None
    normalized = domain.casefold().strip(" .")
    if "@" in normalized or "/" in normalized or " " in normalized or "." not in normalized:
        raise MailboxIngestError("invalid_bounded_domain")
    return normalized


def _gmail_search_signals(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise MailboxIngestError("gmail_search_signals_must_be_list")
    if len(value) > len(_ALLOWED_GMAIL_SEARCH_SIGNALS):
        raise MailboxIngestError("too_many_gmail_search_signals")

    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise MailboxIngestError("invalid_gmail_search_signal")
        signal = item.casefold().strip()
        if signal not in _ALLOWED_GMAIL_SEARCH_SIGNALS:
            raise MailboxIngestError("invalid_gmail_search_signal")
        if signal in result:
            raise MailboxIngestError("duplicate_gmail_search_signal")
        result.append(signal)
    return tuple(result)


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
    forbidden = {
        "raw_body",
        "headers",
        "access_token",
        "to",
        "recipient",
        "recipient_address",
        "from_address",
    }
    if forbidden.intersection(payload):
        raise MailboxIngestError("raw_or_secret_mail_material_forbidden")

    mail_direction = _text(payload.get("mail_direction"), limit=20) or "inbound"
    mail_direction = mail_direction.casefold()
    if mail_direction not in _ALLOWED_MAIL_DIRECTIONS:
        raise MailboxIngestError("invalid_mail_direction")
    counterparty_domain = _domain(
        payload.get("counterparty_domain"), required=mail_direction == "outbound"
    )

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
        sender_domain=_domain(payload.get("sender_domain")),
        employer_name=_text(payload.get("employer_name"), limit=300),
        job_title=_text(payload.get("job_title"), limit=500),
        source_url=_text(payload.get("source_url"), limit=1200),
        mail_direction=mail_direction,
        counterparty_domain=counterparty_domain,
        employer_evidence_source=_text(
            payload.get("employer_evidence_source"), limit=80
        ),
        gmail_search_signals=_gmail_search_signals(
            payload.get("gmail_search_signals")
        ),
    )


def _normalized(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def application_kind_for_observation(
    observation: NormalizedMailboxObservation,
) -> str | None:
    """Return explicit bounded application kind without inventing a vacancy title."""

    subject = " ".join(observation.subject.split())
    if _UNSOLICITED_APPLICATION_SUBJECT.search(subject):
        return "unsolicited"
    return None


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


def source_message_identity_key(observation: NormalizedMailboxObservation) -> str:
    """Return classifier-independent identity for one normalized Gmail message."""

    return "gmail-message:" + canonical_sha256(
        {
            "source_kind": "gmail",
            "mailbox_account_fingerprint": observation.mailbox_account_fingerprint,
            "message_reference": observation.message_reference,
        }
    )


def evidence_fingerprint(
    observation: NormalizedMailboxObservation, classification: ClassificationResult
) -> str:
    """Fingerprint one interpretation of a stable source message."""

    payload: dict[str, object] = {
        "mailbox_account_fingerprint": observation.mailbox_account_fingerprint,
        "message_reference": observation.message_reference,
        "candidate_class": classification.candidate_class,
        "reason_code": classification.reason_code,
    }
    application_kind = application_kind_for_observation(observation)
    if application_kind is not None:
        # Only explicit non-default semantics participate. Ordinary historical
        # message fingerprints therefore remain stable across this hardening.
        payload["application_kind"] = application_kind
    return canonical_sha256(payload)


def should_discover_application(classification: ClassificationResult) -> bool:
    return (
        classification.deterministic
        and classification.candidate_class in _DISCOVERY_CLASSES
        and classification.confidence is not None
        and classification.confidence >= 0.95
        and classification.reason_code.startswith("deterministic_")
    )


def should_persist_candidate(classification: ClassificationResult) -> bool:
    """Persist lifecycle/review evidence; first-seen deterministic noise stays out."""

    return classification.candidate_class in _PERSISTENCE_CLASSES


def _identity_snapshot(observation: NormalizedMailboxObservation) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "job_title": observation.job_title,
        "employer_name": observation.employer_name,
        "sender_domain": observation.sender_domain,
        "mail_direction": observation.mail_direction,
        "counterparty_domain": observation.counterparty_domain,
        "employer_evidence_source": observation.employer_evidence_source,
        "application_url": observation.source_url,
        "identity_source": "gmail_normalized_observation",
    }
    application_kind = application_kind_for_observation(observation)
    if application_kind is not None:
        snapshot["application_kind"] = application_kind
    return snapshot


def _operator_confirmed_application_identities(
    cur: object,
) -> list[ExistingApplicationIdentity]:
    cur.execute(
        """
        SELECT
            application.application_key,
            coalesce(
                silver.company_name,
                application.job_identity_snapshot->>'company_name',
                application.job_identity_snapshot->>'employer_name',
                application.job_identity_snapshot->>'company'
            ) AS employer_name,
            coalesce(
                silver.title,
                application.job_identity_snapshot->>'title',
                application.job_identity_snapshot->>'job_title',
                application.job_identity_snapshot->>'position'
            ) AS job_title,
            coalesce(
                silver.source_url,
                application.job_identity_snapshot->>'source_url',
                application.job_identity_snapshot->>'job_url',
                application.job_identity_snapshot->>'application_url'
            ) AS source_url
        FROM applications application
        JOIN application_submissions submission
          ON submission.application_id = application.id
        LEFT JOIN silver_jobs silver
          ON silver.id = application.silver_job_id
        WHERE application.discovery_kind IN ('jap_prepared', 'manual_external')
          AND submission.authority_kind = 'operator_confirmation'
        ORDER BY application.id
        """
    )
    return [
        ExistingApplicationIdentity(
            application_key=str(row["application_key"]),
            employer_name=(
                str(row["employer_name"]) if row["employer_name"] is not None else None
            ),
            job_title=(
                str(row["job_title"]) if row["job_title"] is not None else None
            ),
            source_url=(
                str(row["source_url"]) if row["source_url"] is not None else None
            ),
        )
        for row in cur.fetchall()
    ]


def _skipped_result(
    *,
    observation: NormalizedMailboxObservation,
    classification: ClassificationResult,
    source_identity_key: str,
) -> dict[str, object]:
    return {
        "application_key": None,
        "application_id": None,
        "application_discovered": False,
        "application_created": False,
        "candidate_recorded": False,
        "candidate_noop": False,
        "candidate_skipped": True,
        "superseded_candidate_id": None,
        "source_identity_key": source_identity_key,
        "candidate_class": classification.candidate_class,
        "confidence": classification.confidence,
        "match_status": "unmatched",
        "observed_at": observation.observed_at.isoformat(),
        "mail_direction": observation.mail_direction,
        "counterparty_domain": observation.counterparty_domain,
        "application_kind": application_kind_for_observation(observation),
        "application_match_basis": existing_application_match_basis,
        "authoritative_state_mutation": False,
        "application_submission_action": False,
        "email_action": False,
    }


def ingest_normalized_mailbox_observation(
    observation: NormalizedMailboxObservation,
    *,
    connection: object | None = None,
) -> dict[str, object]:
    classification = classify_application_evidence(
        subject=observation.subject,
        text_excerpt=observation.text_excerpt,
        sender_domain=observation.sender_domain,
        mail_direction=observation.mail_direction,
        counterparty_domain=observation.counterparty_domain,
        deterministic_event_signals=observation.gmail_search_signals,
    )
    source_identity_key = source_message_identity_key(observation)
    generated_application_key = mailbox_application_key(observation)
    evidence_hash = evidence_fingerprint(observation, classification)

    import psycopg
    from psycopg.rows import dict_row

    from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig

    discovery_allowed = should_discover_application(classification)
    default_persistence_allowed = should_persist_candidate(classification)
    snapshot = _identity_snapshot(observation)
    snapshot_sha = canonical_sha256(snapshot)
    application_created = False
    candidate_noop = False
    superseded_candidate_id: int | None = None
    resolved_application_key: str | None = None
    existing_application_match_basis: str | None = None
    existing_application_match_ambiguous = False

    connection_context = (
        psycopg.connect(
            DatabaseConfig.from_environment().dsn(),
            row_factory=dict_row,
        )
        if connection is None
        else nullcontext(connection)
    )

    with connection_context as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                # Serialize both first-seen and already-seen processing of one source
                # identity. Row locks alone cannot protect the first insert race.
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (source_identity_key,),
                )
                cur.execute(
                    """
                    SELECT
                        candidate.id,
                        candidate.matched_application_id,
                        candidate.match_status,
                        candidate.candidate_class,
                        candidate.evidence_fingerprint,
                        application.application_key AS matched_application_key
                    FROM application_event_candidates candidate
                    LEFT JOIN applications application
                      ON application.id = candidate.matched_application_id
                    WHERE candidate.source_kind = 'gmail'
                      AND candidate.source_identity_key = %s
                      AND candidate.is_active
                    FOR UPDATE OF candidate
                    """,
                    (source_identity_key,),
                )
                active_candidate = cur.fetchone()

                # First-seen `other` is noise and creates no persistent row. If an
                # earlier active interpretation exists, however, record a dismissed
                # `other` tombstone so stale lifecycle evidence becomes inactive.
                if not default_persistence_allowed and active_candidate is None:
                    return _skipped_result(
                        observation=observation,
                        classification=classification,
                        source_identity_key=source_identity_key,
                    )

                application_id: int | None = None
                if (
                    active_candidate is not None
                    and active_candidate["matched_application_id"] is not None
                ):
                    # Reclassification alone must not silently rematch an already
                    # identified source message to another application.
                    application_id = int(active_candidate["matched_application_id"])
                    matched_key = active_candidate["matched_application_key"]
                    if matched_key is None:
                        raise MailboxIngestError("matched_application_key_missing")
                    resolved_application_key = str(matched_key)
                elif discovery_allowed:
                    (
                        matched_application_key,
                        existing_application_match_ambiguous,
                        existing_application_match_basis,
                    ) = match_existing_application_identity(
                        employer_name=observation.employer_name,
                        job_title=observation.job_title,
                        source_url=observation.source_url,
                        applications=_operator_confirmed_application_identities(cur),
                    )

                    if matched_application_key is not None:
                        cur.execute(
                            """
                            SELECT id, application_key
                            FROM applications
                            WHERE application_key = %s
                            FOR SHARE
                            """,
                            (matched_application_key,),
                        )
                        existing_application = cur.fetchone()
                        if existing_application is None:
                            raise MailboxIngestError(
                                "matched_existing_application_missing"
                            )
                        application_id = int(existing_application["id"])
                        resolved_application_key = str(
                            existing_application["application_key"]
                        )
                    elif not existing_application_match_ambiguous:
                        provenance = {
                            "discovery": "mailbox_observed",
                            "mailbox_account_fingerprint": observation.mailbox_account_fingerprint,
                            "thread_reference": observation.thread_reference,
                            "mail_direction": observation.mail_direction,
                            "counterparty_domain": observation.counterparty_domain,
                            "employer_evidence_source": observation.employer_evidence_source,
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
                                generated_application_key,
                                observation.observed_at,
                                json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
                                snapshot_sha,
                                json.dumps(provenance, ensure_ascii=False, sort_keys=True),
                            ),
                        )
                        inserted = cur.fetchone()
                        if inserted is not None:
                            application_id = int(inserted["id"])
                            application_created = True
                        else:
                            cur.execute(
                                "SELECT id FROM applications WHERE application_key = %s FOR SHARE",
                                (generated_application_key,),
                            )
                            existing = cur.fetchone()
                            if existing is None:
                                raise MailboxIngestError(
                                    "application_missing_after_conflict"
                                )
                            application_id = int(existing["id"])
                        resolved_application_key = generated_application_key

                match_status = (
                    "exact"
                    if application_id is not None
                    else "ambiguous"
                    if existing_application_match_ambiguous
                    else "unmatched"
                )
                ambiguity_reason = (
                    None
                    if application_id is not None
                    else (
                        "multiple_existing_application_candidates"
                        if existing_application_match_ambiguous
                        else "classification_ambiguous"
                        if classification.candidate_class == "ambiguous"
                        else "no_safe_application_identity"
                    )
                )

                same_interpretation = (
                    active_candidate is not None
                    and str(active_candidate["candidate_class"])
                    == classification.candidate_class
                    and str(active_candidate["evidence_fingerprint"]) == evidence_hash
                    and active_candidate["matched_application_id"] == application_id
                    and str(active_candidate["match_status"]) == match_status
                )

                candidate = None
                if same_interpretation:
                    candidate_noop = True
                else:
                    if active_candidate is not None:
                        superseded_candidate_id = int(active_candidate["id"])
                        cur.execute(
                            """
                            UPDATE application_event_candidates
                            SET is_active = FALSE
                            WHERE id = %s AND is_active
                            """,
                            (superseded_candidate_id,),
                        )
                        if cur.rowcount != 1:
                            raise MailboxIngestError("active_candidate_supersession_race")

                    evidence_payload = classification.as_payload()
                    application_kind = application_kind_for_observation(observation)
                    if application_kind is not None:
                        evidence_payload["application_kind"] = application_kind
                    evidence_payload.update(
                        {
                            "sender_domain": observation.sender_domain,
                            "mail_direction": observation.mail_direction,
                            "counterparty_domain": observation.counterparty_domain,
                            "employer_evidence_source": observation.employer_evidence_source,
                            "gmail_search_signals": list(observation.gmail_search_signals),
                            "source_identity_key": source_identity_key,
                            "subject_fingerprint": canonical_sha256(
                                {"subject": _normalized(observation.subject)}
                            ),
                            "thread_match_reason": (
                                existing_application_match_basis
                                or (
                                    "mailbox_application_identity"
                                    if application_id is not None
                                    else "not_discovered"
                                )
                            ),
                        }
                    )
                    if classification.candidate_class == "other":
                        review_status = "dismissed"
                    elif (
                        classification.candidate_class == "ambiguous"
                        or application_id is None
                    ):
                        review_status = "ambiguous"
                    else:
                        review_status = "unreviewed"
                    cur.execute(
                        """
                        INSERT INTO application_event_candidates (
                            matched_application_id,
                            match_status,
                            candidate_class,
                            source_kind,
                            source_thread_reference,
                            source_message_reference,
                            source_identity_key,
                            evidence_fingerprint,
                            confidence,
                            ambiguity_reason,
                            evidence_payload,
                            review_status,
                            observed_at,
                            is_active,
                            supersedes_candidate_id
                        )
                        VALUES (%s, %s, %s, 'gmail', %s, %s, %s, %s, %s, %s,
                                %s::jsonb, %s, %s, TRUE, %s)
                        RETURNING id
                        """,
                        (
                            application_id,
                            match_status,
                            classification.candidate_class,
                            observation.thread_reference,
                            observation.message_reference,
                            source_identity_key,
                            evidence_hash,
                            classification.confidence,
                            ambiguity_reason,
                            json.dumps(evidence_payload, ensure_ascii=False, sort_keys=True),
                            review_status,
                            observation.observed_at,
                            superseded_candidate_id,
                        ),
                    )
                    candidate = cur.fetchone()

    return {
        "application_key": resolved_application_key,
        "application_id": application_id,
        "application_discovered": application_id is not None,
        "application_created": application_created,
        "candidate_recorded": candidate is not None,
        "candidate_noop": candidate_noop,
        "candidate_skipped": False,
        "superseded_candidate_id": superseded_candidate_id,
        "source_identity_key": source_identity_key,
        "candidate_class": classification.candidate_class,
        "confidence": classification.confidence,
        "match_status": match_status,
        "observed_at": observation.observed_at.isoformat(),
        "mail_direction": observation.mail_direction,
        "counterparty_domain": observation.counterparty_domain,
        "application_kind": application_kind_for_observation(observation),
        "authoritative_state_mutation": False,
        "application_submission_action": False,
        "email_action": False,
    }
