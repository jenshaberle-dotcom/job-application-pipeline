from pathlib import Path


def test_connector_feasibility_migration_defines_review_tables() -> None:
    migration = Path("db/migrations/044_create_connector_feasibility_reviews.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS connector_feasibility_reviews" in migration
    assert "CREATE TABLE IF NOT EXISTS connector_feasibility_review_items" in migration
    assert "likely_feasible" in migration
    assert "manual_review_required" in migration
    assert "missing_origin_url" in migration
    assert "bronze_persistence_allowed" not in migration


def test_connector_feasibility_migration_has_url_quality_feedback_columns() -> None:
    migration = Path("db/migrations/044_create_connector_feasibility_reviews.sql").read_text(encoding="utf-8")

    assert "url_quality_status" in migration
    assert "url_quality_feedback_code" in migration
    assert "url_repair_candidate_url" in migration
    assert "structural_job_evidence_count" in migration


def test_connector_feasibility_migration_has_structural_evidence_columns() -> None:
    migration = Path("db/migrations/044_create_connector_feasibility_reviews.sql").read_text(encoding="utf-8")

    assert "url_quality_status" in migration
    assert "url_quality_feedback_code" in migration
    assert "url_repair_candidate_url" in migration
    assert "structural_job_evidence_count" in migration
    assert "job_search_page_evidence_count" in migration
    assert "job_detail_candidate_evidence_count" in migration
    assert "career_context_evidence_count" in migration
    assert "rejected_noise_count" in migration
    assert "evidence_classification" in migration

def test_connector_feasibility_url_quality_constraint_is_single_and_complete() -> None:
    migration = Path("db/migrations/044_create_connector_feasibility_reviews.sql").read_text(encoding="utf-8")

    assert migration.count("ADD CONSTRAINT chk_connector_feasibility_url_quality_status") == 1
    assert "DROP CONSTRAINT IF EXISTS chk_connector_feasibility_url_quality_status" in migration
    assert "'structural_without_detail'::text" in migration
    assert "UPDATE connector_feasibility_review_items" in migration
    assert "ALTER COLUMN url_quality_status SET DEFAULT 'not_evaluated'" in migration
    assert "ALTER COLUMN url_quality_status SET NOT NULL" in migration

