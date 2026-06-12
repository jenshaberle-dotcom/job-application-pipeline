from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.search_intelligence.generic_pipeline_proof_gate import (
    build_generic_pipeline_proof_report,
    find_latest_expand003_report,
    load_expand003_report,
    write_outputs as write_generic001_outputs,
)

SCHEMA_VERSION = "generic003.benchmark_control_rerun_review.v1"
WORK_ITEM = "GENERIC-003 Benchmark Control Rerun Review"
GENERIC002_SCHEMA_PREFIX = "generic002.benchmark_gap_closure_plan"

READY_STATUS = "ready_to_close_with_existing_artifact"
POSITIVE_GAP = "positive_control_coverage"
NEGATIVE_GAP = "negative_control_coverage"
NO_ACTIONABLE_GAP = "no_actionable_evidence_coverage"


def no_mutation_boundary() -> dict[str, bool]:
    return {
        "review_artifact_only": True,
        "external_requests": False,
        "database_reads": False,
        "database_writes": False,
        "candidate_creation": False,
        "candidate_promotion": False,
        "gate_decision": False,
        "connector_activation": False,
        "scheduler_mutation": False,
        "bronze_silver_gold_mutation": False,
    }


def mutation_counts() -> dict[str, int]:
    return {
        "created_candidates": 0,
        "automatic_candidate_promotions": 0,
        "written_gate_decisions": 0,
        "activated_connectors": 0,
        "scheduler_changes": 0,
        "bronze_silver_gold_writes": 0,
        "database_writes": 0,
        "external_requests": 0,
    }


