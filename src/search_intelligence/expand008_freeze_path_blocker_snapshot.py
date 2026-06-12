from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "expand008.freeze_path_blocker_snapshot.v1"
WORK_ITEM = "EXPAND-008 Freeze-Path Blocker Snapshot"
GENERIC005_SCHEMA_PREFIX = "generic005.stop_control_final_rerun"
EXPAND007_SCHEMA_PREFIX = "expand007.controlled_candidate_creation_apply_gate_readiness"
GENERIC006_SCHEMA_PREFIX = "generic006.stop_control_capture_repair_packet"


def no_mutation_boundary() -> dict[str, bool]:
    return {
        "review_artifact_only": True,
        "external_requests": False,
        "database_reads": False,
        "database_writes": False,
        "pipeline_mutation": False,
        "candidate_creation": False,
        "candidate_promotion": False,
        "gate_decision": False,
        "connector_activation": False,
        "scheduler_change": False,
        "bronze_silver_gold_mutation": False,
    }


def mutation_counts() -> dict[str, int]:
    return {
        "created_candidates": 0,
        "promoted_candidates": 0,
        "written_gate_decisions": 0,
        "activated_connectors": 0,
        "scheduler_changes": 0,
        "bronze_silver_gold_writes": 0,
        "database_writes": 0,
        "external_requests": 0,
    }


@dataclass(frozen=True)
class FreezePathGate:
    gate_id: str
    status: str
    source_status: str
    blocker: str
    next_action: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def load_json_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Input report must be a JSON object: {path}")
    return payload


