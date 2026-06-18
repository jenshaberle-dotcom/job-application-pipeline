from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import subprocess
import sys
from typing import Callable, Mapping, Sequence

SCHEMA_VERSION = "generic010.report_chain_refresh_runner.v1"
WORK_ITEM = "GENERIC-010 Market to EXPAND to GENERIC Report Chain Refresh Runner"
DEFAULT_CHAIN = (
    ("market003c_candidate_expansion_review", "scripts/run_market003c_candidate_expansion_review.py"),
    ("market003d_candidate_expansion_review_action_plan", "scripts/run_market003d_candidate_expansion_review_action_plan.py"),
    ("market003e_candidate_expansion_review_queue_readiness", "scripts/run_market003e_candidate_expansion_review_queue_readiness.py"),
    ("market003f_expand001_controlled_manual_candidate_pipeline_trial", "scripts/run_market003f_expand001_controlled_manual_candidate_pipeline_trial.py"),
    ("expand003_candidate_review_delta_report", "scripts/run_expand003_candidate_review_delta_report.py"),
    ("generic001_pipeline_generics_proof_gate", "scripts/run_generic001_pipeline_generics_proof_gate.py"),
    ("generic002_benchmark_gap_closure_plan", "scripts/run_generic002_benchmark_gap_closure_plan.py"),
    ("generic003_benchmark_control_rerun_review", "scripts/run_generic003_benchmark_control_rerun_review.py"),
    ("generic004_stop_control_evidence_capture_plan", "scripts/run_generic004_stop_control_evidence_capture_plan.py"),
    ("generic005_stop_control_final_rerun", "scripts/run_generic005_stop_control_final_rerun.py"),
    ("generic006_stop_control_capture_repair_packet", "scripts/run_generic006_stop_control_capture_repair_packet.py"),
    ("expand004_controlled_candidate_creation_dry_run", "scripts/run_expand004_controlled_candidate_creation_dry_run.py"),
    ("expand006_candidate_creation_evidence_review", "scripts/run_expand006_candidate_creation_evidence_review.py", "--include-db"),
    ("expand007_controlled_candidate_creation_apply_gate_readiness", "scripts/run_expand007_controlled_candidate_creation_apply_gate_readiness.py"),
    ("expand008_freeze_path_blocker_snapshot", "scripts/run_expand008_freeze_path_blocker_snapshot.py"),
)
OPTIONAL_EXTERNAL_PROBE_STEP = (
    "expand002_controlled_external_probe_trial_run",
    "scripts/run_expand002_controlled_external_probe_trial_run.py",
)

RunCommand = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]


def safety_boundary(*, include_external_probe: bool) -> dict[str, bool | str]:
    return {
        "report_refresh_only": True,
        "uses_existing_report_scripts": True,
        "external_requests_allowed_by_runner": include_external_probe,
        "database_writes_allowed_by_runner": False,
        "candidate_creation": False,
        "candidate_promotion": False,
        "gate_decision": False,
        "connector_activation": False,
        "scheduler_change": False,
        "bronze_silver_gold_mutation": False,
        "csv_excel_or_export_as_pipeline_input": False,
        "decision_boundary": "report_chain_refresh_not_apply_not_pipeline_mutation",
    }


def build_chain(*, include_external_probe: bool = False) -> list[tuple[str, ...]]:
    chain = list(DEFAULT_CHAIN)
    if include_external_probe:
        insert_at = 4
        chain.insert(insert_at, OPTIONAL_EXTERNAL_PROBE_STEP)
    return chain


def build_dry_run_report(*, include_external_probe: bool = False, generated_at: str | None = None) -> dict[str, object]:
    chain = build_chain(include_external_probe=include_external_probe)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "overall_status": "dry_run_only",
        "safety_boundary": safety_boundary(include_external_probe=include_external_probe),
        "summary": {
            "step_count": len(chain),
            "failure_count": None,
            "skipped_count": None,
            "dependency_block_count": 0,
            "include_external_probe": include_external_probe,
            "keep_going": False,
        },
        "step_count": len(chain),
        "steps": [_step_to_dict(index, step, skipped=False) for index, step in enumerate(chain, start=1)],
        "next_action": "Run without --dry-run only after confirming this report-only chain order.",
    }


def run_chain(
    *,
    repo_root: Path,
    include_external_probe: bool = False,
    keep_going: bool = False,
    runner: RunCommand | None = None,
    generated_at: str | None = None,
) -> dict[str, object]:
    chain = build_chain(include_external_probe=include_external_probe)
    run = runner or _default_runner
    results: list[dict[str, object]] = []
    failed = False
    dependency_blocked = False
    for index, step in enumerate(chain, start=1):
        name = step[0]
        command = [sys.executable, *step[1:]]
        if failed and not keep_going:
            results.append(_step_to_dict(index, step, skipped=True, skip_reason="previous_step_failed"))
            continue
        if dependency_blocked and not keep_going:
            results.append(_step_to_dict(index, step, skipped=True, skip_reason="previous_dependency_missing"))
            continue

        dependency_issue = _dependency_issue_for_step(
            name,
            repo_root=repo_root,
            include_external_probe=include_external_probe,
        )
        if dependency_issue is not None:
            dependency_blocked = True
            results.append(
                _step_to_dict(
                    index,
                    step,
                    skipped=True,
                    skip_reason="missing_dependency",
                    dependency_issue=dependency_issue,
                )
            )
            continue

        completed = run(command, repo_root)
        step_result = _completed_to_dict(index, name, command, completed)
        results.append(step_result)
        if completed.returncode != 0:
            failed = True
    failure_count = sum(1 for item in results if item.get("exit_code") not in (0, None))
    skipped_count = sum(1 for item in results if item.get("skipped"))
    dependency_block_count = sum(1 for item in results if item.get("skip_reason") == "missing_dependency")
    overall_status = _overall_status(failure_count=failure_count, dependency_block_count=dependency_block_count)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "overall_status": overall_status,
        "safety_boundary": safety_boundary(include_external_probe=include_external_probe),
        "summary": {
            "step_count": len(chain),
            "failure_count": failure_count,
            "skipped_count": skipped_count,
            "dependency_block_count": dependency_block_count,
            "include_external_probe": include_external_probe,
            "keep_going": keep_going,
        },
        "steps": results,
        "next_action": _next_action(failure_count=failure_count, dependency_block_count=dependency_block_count),
    }


