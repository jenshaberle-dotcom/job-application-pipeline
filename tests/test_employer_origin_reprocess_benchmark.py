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



def test_reprocess_benchmark_reset_evidence_casts_reviewed_by_parameter() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "'reviewed_by', %s::text" in text


def test_reprocess_benchmark_actions_use_company_keys_not_candidate_url_identity() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "--company-key" in text
    assert "run_employer_origin_next_safe_action_agent" in text
    assert "--candidate-url" not in text


def test_reprocess_benchmark_excludes_literal_none_candidate_urls() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "lower(btrim(coalesce(c.candidate_url, ''))) NOT IN ('none', 'null')" in text