def load_generic002_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("GENERIC-002 input JSON root must be an object.")
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(GENERIC002_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected GENERIC-002 schema_version: {schema_version or '<missing>'}")
    return payload


def _timestamp_from_parent(path: Path) -> str:
    name = path.parent.name
    for prefix in (
        "generic003_benchmark_control_rerun_review_",
        "generic002_benchmark_gap_closure_plan_",
        "generic002_benchmark_gap_closure_plan",
    ):
        if name.startswith(prefix):
            return name.removeprefix(prefix)
    return ""


def find_latest_generic002_report(exports_dir: Path = Path("exports")) -> Path | None:
    patterns = [
        "generic002_benchmark_gap_closure_plan/generic002_benchmark_gap_closure_plan.json",
        "generic002_benchmark_gap_closure_plan_*/generic002_benchmark_gap_closure_plan.json",
    ]
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(path for path in exports_dir.glob(pattern) if path.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda path: (_timestamp_from_parent(path), path.stat().st_mtime, str(path)))


def build_benchmark_control_rerun_review(
    generic002_report: Mapping[str, Any],
    expand003_report: Mapping[str, Any],
    *,
    generic002_path: str | None = None,
    expand003_path: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    closure_steps = _mapping_list(generic002_report.get("closure_steps"))
    positive_control_keys = _control_keys(closure_steps, POSITIVE_GAP)
    negative_control_keys = _control_keys(closure_steps, NEGATIVE_GAP)
    before_gap_ids = _gap_ids_from_generic002(generic002_report, closure_steps)

    generic001_after = build_generic_pipeline_proof_report(
        expand003_report,
        expand003_path=expand003_path,
        positive_control_keys=positive_control_keys,
        negative_control_keys=negative_control_keys,
        generated_at=generated_at,
    )
    after_gap_ids = _string_list(generic001_after.get("gap_ids"))
    closed_gap_ids = sorted(gap for gap in before_gap_ids if gap not in after_gap_ids)
    still_blocked_gap_ids = sorted(gap for gap in before_gap_ids if gap in after_gap_ids)
    newly_detected_gap_ids = sorted(gap for gap in after_gap_ids if gap not in before_gap_ids)

    overall_status = _overall_status(
        positive_control_keys=positive_control_keys,
        negative_control_keys=negative_control_keys,
        closed_gap_ids=closed_gap_ids,
        after_gap_ids=after_gap_ids,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "overall_status": overall_status,
        "generic002_input_path": generic002_path,
        "generic002_input_schema_version": generic002_report.get("schema_version"),
        "generic002_input_overall_status": generic002_report.get("overall_status"),
        "expand003_input_path": expand003_path,
        "expand003_input_schema_version": expand003_report.get("schema_version"),
        "safety_boundary": no_mutation_boundary(),
        "mutation_counts": mutation_counts(),
        "interpretation_boundary": (
            "GENERIC-003 performs an artifact-only control rerun from GENERIC-002 recommendations. It may close explicit "
            "control metadata gaps by rerunning GENERIC-001 in memory, but it does not create candidates, write gates, "
            "activate connectors, mutate Bronze/Silver/Gold, change scheduler behavior, read the database, or perform external requests."
        ),
        "summary": {
            "before_gap_count": len(before_gap_ids),
            "after_gap_count": len(after_gap_ids),
            "closed_gap_count": len(closed_gap_ids),
            "still_blocked_gap_count": len(still_blocked_gap_ids),
            "newly_detected_gap_count": len(newly_detected_gap_ids),
            "positive_control_keys": positive_control_keys,
            "negative_control_keys": negative_control_keys,
            "closed_gap_ids": closed_gap_ids,
            "still_blocked_gap_ids": still_blocked_gap_ids,
            "newly_detected_gap_ids": newly_detected_gap_ids,
        },
        "control_rerun_command": _control_rerun_command(positive_control_keys, negative_control_keys),
        "generic001_after_summary": _generic001_summary(generic001_after),
        "remaining_benchmark_evidence_requests": build_remaining_benchmark_evidence_requests(after_gap_ids),
        "next_action": build_next_action(overall_status, after_gap_ids),
        "generic001_after_report": generic001_after,
    }


def build_remaining_benchmark_evidence_requests(after_gap_ids: Sequence[str]) -> list[dict[str, str]]:
    requests: list[dict[str, str]] = []
    if NO_ACTIONABLE_GAP in after_gap_ids:
        requests.append(
            {
                "gap_id": NO_ACTIONABLE_GAP,
                "evidence_needed": "one reviewed benchmark row with a clean no-actionable-evidence stop action",
                "acceptable_review_actions": "no_useful_external_hint_no_candidate_creation, provider_auth_failed_requires_key_review, probe_error_requires_retry_or_review",
                "boundary": "capture as review artifact only; do not create a candidate or write a gate decision",
            }
        )
    if NEGATIVE_GAP in after_gap_ids:
        requests.append(
            {
                "gap_id": NEGATIVE_GAP,
                "evidence_needed": "one explicit known-stopped or blocked negative control candidate key",
                "acceptable_review_actions": "same safe-stop actions as no-actionable evidence; weak-only market hints alone are not a negative control",
                "boundary": "operator control metadata only; do not infer a negative control silently from company name or weak evidence",
            }
        )
    if POSITIVE_GAP in after_gap_ids:
        requests.append(
            {
                "gap_id": POSITIVE_GAP,
                "evidence_needed": "one explicit known-good positive control candidate key with strong_detail or strong_origin evidence",
                "acceptable_review_actions": "ready_for_human_evidence_review or ready_for_detail_followup_review with strong evidence",
                "boundary": "operator control metadata only; do not infer a positive control silently from company name",
            }
        )
    return requests


def build_next_action(overall_status: str, after_gap_ids: Sequence[str]) -> str:
    if overall_status == "passed_all_control_and_generics_checks_review_artifact_only":
        return "GENERIC-001 now passes as review artifact only; design EXPAND-004 as a separate controlled dry-run, not broad apply."
    if overall_status == "partial_control_closure_remaining_benchmark_gaps":
        return (
            "Keep EXPAND-004, Wave Search scaling, scheduler changes, and TOP5 product claims blocked. Capture the remaining "
            f"benchmark evidence first: {', '.join(after_gap_ids) or '<unknown>'}."
        )
    if overall_status == "no_control_keys_available":
        return "No explicit control keys were available from GENERIC-002; capture positive/negative control metadata before rerunning GENERIC-001."
    return "Review why the GENERIC-003 control rerun did not close expected benchmark gaps before continuing."


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# GENERIC-003 Benchmark Control Rerun Review",
        "",
        f"- overall_status: `{report.get('overall_status')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        f"- generic002_input_path: `{report.get('generic002_input_path')}`",
        f"- expand003_input_path: `{report.get('expand003_input_path')}`",
        "",
        "## Safety boundary",
        "",
    ]
    for key, value in _mapping(report.get("safety_boundary")).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Summary", ""])
    summary = _mapping(report.get("summary"))
    for key in [
        "before_gap_count",
        "after_gap_count",
        "closed_gap_count",
        "still_blocked_gap_count",
        "positive_control_keys",
        "negative_control_keys",
        "closed_gap_ids",
        "still_blocked_gap_ids",
        "newly_detected_gap_ids",
    ]:
        lines.append(f"- {key}: `{summary.get(key)}`")
    lines.extend(["", "## Control rerun command", ""])
    command = report.get("control_rerun_command")
    lines.append(f"    {command}" if command else "No control rerun command available.")
    lines.extend(["", "## Generic-001 after rerun", ""])
    after = _mapping(report.get("generic001_after_summary"))
    for key in ["overall_status", "candidate_count", "passed_check_count", "failed_check_count", "failed_checks"]:
        lines.append(f"- {key}: `{after.get(key)}`")
    lines.extend(["", "## Remaining benchmark evidence requests", ""])
    requests = _mapping_list(report.get("remaining_benchmark_evidence_requests"))
    if requests:
        lines.append("| Gap | Evidence needed | Boundary |")
        lines.append("|---|---|---|")
        for item in requests:
            lines.append(f"| {item.get('gap_id')} | {item.get('evidence_needed')} | {item.get('boundary')} |")
    else:
        lines.append("No remaining benchmark evidence requests.")
    lines.extend(["", "## Next action", "", str(report.get("next_action") or ""), ""])
    return "\n".join(lines)


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "generic003_benchmark_control_rerun_review.json"
    md_path = output_dir / "generic003_benchmark_control_rerun_review.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    generic001_report = _mapping(report.get("generic001_after_report"))
    generic001_outputs = write_generic001_outputs(generic001_report, output_dir / "generic001_after_control_rerun")
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "generic001_after_json": generic001_outputs["json"],
        "generic001_after_csv": generic001_outputs["csv"],
        "generic001_after_markdown": generic001_outputs["markdown"],
    }


