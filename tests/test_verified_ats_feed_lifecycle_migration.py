from pathlib import Path


MIGRATION = Path("db/migrations/099_authorize_verified_ats_feed_observations.sql")


def test_migration_099_reads_current_observation_evidence_not_rewritten_bronze() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "observation.normalized_evidence" in sql
    assert "{raw_evidence,ats_feed_authority,authority_validated}" in sql
    assert "{raw_evidence,ats_feed_authority,employer_identity_bound}" in sql
    assert "{raw_evidence,ats_feed_authority,feed_inventory_complete}" in sql
    assert "{raw_evidence,ats_feed_authority,evidence_fingerprint}" in sql
    assert "{raw_evidence,job,source_url}" in sql
    assert "observation.normalized_evidence ->> 'source_url'" in sql
    assert "UPDATE raw_jobs" not in sql
    assert "ALTER TABLE raw_jobs" not in sql


def test_migration_099_is_narrow_to_reviewed_verified_personio_full_feed() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "personio-recurring-feed-authority.v1" in sql
    assert "runtime_203_personio_target_authority_shadow_v1" in sql
    assert "= 'personio'" in sql
    assert "observation.source_name" in sql
    assert "= 'personio:' ||" in sql
    assert "product_authority" in sql
    assert "= 'false'" in sql
    assert "http_status_code" in sql
    assert "BETWEEN 200 AND 399" in sql
    assert "authoritative_verified_ats_feed_observation" in sql
    assert "'complete_inventory'" in sql


def test_migration_099_preserves_existing_direct_and_exact_ats_authority_paths() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "= 'employer_origin_career_site'" in sql
    assert "{acquisition_boundary,detail_pages_fetched}" in sql
    assert "= 'employer_origin_ats_backed_career_site'" in sql
    assert "{detail_evidence,target_employer_verified}" in sql
    assert "{detail_evidence,status_code}" in sql
    assert "authoritative_employer_origin_job_observation" in sql


def test_migration_099_keeps_sensor_and_unreviewed_sources_out_of_new_authority() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "stepstone" not in sql.lower()
    assert "greenhouse" not in sql.lower()
    assert "personio:*" not in sql
    assert "reviewed_binding_contract" in sql
