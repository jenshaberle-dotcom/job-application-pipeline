from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from scripts.run_project_state_snapshot import (
    SNAPSHOT_SCHEMA_VERSION,
    build_project_state_snapshot,
    render_markdown,
    write_snapshot_reports,
)


def _write_required_docs(root: Path) -> None:
    required_files = [
        "docs/README.md",
        "docs/current/product.md",
        "docs/current/architecture.md",
        "docs/current/pipeline.md",
        "docs/current/system-diagrams.md",
        "docs/current/governance.md",
        "docs/current/operations.md",
        "docs/guides/development-workflow.md",
        "docs/guides/operator-runbook.md",
        "docs/reference/database/schema_overview.md",
        "docs/reference/governance/governance_foundation.md",
        "docs/reference/security/search_intelligence_security_baseline.md",
        "docs/decisions/adr_status_table.md",
        "docs/decisions/adr/033_define_search_intelligence_safety_security_boundaries.md",
        "docs/planning/active/README.md",
        "docs/archive/planning/doc001j_link_reference_check.md",
        "docs/archive/source-analysis/stepstone_company_discovery_cycle.md",
    ]
    for relative_path in required_files:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.name}\n", encoding="utf-8")


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def test_state001a_snapshot_is_read_only_and_machine_readable(tmp_path: Path) -> None:
    _write_required_docs(tmp_path)
    _init_git_repo(tmp_path)

    snapshot = build_project_state_snapshot(
        tmp_path,
        generated_at=datetime(2026, 6, 8, 12, 0, tzinfo=UTC),
    )

    assert snapshot["schema_version"] == SNAPSHOT_SCHEMA_VERSION
    assert snapshot["read_only"] is True
    assert snapshot["external_requests"] is False
    assert snapshot["database_reads"] is False
    assert snapshot["database_writes"] is False
    assert snapshot["documentation"]["architecture_status"] == "pass"
    assert snapshot["validation"]["latest_validation_known_to_snapshot"] == "not_run_by_snapshot"
    assert snapshot["horizontal_freeze_path_bundle_mode"]["mode_id"] == "FREEZE-001A"
    assert snapshot["horizontal_freeze_path_bundle_mode"]["available"] is True
    assert "python scripts/run_validate001_unified_validation.py --profile commit" in snapshot["validation"]["required_before_commit_or_pr"]
    assert snapshot["next_safe_action"]["action"] in {
        "select_next_work_item_then_create_feature_branch",
        "inspect_branch_intent_before_patch",
    }


def test_state001a_snapshot_detects_dirty_worktree(tmp_path: Path) -> None:
    _write_required_docs(tmp_path)
    _init_git_repo(tmp_path)
    (tmp_path / "README.md").write_text("changed\n", encoding="utf-8")

    snapshot = build_project_state_snapshot(tmp_path)

    assert snapshot["git"]["is_dirty"] is True
    assert "README.md" in snapshot["git"]["changed_files"]
    assert snapshot["next_safe_action"]["action"] == "validate_current_worktree_before_commit_or_continue"


def test_state001a_snapshot_detects_documentation_architecture_failure(tmp_path: Path) -> None:
    _write_required_docs(tmp_path)
    (tmp_path / "docs" / "project_state").mkdir()
    _init_git_repo(tmp_path)

    snapshot = build_project_state_snapshot(tmp_path)

    assert snapshot["documentation"]["architecture_status"] == "fail"
    assert "project_state" in snapshot["documentation"]["forbidden_top_level_dirs_present"]
    assert snapshot["next_safe_action"]["action"] == "fix_documentation_architecture_before_patch"


def test_state001a_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    _write_required_docs(tmp_path)
    _init_git_repo(tmp_path)
    snapshot = build_project_state_snapshot(tmp_path)

    json_path, markdown_path = write_snapshot_reports(snapshot, tmp_path / "exports", "state test")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert payload["schema_version"] == SNAPSHOT_SCHEMA_VERSION
    assert "# Project State Snapshot" in markdown
    assert "## Next safe action" in markdown
    assert json_path.name == "state_test.json"
    assert markdown_path.name == "state_test.md"


def test_state001a_markdown_contains_tooling_governance_sequence(tmp_path: Path) -> None:
    _write_required_docs(tmp_path)
    _init_git_repo(tmp_path)
    snapshot = build_project_state_snapshot(tmp_path)

    markdown = render_markdown(snapshot)

    assert "STATE-001 Project State Snapshot Contract" in markdown
    assert "INSPECT-001 Repo/DB/Docs Inspection Bundle" in markdown
    assert "MCP-001 External Engineering Agent Control Plane" in markdown
    assert "Horizontal Freeze-Path Bundle Mode" in markdown
