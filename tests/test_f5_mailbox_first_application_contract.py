from pathlib import Path


MIGRATION = Path("db/migrations/113_enable_mailbox_first_application_tracking.sql")
QUALIFIER = Path("scripts/run_f5_mailbox_tracking_schema_qualification.py")
WORKFLOW = Path(".github/workflows/f5-application-lifecycle-reconciliation.yml")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_mailbox_discovered_application_does_not_require_known_silver_job() -> None:
    sql = _sql()

    assert "ALTER COLUMN silver_job_id DROP NOT NULL" in sql
    assert "discovery_kind TEXT NOT NULL DEFAULT 'jap_prepared'" in sql
    assert "'mailbox_observed'" in sql
    assert "Optional canonical JAP/Silver job link" in sql


def test_mailbox_observation_time_is_explicit_and_indexed() -> None:
    sql = _sql()

    assert "ADD COLUMN IF NOT EXISTS observed_at TIMESTAMPTZ" in sql
    assert "ALTER COLUMN observed_at SET NOT NULL" in sql
    assert "idx_application_event_candidates_observed" in sql


def test_observed_stage_is_derived_only_from_exact_deterministic_high_confidence_evidence() -> None:
    sql = _sql()
    eligible = sql.split("eligible_observations AS", 1)[1].split(
        "), latest_observation AS", 1
    )[0]

    assert "candidate.match_status = 'exact'" in eligible
    assert "candidate.confidence >= 0.95" in eligible
    assert "LIKE 'deterministic_%'" in eligible
    assert "candidate.review_status IN ('unreviewed', 'accepted_as_evidence')" in eligible
    assert "'ambiguous'" not in eligible


def test_observed_stage_mapping_tracks_mailbox_lifecycle_without_rewriting_authority() -> None:
    sql = _sql()
    eligible = sql.split("eligible_observations AS", 1)[1].split(
        "), latest_observation AS", 1
    )[0]

    for candidate_class, stage in (
        ("application_acknowledgement", "applied"),
        ("recruiter_contact", "reply"),
        ("assessment_request", "reply"),
        ("interview_invitation", "interview"),
        ("offer_signal", "offer"),
        ("rejection", "closed"),
        ("withdrawal_confirmation", "closed"),
    ):
        assert f"WHEN '{candidate_class}' THEN '{stage}'" in eligible

    assert "UPDATE application_lifecycle_events" not in sql
    assert "DELETE FROM application_lifecycle_events" not in sql
    assert "coalesce(observation.observed_stage, base.authoritative_stage) AS effective_stage" in sql


def test_ambiguous_evidence_remains_attention_not_automatic_status() -> None:
    sql = _sql()

    assert "review_status IN ('unreviewed', 'ambiguous')" in sql
    assert "evidence_review_required" in sql
    assert "candidate.match_status = 'exact'" in sql


def test_replace_view_keeps_migration_112_column_prefix_position_stable() -> None:
    sql = _sql()
    base = sql.split("application_base AS", 1)[1].split(
        ")\nSELECT\n    base.*", 1
    )[0]

    old_prefix = (
        "application.id AS application_id",
        "application.application_key",
        "application.silver_job_id",
        "application.draft_request_id",
        "application.prepared_at",
        "application.prepared_by",
        "application.job_identity_snapshot",
        "application.job_identity_sha256",
        "submission.id AS submission_id",
        "submission.submitted_at",
        "submission.submission_channel",
        "submission.authority_kind AS submission_authority_kind",
        "submission.authority_reference AS submission_authority_reference",
        "END AS authoritative_stage",
        "coalesce(events.authoritative_event_count, 0) AS authoritative_event_count",
        "events.latest_authoritative_event_at",
        "coalesce(candidates.attention_candidate_count, 0) AS attention_candidate_count",
        "candidates.latest_candidate_at",
        "END AS attention_status",
    )
    positions = [base.index(fragment) for fragment in old_prefix]
    assert positions == sorted(positions)
    assert base.index("application.discovery_kind") > positions[-1]
    assert base.index("application.discovered_at") > base.index("application.discovery_kind")


def test_mailbox_first_migration_introduces_no_mail_or_submission_side_effect() -> None:
    sql = _sql().lower()

    assert "send_email" not in sql
    assert "smtp" not in sql
    assert "requests.post" not in sql
    assert "insert into application_submissions" not in sql
    assert "no mailbox network access" in sql


def test_steady_state_qualification_measures_rows_without_reopening_migration_gate() -> None:
    qualifier = QUALIFIER.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'choices=("preflight", "postapply", "current")' in qualifier
    assert 'phase="current", require_empty_rows=False' in qualifier
    assert '"row_policy": "must_be_empty" if require_empty_rows else "measure_only"' in qualifier
    assert "default: current" in workflow
    assert "inputs.mode || 'current'" in workflow
    assert "env.MODE == 'current'" in workflow
    assert "--phase current" in workflow
    assert "run_f5_application_tracking_product_proof" in workflow
