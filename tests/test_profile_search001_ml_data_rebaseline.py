from pathlib import Path


MIGRATION = Path("db/migrations/076_rebaseline_stepstone_ml_data_search_profile.sql")
PROFILE = Path("docs/planning/active/canonical_target_profile.md")
RELEVANCE = Path("docs/reference/scoring-and-gates/relevance_strategy.md")


PRIMARY_TERMS = (
    "Machine Learning Engineer",
    "ML Engineer",
    "MLOps Engineer",
    "ML Platform Engineer",
    "AI Platform Engineer",
    "AI Engineer",
)

DATA_BRIDGE_TERMS = (
    "Data Engineer",
    "Data Platform Engineer",
    "Analytics Engineer",
)

RELIABILITY_TERMS = (
    "AI Reliability Engineer",
    "ML Reliability Engineer",
)



def test_stepstone_profile_is_rebased_to_ml_first_search_raster() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "stepstone_data_engineer_hannover" in sql
    assert "UPDATE search_terms st" in sql
    assert "SET is_active = FALSE" in sql

    for term in PRIMARY_TERMS + DATA_BRIDGE_TERMS + RELIABILITY_TERMS:
        assert f"('{term}')" in sql

    assert "('Machine Learning')" in sql



def test_old_data_first_terms_are_not_active_values_in_new_raster() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    values_block = sql.split("CROSS JOIN (", maxsplit=1)[1].split(") AS terms", maxsplit=1)[0]

    for old_term in ("ETL", "Data Warehouse", "Big Data", "Python SQL"):
        assert f"('{old_term}')" not in values_block



def test_canonical_profile_keeps_ml_identity_data_focus_and_reliability_direction() -> None:
    profile = PROFILE.read_text(encoding="utf-8")

    assert "Foundation role family:** Machine Learning Engineer" in profile
    assert "Technical focus:** Data Engineering and data-centric ML systems" in profile
    assert "Future specialization:** AI Reliability" in profile

    for term in PRIMARY_TERMS + DATA_BRIDGE_TERMS + RELIABILITY_TERMS:
        assert f"`{term}`" in profile



def test_relevance_strategy_treats_accessibility_and_work_model_as_preferences() -> None:
    relevance = RELEVANCE.read_text(encoding="utf-8")

    assert "Approximately 30 minutes commute per direction is ideal" in relevance
    assert "Up to approximately 45 minutes per direction is generally acceptable" in relevance
    assert "Good public-transport access is desirable but not required" in relevance
    assert "Hybrid wins as a preference when otherwise comparable jobs" in relevance



def test_not_wave_scope_is_not_silently_expanded_to_unvalidated_ml_terms() -> None:
    profile = PROFILE.read_text(encoding="utf-8")

    assert "Current approved wave terms" in profile
    assert "`Data Engineer`" in profile
    assert "`Analytics Engineer`" in profile
    assert "New ML-first terms must first pass bounded stability probes" in profile
