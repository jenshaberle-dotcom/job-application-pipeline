from __future__ import annotations

from pathlib import Path

SCRIPT = Path("scripts/run_employer_origin_reprocess_benchmark.py")


def test_reprocess_benchmark_is_dry_run_by_default_and_requires_apply() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "--apply" in text
    assert "dry_run: no candidate or gate rows were changed" in text
    assert "pass --apply to execute next-safe actions" in text


def test_reprocess_benchmark_active_controlled_is_explicit() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "--include-active-controlled" in text
    assert "active_controlled" in text
    assert "IN_PROCESS_STATUSES" in text


def test_reprocess_benchmark_excludes_active_controlled_gate_history_by_default() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "active_controlled_history_guard" in text
    assert "c.status <> 'active_controlled'" in text
    assert "TRUE" in text
