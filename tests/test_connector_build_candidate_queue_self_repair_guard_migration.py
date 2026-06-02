from pathlib import Path


def test_connector_build_queue_self_repair_guard_migration_exists() -> None:
    text = Path("db/migrations/047_add_connector_build_queue_self_repair_guard.sql").read_text(encoding="utf-8")

    assert "gold_connector_build_candidate_queue" in text
    assert "url_repair_candidate_url = coalesce(g.candidate_url, l.origin_url)" in text
    assert "origin_source_discovery_required" in text
    assert "repair candidate equals current URL" in text
    assert "origin_url_repair_required" in text


def test_connector_build_queue_self_repair_guard_keeps_read_only_boundary() -> None:
    text = Path("db/migrations/047_add_connector_build_queue_self_repair_guard.sql").read_text(encoding="utf-8")

    assert "Read-only Gold view replacement only" in text
    assert "does not build" in text
    assert "connector artifacts" in text
    assert "write Bronze" in text
