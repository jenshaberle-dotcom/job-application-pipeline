from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from scripts.run_next001_next_safe_action_report import (
    NEXT001_SCHEMA_VERSION,
    _changed_files,
    default_output_dir,
    build_next_safe_action_report,
    render_markdown,
    safety_boundary,
    write_reports,
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


def _write_tooling_paths(root: Path, *, include_next: bool = False) -> None:
    paths = [
        "scripts/run_project_state_snapshot.py",
        "tests/test_project_state_snapshot.py",
        "scripts/run_inspect001_repo_db_docs_bundle.py",
        "tests/test_inspect001_repo_db_docs_bundle.py",
        "docs/reference/governance/workflow/inspect001_repo_db_docs_bundle.md",
        "scripts/run_handover001_validate_contract.py",
        "tests/test_handover001_contract.py",
        "docs/reference/governance/workflow/handover001_standard_chat_handover_contract.md",
        "scripts/run_rules001_validate_index.py",
        "tests/test_rules001_project_rules_index.py",
        "docs/reference/governance/workflow/rules001_project_rules_index.md",
        "scripts/run_validate001_unified_validation.py",
        "tests/test_validate001_unified_validation.py",
        "docs/reference/governance/workflow/validate001_unified_validation_command.md",
    ]
    if include_next:
        paths.extend(
            [
                "scripts/run_next001_next_safe_action_report.py",
                "tests/test_next001_next_safe_action_report.py",
                "docs/reference/governance/workflow/next001_next_safe_action_report.md",
            ]
        )
    for relative_path in paths:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.name}\n", encoding="utf-8")


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "checkout", "-b", "main"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def test_next001_report_is_read_only_and_recommends_next_tooling_item(tmp_path: Path) -> None:
    _write_required_docs(tmp_path)
    _write_tooling_paths(tmp_path, include_next=False)
    _init_git_repo(tmp_path)

    report = build_next_safe_action_report(
        tmp_path,
        output_dir=tmp_path / "exports",
        generated_at=datetime(2026, 6, 8, 12, 0, tzinfo=UTC).isoformat(),
    )

    assert report["schema_version"] == NEXT001_SCHEMA_VERSION
    assert report["safety_boundary"] == safety_boundary()
    assert report["standard_workflow_completion"]["present_in_head_count"] == 5
    assert report["next_safe_action"]["action"] == "create_feature_branch_for_next_tooling_governance_item"
    assert report["next_safe_action"]["work_item"] == "NEXT-001A"
    assert report["next_safe_action"]["requires_user_decision"] is False


def test_next001_detects_stale_handover_recommendation(tmp_path: Path) -> None:
    _write_required_docs(tmp_path)
    _write_tooling_paths(tmp_path, include_next=False)
    _init_git_repo(tmp_path)
    current_head = subprocess.check_output(["git", "log", "-1", "--oneline", "--decorate"], cwd=tmp_path, text=True).strip()

    exports = tmp_path / "exports"
    exports.mkdir()
    handover_path = exports / "efficient_handover_after_rules001a_20260608-120000.json"
    handover_path.write_text(
        json.dumps(
            {
                "git": {"head": current_head},
                "completed_work_items": ["STATE-001A", "INSPECT-001A", "HANDOVER-001A", "RULES-001A"],
                "recommended_next": ["VALIDATE-001 Unified Validation Command", "NEXT-001 Next Safe Action Report"],
            }
        ),
        encoding="utf-8",
    )
    # Keep the fixture repository clean so restart_readiness can evaluate the
    # stale handover signal instead of correctly stopping at worktree_dirty.
    subprocess.run(["git", "add", str(handover_path.relative_to(tmp_path))], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "add stale handover fixture"],
        cwd=tmp_path,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    report = build_next_safe_action_report(tmp_path, output_dir=exports)

    handover_signal = report["handover_signal"]
    assert handover_signal["status"] == "stale"
    assert "handover_completed_work_items_missing_present_head_items" in handover_signal["stale_reasons"]
    assert "handover_recommended_next_contains_already_implemented_item" in handover_signal["stale_reasons"]
    assert "VALIDATE-001A" in handover_signal["missing_completed_items_from_handover"]
    assert report["restart_readiness"]["status"] == "refresh_handover_required"