def _control_keys(closure_steps: Sequence[Mapping[str, Any]], gap_id: str) -> list[str]:
    keys: list[str] = []
    for step in closure_steps:
        if step.get("gap_id") != gap_id or step.get("status") != READY_STATUS:
            continue
        key = str(step.get("candidate_key") or "").strip()
        if key and key not in keys:
            keys.append(key)
    return keys


def _gap_ids_from_generic002(generic002_report: Mapping[str, Any], closure_steps: Sequence[Mapping[str, Any]]) -> list[str]:
    summary = _mapping(generic002_report.get("summary"))
    gaps = _string_list(summary.get("ready_to_close_gaps")) + _string_list(summary.get("blocked_gaps"))
    if not gaps:
        gaps = [str(step.get("gap_id")) for step in closure_steps if step.get("gap_id")]
    return sorted(set(gaps))


def _control_rerun_command(positive_control_keys: Sequence[str], negative_control_keys: Sequence[str]) -> str | None:
    if not positive_control_keys and not negative_control_keys:
        return None
    parts = ["python", "scripts/run_generic001_pipeline_generics_proof_gate.py"]
    for key in positive_control_keys:
        parts.extend(["--positive-control-key", key])
    for key in negative_control_keys:
        parts.extend(["--negative-control-key", key])
    return " ".join(parts)


def _generic001_summary(generic001_report: Mapping[str, Any]) -> dict[str, Any]:
    summary = _mapping(generic001_report.get("summary"))
    return {
        "overall_status": generic001_report.get("overall_status"),
        "candidate_count": summary.get("candidate_count"),
        "passed_check_count": summary.get("passed_check_count"),
        "failed_check_count": summary.get("failed_check_count"),
        "failed_checks": summary.get("failed_checks"),
        "gap_ids": generic001_report.get("gap_ids"),
    }


def _overall_status(
    *,
    positive_control_keys: Sequence[str],
    negative_control_keys: Sequence[str],
    closed_gap_ids: Sequence[str],
    after_gap_ids: Sequence[str],
) -> str:
    if not positive_control_keys and not negative_control_keys:
        return "no_control_keys_available"
    if not after_gap_ids:
        return "passed_all_control_and_generics_checks_review_artifact_only"
    if closed_gap_ids:
        return "partial_control_closure_remaining_benchmark_gaps"
    return "control_rerun_did_not_close_expected_gaps"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