def _default_runner(command: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def _step_to_dict(
    index: int,
    step: Sequence[str],
    *,
    skipped: bool,
    skip_reason: str | None = None,
    dependency_issue: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "index": index,
        "name": step[0],
        "command": [sys.executable, *step[1:]],
        "skipped": skipped,
        "skip_reason": skip_reason,
        "dependency_issue": dict(dependency_issue or {}),
        "exit_code": None,
        "stdout_tail": "",
        "stderr_tail": "",
    }


def _completed_to_dict(
    index: int,
    name: str,
    command: Sequence[str],
    completed: subprocess.CompletedProcess[str],
) -> dict[str, object]:
    return {
        "index": index,
        "name": name,
        "command": list(command),
        "skipped": False,
        "skip_reason": None,
        "dependency_issue": {},
        "exit_code": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def _dependency_issue_for_step(
    name: str,
    *,
    repo_root: Path,
    include_external_probe: bool,
) -> dict[str, object] | None:
    if name != "expand003_candidate_review_delta_report":
        return None
    if include_external_probe:
        return None
    if _find_latest_expand002_report(repo_root) is not None:
        return None
    return {
        "dependency_status": "missing",
        "required_report": "expand002_controlled_external_probe_trial_run",
        "required_input": "EXPAND-002 controlled external probe trial report",
        "reason": (
            "EXPAND-003 requires an EXPAND-002 report, but the external probe step "
            "is excluded and no existing EXPAND-002 report was found."
        ),
        "safe_next_action": (
            "Decide whether to run the bounded external probe explicitly or keep the "
            "EXPAND path blocked; do not auto-enable external requests."
        ),
    }


def _find_latest_expand002_report(repo_root: Path) -> Path | None:
    exports_dir = repo_root / "exports"
    candidates = list(
        exports_dir.glob(
            "expand002_controlled_external_probe_trial_run_*/expand002_controlled_external_probe_trial_run.json"
        )
    )
    default = exports_dir / "expand002_controlled_external_probe_trial_run" / "expand002_controlled_external_probe_trial_run.json"
    if default.exists():
        candidates.append(default)
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _overall_status(*, failure_count: int, dependency_block_count: int) -> str:
    if failure_count:
        return "fail"
    if dependency_block_count:
        return "blocked_missing_dependency"
    return "pass"


def _next_action(*, failure_count: int, dependency_block_count: int) -> str:
    if failure_count:
        return "Review failing step before rerunning downstream reports."
    if dependency_block_count:
        return "Review missing report dependency before rerunning downstream reports."
    return "Report chain refreshed; inspect GENERIC-005/EXPAND-008 for remaining proof gaps."


def _tail(value: str, *, max_chars: int = 4000) -> str:
    if len(value) <= max_chars:
        return value
    return value[-max_chars:]


def render_markdown(report: Mapping[str, object]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    lines = [
        "# GENERIC-010 Report Chain Refresh Runner",
        "",
        f"Generated: `{report.get('generated_at_utc')}`",
        f"Overall status: `{report.get('overall_status')}`",
        "",
        "Boundary: `report_chain_refresh_not_apply_not_pipeline_mutation`",
        "",
        "## Summary",
        "",
        f"- Steps: `{summary.get('step_count', report.get('step_count'))}`",
        f"- Failures: `{summary.get('failure_count')}`",
        f"- Skipped: `{summary.get('skipped_count')}`",
        f"- Dependency blocks: `{summary.get('dependency_block_count')}`",
        f"- Include external probe: `{summary.get('include_external_probe')}`",
        "",
        "## Steps",
        "",
    ]
    for step in report.get("steps", []):
        if isinstance(step, Mapping):
            dependency_issue = step.get("dependency_issue") if isinstance(step.get("dependency_issue"), Mapping) else {}
            dependency_reason = f" dependency=`{dependency_issue.get('required_report')}`" if dependency_issue else ""
            lines.append(
                f"- `{step.get('index')}` `{step.get('name')}` exit=`{step.get('exit_code')}` "
                f"skipped=`{step.get('skipped')}` reason=`{step.get('skip_reason')}`{dependency_reason}"
            )
    lines.extend(["", "## Next action", "", str(report.get("next_action")), ""])
    return "\n".join(lines)


def write_outputs(report: Mapping[str, object], export_dir: Path) -> dict[str, Path]:
    export_dir.mkdir(parents=True, exist_ok=True)
    json_path = export_dir / "generic010_report_chain_refresh_runner.json"
    md_path = export_dir / "generic010_report_chain_refresh_runner.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