def test_next001_recommends_product_return_after_standard_workflow_is_present(tmp_path: Path) -> None:
    _write_required_docs(tmp_path)
    _write_tooling_paths(tmp_path, include_next=True)
    _init_git_repo(tmp_path)

    report = build_next_safe_action_report(tmp_path, output_dir=tmp_path / "exports")

    assert report["standard_workflow_completion"]["present_in_head_count"] == 6
    assert report["next_safe_action"]["action"] == "return_to_product_pipeline_work_with_explicit_work_item"
    assert report["next_safe_action"]["workstream"] == "search_intelligence_product_work"
    assert report["next_safe_action"]["work_item"] == "PROVIDER-001B Read-only Provider Evidence Discovery"
    assert report["next_safe_action"]["requires_user_decision"] is True
    assert report["horizontal_freeze_path_bundle_mode"]["mode_id"] == "FREEZE-001A"
    assert report["horizontal_freeze_path_bundle_mode"]["available"] is True
    assert report["restart_readiness"]["status"] == "ready_for_next_work_selection"


def test_next001_dirty_worktree_prevents_new_work_recommendation(tmp_path: Path) -> None:
    _write_required_docs(tmp_path)
    _write_tooling_paths(tmp_path, include_next=True)
    _init_git_repo(tmp_path)
    (tmp_path / "README.md").write_text("changed\n", encoding="utf-8")

    report = build_next_safe_action_report(tmp_path, output_dir=tmp_path / "exports")

    assert report["git"]["is_dirty"] is True
    assert report["next_safe_action"]["action"] == "validate_current_worktree_before_commit_or_continue"


def test_next001_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    _write_required_docs(tmp_path)
    _write_tooling_paths(tmp_path, include_next=True)
    _init_git_repo(tmp_path)
    report = build_next_safe_action_report(tmp_path, output_dir=tmp_path / "exports")

    written = write_reports(report, tmp_path / "exports", stamp="20260608-120000")

    json_path = Path(written["json"])
    markdown_path = Path(written["markdown"])
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert payload["schema_version"] == NEXT001_SCHEMA_VERSION
    assert "restart_readiness" in payload
    assert "# NEXT-001A Next Safe Action Report" in markdown
    assert "## Horizontal Freeze-Path Bundle Mode" in markdown
    assert "## Restart readiness" in markdown
    assert "## Next safe action" in markdown


def test_next001_markdown_contains_handover_stale_details(tmp_path: Path) -> None:
    _write_required_docs(tmp_path)
    _write_tooling_paths(tmp_path, include_next=False)
    _init_git_repo(tmp_path)
    exports = tmp_path / "exports"
    exports.mkdir()
    handover_path = exports / "efficient_handover.json"
    handover_path.write_text(
        json.dumps(
            {
                "git": {"head": "oldhash Old state"},
                "completed_work_items": ["STATE-001A"],
                "recommended_next": ["VALIDATE-001 Unified Validation Command"],
            }
        ),
        encoding="utf-8",
    )

    report = build_next_safe_action_report(tmp_path, output_dir=exports)
    markdown = render_markdown(report)

    assert "Handover signal" in markdown
    assert "handover_git_head_does_not_match_current_head" in markdown
    assert "VALIDATE-001A" in markdown

def test_next001_changed_files_parser_preserves_docs_prefix() -> None:
    changed = _changed_files([
        " M docs/current/operations.md",
        "M docs/reference/README.md",
        "?? docs/reference/governance/workflow/",
    ])

    assert "docs/current/operations.md" in changed
    assert "docs/reference/README.md" in changed
    assert "docs/reference/governance/workflow/" in changed
    assert "ocs/current/operations.md" not in changed


def test_next001_does_not_treat_contract_validation_as_chat_handover(tmp_path: Path) -> None:
    _write_required_docs(tmp_path)
    _write_tooling_paths(tmp_path, include_next=True)
    _init_git_repo(tmp_path)
    exports = tmp_path / "exports"
    exports.mkdir()
    (exports / "handover001_contract_validation_20260608-120000.json").write_text(
        json.dumps({"schema_version": "handover001.contract_validation.v1", "status": "pass"}),
        encoding="utf-8",
    )

    report = build_next_safe_action_report(tmp_path, output_dir=exports)

    assert report["handover_signal"]["status"] == "not_provided"
    assert report["handover_signal"]["stale_reasons"] == []



def test_next001_default_output_dir_is_run_scoped_under_exports() -> None:
    assert default_output_dir("20260613-123456") == Path("exports") / "next001_next_safe_action_report_20260613-123456"
