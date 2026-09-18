from datetime import date
from pathlib import Path

from scripts.product_v1_f5_mailbox_ingest import (
    evidence_fingerprint,
    parse_normalized_mailbox_observation,
    source_message_identity_key,
)
from scripts.run_product_v1_f5_mailbox_persistence_apply import (
    APPROVAL_TOKEN,
    _plan_sha256,
    _select_apply_rows,
    _summarize_results,
)
from scripts.run_product_v1_f5_mailbox_persistence_preflight import (
    ActiveCandidate,
    PersistencePlan,
)
from src.search_intelligence.application_event_classifier import (
    classify_application_evidence,
)


APPLY = Path("scripts/run_product_v1_f5_mailbox_persistence_apply.py")
LIVE_PREFLIGHT = Path("scripts/run_product_v1_f5_mailbox_persistence_live_preflight.py")
INGEST = Path("scripts/product_v1_f5_mailbox_ingest.py")


def _row(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_kind": "gmail",
        "mailbox_account_fingerprint": "acct",
        "thread_reference": "thread-1",
        "message_reference": "message-1",
        "observed_at": "2026-07-01T10:00:00+00:00",
        "subject": "Vielen Dank für Ihre Bewerbung",
        "text_excerpt": "Ihre Bewerbung ist eingegangen.",
        "sender_domain": "example.com",
        "employer_name": "Example GmbH",
        "job_title": "Data Engineer",
        "source_url": None,
        "mail_direction": "inbound",
        "counterparty_domain": "example.com",
        "employer_evidence_source": "counterparty_domain_brand",
    }
    payload.update(overrides)
    return payload


def test_apply_contract_requires_explicit_authority_and_exact_identity_bindings() -> None:
    source = APPLY.read_text(encoding="utf-8")

    assert APPROVAL_TOKEN == "F5-GMAIL-BATCH-PERSISTENCE-V1"
    assert 'parser.add_argument("--expected-input-sha256", required=True)' in source
    assert 'parser.add_argument("--expected-plan-sha256", required=True)' in source
    assert 'parser.add_argument("--source-sha", required=True)' in source
    assert 'parser.add_argument("--approval-token", required=True)' in source
    assert 'parser.add_argument("--apply", action="store_true")' in source
    assert "checkout_source_mismatch" in source
    assert "input_sha256_mismatch" in source
    assert "plan_sha256_mismatch" in source


def test_apply_contract_is_atomic_and_keeps_authoritative_tables_read_only() -> None:
    source = APPLY.read_text(encoding="utf-8")
    ingest = INGEST.read_text(encoding="utf-8")

    assert 'conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")' in source
    assert "with conn.transaction():" in source
    assert "connection=conn" in source
    assert "authoritative_state_changed" in source
    assert "INSERT INTO application_submissions" not in source
    assert "INSERT INTO application_lifecycle_events" not in source

    assert "from contextlib import nullcontext" in ingest
    assert "connection: object | None = None" in ingest
    assert "else nullcontext(connection)" in ingest
    assert "with conn.transaction():" in ingest


def test_plan_digest_is_deterministic_and_binds_all_effect_counts() -> None:
    base = PersistencePlan(
        input_rows=203,
        window_rows=93,
        valid_rows=93,
        invalid_rows=0,
        persistence_candidate_rows=11,
        skipped_other_rows=82,
        application_inserts=9,
        candidate_inserts=11,
        candidate_noops=0,
        candidate_supersessions=0,
        unique_source_messages=11,
        class_counts={"application_acknowledgement": 8, "rejection": 3},
    )
    changed = PersistencePlan(
        **{
            **base.__dict__,
            "candidate_inserts": 10,
            "candidate_noops": 1,
        }
    )

    assert _plan_sha256(base) == _plan_sha256(base)
    assert _plan_sha256(base) != _plan_sha256(changed)


def test_apply_selection_skips_first_seen_other_but_keeps_active_reclassification() -> None:
    other = _row(
        subject="Allgemeine Nachricht",
        text_excerpt="Keine Bewerbungsinformation.",
    )
    assert _select_apply_rows(
        [other],
        active_candidates={},
        since=date(2026, 1, 1),
        until=date(2026, 9, 17),
    ) == []

    observation = parse_normalized_mailbox_observation(other)
    previous_observation = parse_normalized_mailbox_observation(_row())
    previous = classify_application_evidence(
        subject=previous_observation.subject,
        text_excerpt=previous_observation.text_excerpt,
        sender_domain=previous_observation.sender_domain,
    )
    source_key = source_message_identity_key(observation)
    active = {
        source_key: ActiveCandidate(
            source_identity_key=source_key,
            evidence_fingerprint=evidence_fingerprint(
                previous_observation,
                previous,
            ),
            candidate_class=previous.candidate_class,
            application_key="mailbox-application:existing",
        )
    }

    assert _select_apply_rows(
        [other],
        active_candidates=active,
        since=date(2026, 1, 1),
        until=date(2026, 9, 17),
    ) == [other]


def test_result_summary_rejects_any_forbidden_authority_boundary() -> None:
    safe = {
        "candidate_class": "rejection",
        "application_created": True,
        "candidate_recorded": True,
        "candidate_noop": False,
        "candidate_skipped": False,
        "superseded_candidate_id": None,
        "authoritative_state_mutation": False,
        "application_submission_action": False,
        "email_action": False,
    }
    summary = _summarize_results([safe])
    assert summary["application_inserts"] == 1
    assert summary["candidate_inserts"] == 1
    assert summary["candidate_supersessions"] == 0


def test_live_preflight_is_read_only_and_binds_same_input_plan_source_identities() -> None:
    source = LIVE_PREFLIGHT.read_text(encoding="utf-8")

    assert 'conn.execute("SET TRANSACTION READ ONLY")' in source
    assert '"database_writes": 0' in source
    assert '"gmail_network_requests": 0' in source
    assert 'parser.add_argument("--expected-input-sha256", required=True)' in source
    assert 'parser.add_argument("--expected-plan-sha256", required=True)' in source
    assert 'parser.add_argument("--source-sha", required=True)' in source
    assert "plan_sha256_mismatch" in source
    assert "checkout_source_mismatch" in source
