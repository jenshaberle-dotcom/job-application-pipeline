from pathlib import Path


MIGRATION = Path(
    "db/migrations/093_authorize_verified_ats_origin_positive_lifecycle.sql"
)


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def authority_branches() -> tuple[str, str]:
    sql = migration_sql()
    start = sql.index(
        "      AND (\n"
        "            (\n"
        "                raw_job.raw_data ->> 'source_type'"
    )
    end = sql.index("\n          )\n      AND coalesce(", start)
    branch_sql = sql[start:end]
    return branch_sql.split("\n            OR\n", maxsplit=1)


def test_direct_career_site_authority_preserves_migration_092_contract() -> None:
    direct, _ = authority_branches()

    assert "'employer_origin_career_site'" in direct
    assert "{acquisition_boundary,detail_pages_fetched}" in direct
    assert "NULLIF(btrim(observation.source_url), '') IS NOT NULL" in direct
    assert "target_employer_verified" not in direct
    assert "raw_job.source_url" not in direct
    assert "{job,source_url}" not in direct


def test_verified_ats_authority_requires_exact_employer_detail_evidence() -> None:
    _, ats = authority_branches()

    assert "'employer_origin_ats_backed_career_site'" in ats
    assert "{detail_evidence,target_employer_verified}" in ats
    assert "= 'true'" in ats
    assert "{job,source_url}" in ats
    assert "NULLIF(btrim(raw_job.source_url), '')" in ats
    assert ats.count("NULLIF(btrim(observation.source_url), '')") == 2


def test_unverified_or_url_mismatched_ats_observation_cannot_gain_authority() -> None:
    _, ats = authority_branches()

    assert "target_employer_verified" in ats
    assert "= 'true'" in ats
    assert (
        "btrim(raw_job.raw_data #>> '{job,source_url}')" in ats
        and "btrim(observation.source_url)" in ats
    )
    assert "btrim(raw_job.source_url)" in ats


def test_ats_authority_keeps_epoch_and_success_status_bounds() -> None:
    sql = migration_sql()

    assert "authoritative_positive_v1" in sql
    assert "observation.observed_at >= epoch.started_at" in sql
    assert "{detail_evidence,status_code}" in sql
    assert "BETWEEN 200 AND 399" in sql
    assert "THEN 'active_confirmed'" in sql


def test_authority_does_not_expand_other_ats_families_or_sensors() -> None:
    sql = migration_sql().casefold()

    assert "personio" not in sql
    assert "greenhouse" not in sql
    assert "stepstone" not in sql
    assert "sensor" not in sql
