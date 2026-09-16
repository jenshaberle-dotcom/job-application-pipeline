from pathlib import Path


MIGRATION = Path("db/migrations/112_create_authoritative_application_lifecycle.sql")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_f5_application_identity_and_submission_authority_are_separate() -> None:
    sql = _sql()

    assert "CREATE TABLE IF NOT EXISTS applications" in sql
    assert "CREATE TABLE IF NOT EXISTS application_submissions" in sql
    assert "application_id BIGINT NOT NULL UNIQUE" in sql
    assert "'operator_confirmation'" in sql
    assert "'approved_authoritative_record'" in sql
    assert "Presence of an application row or approved draft does not mean submitted" in sql

    applications = sql.split("CREATE TABLE IF NOT EXISTS applications", 1)[1].split(
        "CREATE TABLE IF NOT EXISTS application_submissions", 1
    )[0]
    assert "submitted_at" not in applications
    assert "submission_channel" not in applications


def test_f5_submission_requires_exact_provenance_and_idempotency() -> None:
    sql = _sql()
    submissions = sql.split("CREATE TABLE IF NOT EXISTS application_submissions", 1)[1].split(
        "CREATE TABLE IF NOT EXISTS application_lifecycle_events", 1
    )[0]

    assert "submitted_at TIMESTAMPTZ NOT NULL" in submissions
    assert "submission_channel TEXT NOT NULL" in submissions
    assert "authority_kind TEXT NOT NULL" in submissions
    assert "authority_reference TEXT NOT NULL" in submissions
    assert "confirmed_by TEXT NOT NULL" in submissions
    assert "submission_snapshot JSONB NOT NULL" in submissions
    assert "idempotency_key TEXT NOT NULL UNIQUE" in submissions
    assert "ON DELETE RESTRICT" in submissions


def test_f5_authoritative_events_are_append_only_and_superseding() -> None:
    sql = _sql()
    events = sql.split("CREATE TABLE IF NOT EXISTS application_lifecycle_events", 1)[1].split(
        "CREATE TABLE IF NOT EXISTS application_event_candidates", 1
    )[0]

    assert "supersedes_event_id BIGINT" in events
    assert "REFERENCES application_lifecycle_events(id) ON DELETE RESTRICT" in events
    assert "idempotency_key TEXT NOT NULL UNIQUE" in events
    assert "UPDATE application_lifecycle_events" not in sql
    assert "DELETE FROM application_lifecycle_events" not in sql


def test_f5_communication_candidates_are_evidence_not_authority() -> None:
    sql = _sql()
    candidates = sql.split("CREATE TABLE IF NOT EXISTS application_event_candidates", 1)[1].split(
        "CREATE OR REPLACE VIEW gold_product_v1_application_tracking", 1
    )[0]

    for event_class in (
        "application_acknowledgement",
        "recruiter_contact",
        "interview_invitation",
        "assessment_request",
        "offer_signal",
        "rejection",
        "withdrawal_confirmation",
        "other",
        "ambiguous",
    ):
        assert f"'{event_class}'" in candidates

    assert "source_kind IN ('gmail', 'manual_evidence', 'runtime_evidence')" in candidates
    assert "accepted_as_evidence" in candidates
    assert "cannot establish submission or mutate authoritative application lifecycle state" in sql


def test_f5_tracking_stage_never_uses_candidate_classification_as_authority() -> None:
    sql = _sql()
    view = sql.split("CREATE OR REPLACE VIEW gold_product_v1_application_tracking", 1)[1]
    stage_case = view.split("CASE", 1)[1].split("END AS authoritative_stage", 1)[0]

    assert "submission.id IS NULL THEN 'prepared'" in stage_case
    assert "events.is_closed" in stage_case
    assert "events.has_offer" in stage_case
    assert "events.has_interview" in stage_case
    assert "events.has_reply" in stage_case
    assert "ELSE 'applied'" in stage_case
    assert "candidate_class" not in stage_case
    assert "review_status" not in stage_case


def test_f5_stage_precedence_is_closed_offer_interview_reply_applied() -> None:
    sql = _sql()
    view = sql.split("CREATE OR REPLACE VIEW gold_product_v1_application_tracking", 1)[1]

    closed = view.index("events.is_closed")
    offer = view.index("events.has_offer")
    interview = view.index("events.has_interview")
    reply = view.index("events.has_reply")
    applied = view.index("ELSE 'applied'")
    assert closed < offer < interview < reply < applied


def test_f5_superseded_events_are_excluded_from_current_stage_rollup() -> None:
    sql = _sql()
    active_events = sql.split("WITH active_events AS", 1)[1].split(
        "), event_rollup AS", 1
    )[0]

    assert "replacement.supersedes_event_id = event.id" in active_events
    assert "WHERE NOT EXISTS" in active_events


def test_f5_migration_has_no_automatic_send_submit_or_gmail_execution_path() -> None:
    sql = _sql().lower()

    assert "send_email" not in sql
    assert "smtp" not in sql
    assert "gmail api" not in sql
    assert "requests.post" not in sql
    assert "automatic application-submission path" in sql
    assert "update application_draft_requests" not in sql