def load_generic005_report(path: Path) -> dict[str, Any]:
    payload = load_json_report(path)
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(GENERIC005_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected GENERIC-005 schema_version: {schema_version or '<missing>'}")
    return payload


def load_expand007_report(path: Path) -> dict[str, Any]:
    payload = load_json_report(path)
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(EXPAND007_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected EXPAND-007 schema_version: {schema_version or '<missing>'}")
    return payload


def load_generic006_report(path: Path) -> dict[str, Any]:
    payload = load_json_report(path)
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(GENERIC006_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected GENERIC-006 schema_version: {schema_version or '<missing>'}")
    return payload


def find_latest_generic005_report(exports_dir: Path = Path("exports")) -> Path | None:
    return _find_latest_report(
        exports_dir,
        [
            "generic005_stop_control_final_rerun/generic005_stop_control_final_rerun.json",
            "generic005_stop_control_final_rerun_*/generic005_stop_control_final_rerun.json",
        ],
    )


def find_latest_expand007_report(exports_dir: Path = Path("exports")) -> Path | None:
    return _find_latest_report(
        exports_dir,
        [
            "expand007_controlled_candidate_creation_apply_gate_readiness/expand007_controlled_candidate_creation_apply_gate_readiness.json",
            "expand007_controlled_candidate_creation_apply_gate_readiness_*/expand007_controlled_candidate_creation_apply_gate_readiness.json",
        ],
    )


def find_latest_generic006_report(exports_dir: Path = Path("exports")) -> Path | None:
    return _find_latest_report(
        exports_dir,
        [
            "generic006_stop_control_capture_repair_packet/generic006_stop_control_capture_repair_packet.json",
            "generic006_stop_control_capture_repair_packet_*/generic006_stop_control_capture_repair_packet.json",
        ],
    )


def build_freeze_path_blocker_snapshot(
    generic005_report: Mapping[str, Any],
    expand007_report: Mapping[str, Any],
    generic006_report: Mapping[str, Any] | None = None,
    *,
    generic005_path: str | None = None,
    expand007_path: str | None = None,
    generic006_path: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    gates = build_gates(generic005_report, expand007_report, generic006_report)
    blocked = [gate for gate in gates if gate.status != "pass"]
    overall_status = "ready_for_expand004_rerun_review_only" if not blocked else "blocked_before_candidate_creation_apply_gate"
    progress = block_z_progress(gates)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "overall_status": overall_status,
        "generic005_input_path": generic005_path,
        "generic005_input_schema_version": generic005_report.get("schema_version"),
        "expand007_input_path": expand007_path,
        "expand007_input_schema_version": expand007_report.get("schema_version"),
        "generic006_input_path": generic006_path,
        "generic006_input_schema_version": generic006_report.get("schema_version") if generic006_report else None,
        "safety_boundary": no_mutation_boundary(),
        "mutation_counts": mutation_counts(),
        "interpretation_boundary": (
            "EXPAND-008 is a freeze-path blocker snapshot only. It summarizes which preceding review artifacts block "
            "candidate creation apply-gate work. It does not create candidates, write gates, activate connectors, mutate "
            "Bronze/Silver/Gold, change scheduler behavior, read the database, or call external services."
        ),
        "summary": {
            "block_z_label": "EXPAND / GENERIC / Candidate Creation",
            "block_z_progress_numerator": progress[0],
            "block_z_progress_denominator": progress[1],
            "blocked_gate_count": len(blocked),
            "first_blocking_gate_id": blocked[0].gate_id if blocked else None,
            "generic005_overall_status": generic005_report.get("overall_status"),
            "generic006_overall_status": generic006_report.get("overall_status") if generic006_report else "missing_not_run_yet",
            "expand007_overall_status": expand007_report.get("overall_status"),
            "candidate_creation_apply_allowed": False,
        },
        "freeze_path_gates": [gate.as_dict() for gate in gates],
        "next_action": build_next_action(blocked),
    }


def build_gates(
    generic005_report: Mapping[str, Any],
    expand007_report: Mapping[str, Any],
    generic006_report: Mapping[str, Any] | None,
) -> list[FreezePathGate]:
    generic005_status = str(generic005_report.get("overall_status") or "missing")
    generic006_status = str(generic006_report.get("overall_status") if generic006_report else "missing_not_run_yet")
    expand007_status = str(expand007_report.get("overall_status") or "missing")

    gates: list[FreezePathGate] = []
    gates.append(
        FreezePathGate(
            gate_id="generic005_stop_control_final_rerun",
            status="pass" if generic005_status == "passed_all_generics_checks_review_artifact_only" else "blocked",
            source_status=generic005_status,
            blocker="stop_control_capture_not_accepted" if generic005_status != "passed_all_generics_checks_review_artifact_only" else "-",
            next_action="repair_stop_control_capture_and_rerun_generic005" if generic005_status != "passed_all_generics_checks_review_artifact_only" else "rerun_expand004_with_passed_generics",
        )
    )
    gates.append(
        FreezePathGate(
            gate_id="generic006_stop_control_capture_repair_packet",
            status="pass" if generic006_status == "ready_for_generic005_rerun_after_operator_review" else "blocked",
            source_status=generic006_status,
            blocker="operator_capture_repair_required_or_report_missing" if generic006_status != "ready_for_generic005_rerun_after_operator_review" else "-",
            next_action="run_generic006_and_fix_capture_csv" if generic006_status != "ready_for_generic005_rerun_after_operator_review" else "rerun_generic005_with_reviewed_capture_csv",
        )
    )
    gates.append(
        FreezePathGate(
            gate_id="expand007_apply_gate_readiness",
            status="pass" if expand007_status == "ready_for_manual_apply_gate_design_review_not_apply" else "blocked",
            source_status=expand007_status,
            blocker="apply_gate_readiness_blocked" if expand007_status != "ready_for_manual_apply_gate_design_review_not_apply" else "-",
            next_action="rerun_expand007_after_generic005_and_expand004_refresh" if expand007_status != "ready_for_manual_apply_gate_design_review_not_apply" else "design_manual_apply_gate_preview_only",
        )
    )
    return gates


def block_z_progress(gates: Sequence[FreezePathGate]) -> tuple[float, int]:
    # EXPAND-007 gave the block a 6.5/8 status. GENERIC-006/EXPAND-008 do not unlock apply by themselves;
    # they make the blocking state executable and reviewable. Once all gates pass, the next block can move to 7/8.
    if all(gate.status == "pass" for gate in gates):
        return (7.0, 8)
    return (6.5, 8)


def build_next_action(blocked_gates: Sequence[FreezePathGate]) -> str:
    if not blocked_gates:
        return "Rerun EXPAND-004 and EXPAND-007 with refreshed evidence; then design manual apply-gate preview only."
    first = blocked_gates[0]
    if first.gate_id == "generic005_stop_control_final_rerun":
        return "Run GENERIC-006, repair the stop-control capture CSV, rerun GENERIC-005, then rerun EXPAND-004 and EXPAND-007."
    if first.gate_id == "generic006_stop_control_capture_repair_packet":
        return "Run GENERIC-006 or repair the capture CSV until it is ready for GENERIC-005 rerun."
    return first.next_action


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = _mapping(report.get("summary"))
    lines = [
        "# EXPAND-008 Freeze-Path Blocker Snapshot",
        "",
        f"- overall_status: `{report.get('overall_status')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        f"- generic005_input_path: `{report.get('generic005_input_path')}`",
        f"- generic006_input_path: `{report.get('generic006_input_path')}`",
        f"- expand007_input_path: `{report.get('expand007_input_path')}`",
        "",
        "## Summary",
        "",
    ]
    for key in [
        "block_z_label",
        "block_z_progress_numerator",
        "block_z_progress_denominator",
        "blocked_gate_count",
        "first_blocking_gate_id",
        "generic005_overall_status",
        "generic006_overall_status",
        "expand007_overall_status",
        "candidate_creation_apply_allowed",
    ]:
        lines.append(f"- {key}: `{summary.get(key)}`")
    lines.extend(["", "## Freeze-path gates", ""])
    lines.append("| Gate | Status | Source status | Blocker | Next action |")
    lines.append("|---|---|---|---|---|")
    for gate in _mapping_list(report.get("freeze_path_gates")):
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(gate.get("gate_id")),
                    _md_cell(gate.get("status")),
                    _md_cell(gate.get("source_status")),
                    _md_cell(gate.get("blocker")),
                    _md_cell(gate.get("next_action")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Safety boundary", ""])
    for key, value in _mapping(report.get("safety_boundary")).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Next action", "", str(report.get("next_action") or ""), ""])
    return "\n".join(lines)


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "expand008_freeze_path_blocker_snapshot.json"
    md_path = output_dir / "expand008_freeze_path_blocker_snapshot.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _find_latest_report(exports_dir: Path, patterns: Sequence[str]) -> Path | None:
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(path for path in exports_dir.glob(pattern) if path.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda path: (_timestamp_from_parent(path), path.stat().st_mtime, str(path)))


def _timestamp_from_parent(path: Path) -> str:
    parent = path.parent.name
    for prefix in (
        "generic005_stop_control_final_rerun_",
        "generic006_stop_control_capture_repair_packet_",
        "expand007_controlled_candidate_creation_apply_gate_readiness_",
    ):
        if parent.startswith(prefix):
            return parent.removeprefix(prefix)
    return ""


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _md_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
