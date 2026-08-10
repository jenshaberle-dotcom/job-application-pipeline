from pathlib import Path


MIGRATION = Path(
    "db/migrations/092_activate_authoritative_origin_positive_lifecycle.sql"
)
RUNNER = Path("src/ingestion/runner.py")


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_positive_authority_has_explicit_post_rollout_epoch() -> None:
    sql = migration_sql()

    assert "job_lifecycle_authority_epochs" in sql
    assert "authoritative_positive_v1" in sql
    assert "started_at" in sql
    assert "observation.observed_at >= epoch.started_at" in sql
    assert "ON CONFLICT (epoch_key) DO NOTHING" in sql


def test_only_exact_employer_origin_observations_gain_normal_activity_authority() -> None:
    sql = migration_sql()

    assert "raw_job.raw_data ->> 'source_type'" in sql
    assert "'employer_origin_career_site'" in sql
    assert "{acquisition_boundary,detail_pages_fetched}" in sql
    assert "{detail_evidence,status_code}" in sql
    assert "BETWEEN 200 AND 399" in sql
    assert "NULLIF(btrim(observation.source_url), '') IS NOT NULL" in sql
    assert "raw_job.source_name = observation.source_name" in sql


def test_authoritative_positive_reuses_existing_observation_stream_without_duplicate_write() -> None:
    sql = migration_sql()
    runner = RUNNER.read_text(encoding="utf-8")

    assert "FROM job_observations observation" in sql
    assert "INSERT INTO job_health_observations" not in sql
    assert runner.count("self.repository.save_job_observation(") >= 2


def test_historical_or_aggregator_presence_cannot_be_silently_revived() -> None:
    sql = migration_sql().casefold()

    assert "observation.observed_at >= epoch.started_at" in sql
    assert "source_type" in sql
    assert "employer_origin_career_site" in sql
    assert "stepstone" not in sql
    assert "partial_listing" not in sql


def test_newer_explicit_health_evidence_keeps_precedence() -> None:
    sql = migration_sql()

    precedence = (
        "health.raw_job_id IS NULL\n"
        "                    OR authoritative.last_authoritative_positive_at\n"
        "                        > health.observed_at"
    )
    assert precedence in sql
    assert "WHEN health.outcome = 'closed'" in sql
    assert "AND health.coverage = 'exact_detail'" in sql
    assert "WHEN health.outcome = 'not_seen'" in sql
    assert "AND health.coverage = 'complete_inventory'" in sql
    assert "ELSE 'unverifiable'" in sql


def test_normal_origin_sighting_exposes_existing_lifecycle_contract() -> None:
    sql = migration_sql()

    assert "THEN 'seen_active'" in sql
    assert "THEN 'exact_detail'" in sql
    assert "THEN 'active_confirmed'" in sql
    assert "authoritative_employer_origin_job_observation" in sql
    assert "central_job_observation_authority" in sql
    assert "CREATE OR REPLACE VIEW gold_job_lifecycle_health" in sql
    assert "CREATE OR REPLACE VIEW gold_current_job_opportunities" not in sql
