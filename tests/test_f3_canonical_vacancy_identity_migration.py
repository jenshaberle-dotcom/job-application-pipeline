from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db" / "migrations" / "109_create_canonical_vacancy_identity_truth.sql"


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_identity_projection_is_append_only_and_keeps_members_auditable() -> None:
    sql = _sql()
    assert "CREATE OR REPLACE VIEW gold_vacancy_identity AS" in sql
    assert "identity_group_size" in sql
    assert "is_representative" in sql
    assert "silver_jobs and gold_vacancy_identity" in sql
    upper = sql.upper()
    assert "DELETE FROM" not in upper
    assert "UPDATE SILVER_JOBS" not in upper
    assert "UPDATE RAW_JOBS" not in upper


def test_strong_identity_requires_origin_host_and_strong_identifier_evidence() -> None:
    sql = _sql()
    assert "('schema_org', 'explicit_label')" in sql
    assert "structured_identifier" in sql
    assert "origin_host" in sql
    assert "strong_origin_identifier" in sql
    assert "origin-id|' || evidence.origin_host" in sql
    assert "~ '[0-9]'" in sql
    assert "~ '^[A-Za-z0-9._/-]+$'" in sql


def test_bounded_equivalence_is_same_run_multi_signal_not_locale_stripping() -> None:
    sql = _sql()
    assert "source_name LIKE 'generic_origin:%'" in sql
    assert "ingestion_run_id IS NOT NULL" in sql
    assert "semantic_evidence_fingerprint IS NOT NULL" in sql
    assert "locale_neutral_origin_path IS NOT NULL" in sql
    assert "count(DISTINCT exact_observed_origin_url) > 1" in sql
    assert "count(DISTINCT strong_identifier) <= 1" in sql
    assert "bounded_same_run_detail_equivalence" in sql
    for field in (
        "description",
        "locations",
        "applicant_locations",
        "skills",
        "workplace_type",
        "employment_types",
        "date_posted",
        "valid_through",
    ):
        assert f"'{field}'" in sql


def test_identity_contract_never_uses_fuzzy_title_or_company_matching() -> None:
    sql = _sql().casefold()
    assert "similarity(" not in sql
    assert "levenshtein" not in sql
    assert "soundex" not in sql
    assert "title/company fuzzy" in sql


def test_canonical_gold_views_consume_identity_representative_upstream() -> None:
    sql = _sql()
    current_start = sql.index("CREATE OR REPLACE VIEW gold_current_job_opportunities AS")
    readiness_start = sql.index("CREATE OR REPLACE VIEW gold_product_v1_job_readiness AS")
    current = sql[current_start:readiness_start]
    readiness = sql[readiness_start:]
    assert "JOIN gold_vacancy_identity identity" in current
    assert "identity.is_representative" in current
    assert "JOIN gold_vacancy_identity identity" in readiness
    assert "identity.is_representative" in readiness
    assert "Preserve the Product V1 readiness column contract" in sql


def test_representative_prefers_current_lifecycle_without_deleting_history() -> None:
    sql = _sql()
    assert "WHEN 'active_confirmed' THEN 0" in sql
    assert "WHEN 'inactive_confirmed' THEN 3" in sql
    assert "latest_seen_at DESC NULLS LAST" in sql
    assert "silver_job_id" in sql
