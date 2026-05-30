from pathlib import Path


MIGRATION = Path("db/migrations/025_create_aggregator_discovery_suppression_snapshots.sql")


def test_aggregator_suppression_migration_creates_review_state_tables() -> None:
    sql = MIGRATION.read_text()

    assert "create table if not exists aggregator_discovery_suppression_batches" in sql
    assert "create table if not exists aggregator_discovery_suppression_items" in sql
    assert "stepstone_known_candidate_suppression" in sql
    assert "queue_employer_origin_recheck" in sql
    assert "keep_for_new_candidate_discovery" in sql


def test_aggregator_suppression_migration_documents_non_activation_boundary() -> None:
    sql = MIGRATION.read_text()

    assert "They do not activate sources" in sql
    assert "write Bronze rows" in sql
    assert "schedule ingestion" in sql
