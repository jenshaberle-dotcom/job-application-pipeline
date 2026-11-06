from pathlib import Path

from src.search_intelligence.hannover_profile_market import PROFILE_TARGETS


STAGING_SQL = Path(
    "db/experiments/hannover_profile_solution_architecture_seed.sql"
)


def test_solution_architecture_profile_is_staged_but_never_silently_activated():
    sql = STAGING_SQL.read_text(encoding="utf-8")
    for term in PROFILE_TARGETS["solution_architecture"]:
        assert f"('{term}')" in sql

    assert "search_profiles" in sql
    assert "INSERT INTO search_terms" in sql
    assert "SELECT sp.id, terms.search_term, FALSE" in sql
    assert "ON CONFLICT (search_profile_id, search_term) DO NOTHING" in sql
    assert "INSERT INTO search_profiles" not in sql
    assert "UPDATE search_profiles" not in sql
    assert "UPDATE search_terms" not in sql
    assert "employer_origin_source_candidates" not in sql


def test_market_search_profiles_retain_existing_geo_scope():
    sql = STAGING_SQL.read_text(encoding="utf-8")
    assert "ba_data_engineer_30629_50km" in sql
    assert "ba_data_engineering_remote_nationwide_review" in sql
    assert "stepstone_data_engineer_hannover" in sql
    assert "scheduler" not in sql.lower().split("INSERT INTO search_terms")[1]
