from __future__ import annotations

from pathlib import Path
import re

from src.search_intelligence.employer_origin_gate_registry import DEFAULT_GATES


MIGRATION = Path(
    "db/migrations/094_initialize_employer_origin_candidate_gate_registry.sql"
)


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_trigger_initializes_exact_canonical_registry() -> None:
    sql = migration_sql()
    trigger_rows = re.findall(
        r"\(NEW\.id,\s*'([^']+)',\s*(\d+),\s*'not_started',\s*'defer',\s*(true|false)",
        sql,
    )
    actual = tuple(
        (int(gate_order), gate_name, is_hard_gate == "true")
        for gate_name, gate_order, is_hard_gate in trigger_rows
    )

    assert actual == DEFAULT_GATES
    assert "AFTER INSERT ON employer_origin_source_candidates" in sql
    assert "FOR EACH ROW" in sql
    assert "RETURN NEW;" in sql


def test_backfill_uses_same_canonical_registry() -> None:
    sql = migration_sql()
    backfill_sql = sql.split(
        "WITH official_gates(gate_order, gate_name, is_hard_gate) AS (",
        maxsplit=1,
    )[1]
    rows = re.findall(
        r"\(\s*(\d+),\s*'([^']+)',\s*(true|false)\s*\)",
        backfill_sql,
    )
    actual = tuple(
        (int(gate_order), gate_name, is_hard_gate == "true")
        for gate_order, gate_name, is_hard_gate in rows
    )

    assert actual == DEFAULT_GATES
    assert "CROSS JOIN official_gates AS gate" in backfill_sql


def test_registry_repair_is_additive_and_preserves_existing_evidence() -> None:
    sql = migration_sql()

    assert sql.count("ON CONFLICT (candidate_id, gate_name)") == 2
    assert sql.count("DO NOTHING;") == 2
    assert "DO UPDATE" not in sql
    assert "UPDATE employer_origin_candidate_gate_reviews" not in sql
    assert "DELETE FROM employer_origin_candidate_gate_reviews" not in sql


def test_registry_initialization_has_no_lifecycle_side_effects() -> None:
    sql = migration_sql().casefold()

    assert "insert into connector" not in sql
    assert "insert into raw_jobs" not in sql
    assert "insert into normalized_jobs" not in sql
    assert "update scheduler" not in sql
    assert "active_controlled" not in sql
