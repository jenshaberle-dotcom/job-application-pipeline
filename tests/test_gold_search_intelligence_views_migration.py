from pathlib import Path


def test_gold_search_intelligence_views_migration_exists() -> None:
    migration = Path("db/migrations/038_create_gold_search_intelligence_views.sql")

    assert migration.exists()
    text = migration.read_text(encoding="utf-8")

    assert "create or replace view gold_candidate_lifecycle_status" in text
    assert "create or replace view gold_market_coverage_summary" in text
    assert "create or replace view gold_approval_queue" in text
    assert "create or replace view gold_source_health_summary" in text
    assert "false_negative_risk_snapshots" in text
    assert "employer_origin_connector_build_requests" in text
    assert "aggregator_novelty_snapshots" in text
    assert "csv" not in text.lower()


def test_gold_preview_script_is_read_only() -> None:
    script = Path("scripts/preview_gold_search_intelligence_metrics.py")

    assert script.exists()
    text = script.read_text(encoding="utf-8")

    assert "gold_market_coverage_summary" in text
    assert "gold_candidate_lifecycle_status" in text
    assert "gold_approval_queue" in text
    assert "from src.config import get_database_config" in text
    assert "JOB_PIPELINE_DB_" not in text
    assert "insert " not in text.lower()
    assert "update " not in text.lower()
    assert "delete " not in text.lower()
