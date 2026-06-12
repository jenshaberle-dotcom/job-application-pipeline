from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "expand007.controlled_candidate_creation_apply_gate_readiness.v1"
WORK_ITEM = "EXPAND-007 Controlled Candidate Creation Apply-Gate Readiness"
EXPAND004_SCHEMA_PREFIX = "expand004.controlled_candidate_creation_dry_run"
EXPAND006_SCHEMA_PREFIX = "expand006.candidate_creation_evidence_review"

EXPAND004_READY_STATUS = "ready_for_operator_candidate_creation_dry_run_review"
EXPAND006_EXPECTED_BOUNDARY = "review_only_not_apply"

APPLY_GATE_DESIGN_STATUS = "ready_for_manual_apply_gate_design_review_not_apply"
BLOCKED_STATUS = "blocked_before_apply_gate_design"
NO_CANDIDATES_STATUS = "blocked_no_selected_candidate_creation_dry_run_items"


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
class ApplyGateCandidateAssessment:
    company_key: str
    company_name: str
    dry_run_lane: str
    dry_run_readiness: str
    selected_for_creation_dry_run: bool
    planned_candidate_action: str
    apply_gate_readiness: str
    blocker_reasons: tuple[str, ...]
    required_operator_checks: tuple[str, ...]
    required_apply_artifacts: tuple[str, ...]
    next_action: str
    candidate_creation_allowed_by_this_report: bool = False
    apply_execution_allowed_by_this_report: bool = False
    automatic_promotion_allowed_by_this_report: bool = False
    gate_decision_allowed_by_this_report: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["blocker_reasons"] = list(self.blocker_reasons)
        data["required_operator_checks"] = list(self.required_operator_checks)
        data["required_apply_artifacts"] = list(self.required_apply_artifacts)
        return data


def load_json_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Input report must be a JSON object: {path}")
    return payload


def load_expand004_report(path: Path) -> dict[str, Any]:
    payload = load_json_report(path)
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(EXPAND004_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected EXPAND-004 schema_version: {schema_version or '<missing>'}")
    return payload


def load_expand006_report(path: Path) -> dict[str, Any]:
    payload = load_json_report(path)
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(EXPAND006_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected EXPAND-006 schema_version: {schema_version or '<missing>'}")
    return payload


def find_latest_expand004_report(exports_dir: Path = Path("exports")) -> Path | None:
    return _find_latest_report(
        exports_dir,
        [
            "expand004_controlled_candidate_creation_dry_run/expand004_controlled_candidate_creation_dry_run.json",
            "expand004_controlled_candidate_creation_dry_run_*/expand004_controlled_candidate_creation_dry_run.json",
        ],
    )


def find_latest_expand006_report(exports_dir: Path = Path("exports")) -> Path | None:
    return _find_latest_report(
        exports_dir,
        [
            "expand006_candidate_creation_evidence_review_*.json",
            "expand006_candidate_creation_evidence_review/expand006_candidate_creation_evidence_review.json",
            "expand006_candidate_creation_evidence_review_*/expand006_candidate_creation_evidence_review.json",
        ],
    )


def build_apply_gate_readiness_report(
    expand004_report: Mapping[str, Any],
    expand006_report: Mapping[str, Any],
    *,
    expand004_path: str | None = None,
    expand006_path: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    summary004 = _mapping(expand004_report.get("summary"))
    apply_boundary006 = _mapping(expand006_report.get("apply_boundary"))
    database006 = _mapping(expand006_report.get("database"))

    candidate_items = _mapping_list(expand004_report.get("candidate_creation_dry_run_items"))
    selected_items = [item for item in candidate_items if bool(item.get("selected_for_creation_dry_run"))]
    generic_gap_ids = _string_list(summary004.get("generic001_final_gap_ids"))

    context = {
        "expand004_overall_status": expand004_report.get("overall_status"),
        "expand004_generics_ready": bool(summary004.get("generics_ready_for_candidate_creation_dry_run")),
        "expand004_selected_count": len(selected_items),
        "generic_gap_ids": generic_gap_ids,
        "expand006_database_status": database006.get("status"),
        "expand006_review_signal_strength": apply_boundary006.get("review_signal_strength"),
        "expand006_decision_boundary": apply_boundary006.get("decision_boundary"),
    }
    assessments = [build_candidate_assessment(item, context) for item in candidate_items]
    overall_status = derive_overall_status(context, assessments)
    summary = build_summary(context, assessments)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "overall_status": overall_status,
        "expand004_input_path": expand004_path,
        "expand004_input_schema_version": expand004_report.get("schema_version"),
        "expand004_input_overall_status": expand004_report.get("overall_status"),
        "expand006_input_path": expand006_path,
        "expand006_input_schema_version": expand006_report.get("schema_version"),
        "expand006_input_database_status": database006.get("status"),
        "safety_boundary": no_mutation_boundary(),
        "mutation_counts": mutation_counts(),
        "interpretation_boundary": (
            "EXPAND-007 is an apply-gate readiness report, not an apply command. It combines the EXPAND-004 dry-run "
            "manifest with the EXPAND-006 evidence review and decides whether a separate manual apply-gate design may be "
            "started. It never creates candidates, writes gates, activates connectors, mutates Bronze/Silver/Gold, changes "
            "scheduler behavior, reads the database itself, or performs external requests."
        ),
        "apply_gate_boundary": build_apply_gate_boundary(overall_status, context),
        "summary": summary,
        "candidate_apply_gate_assessments": [assessment.as_dict() for assessment in assessments],
        "next_action": build_next_action(overall_status, summary),
    }


def build_candidate_assessment(
    item: Mapping[str, Any],
    context: Mapping[str, Any],
) -> ApplyGateCandidateAssessment:
    company_key = _text(item.get("company_key"), default="unknown_company")
    company_name = _text(item.get("company_name"), default=company_key)
    dry_run_lane = _text(item.get("dry_run_lane"), default="unknown_lane")
    dry_run_readiness = _text(item.get("dry_run_readiness"), default="unknown_readiness")
    selected = bool(item.get("selected_for_creation_dry_run"))
    planned_action = _text(item.get("planned_candidate_action"), default="unknown_planned_action")

    blockers = candidate_blocker_reasons(item, context)
    readiness = "ready_for_manual_apply_gate_design_review" if selected and not blockers else "blocked_for_apply_gate_design"
    next_action = (
        "include_in_manual_apply_gate_design_preview"
        if readiness == "ready_for_manual_apply_gate_design_review"
        else "resolve_blockers_before_apply_gate_design"
    )

    return ApplyGateCandidateAssessment(
        company_key=company_key,
        company_name=company_name,
        dry_run_lane=dry_run_lane,
        dry_run_readiness=dry_run_readiness,
        selected_for_creation_dry_run=selected,
        planned_candidate_action=planned_action,
        apply_gate_readiness=readiness,
        blocker_reasons=tuple(blockers),
        required_operator_checks=tuple(_required_operator_checks(item, context)),
        required_apply_artifacts=tuple(_required_apply_artifacts(item, context)),
        next_action=next_action,
    )


def candidate_blocker_reasons(item: Mapping[str, Any], context: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if context.get("expand004_overall_status") != EXPAND004_READY_STATUS:
        blockers.append("expand004_not_ready_for_candidate_creation_dry_run_review")
    if not context.get("expand004_generics_ready"):
        blockers.append("generic005_final_rerun_not_passed")
    if _string_list(context.get("generic_gap_ids")):
        blockers.append("generic_proof_gaps_remain")
    if not bool(item.get("selected_for_creation_dry_run")):
        blockers.append("not_selected_in_expand004_dry_run_manifest")
    if _text(item.get("dry_run_readiness")) not in {
        "ready_for_operator_creation_preview",
        "ready_for_operator_creation_preview_with_detail_followup",
    }:
        blockers.append("dry_run_item_not_creation_preview_ready")
    if context.get("expand006_decision_boundary") != EXPAND006_EXPECTED_BOUNDARY:
        blockers.append("expand006_apply_boundary_missing_or_unexpected")
    if context.get("expand006_review_signal_strength") != "inspectable":
        blockers.append("expand006_evidence_review_not_db_inspectable")
    return _unique(blockers)


def derive_overall_status(context: Mapping[str, Any], assessments: Sequence[ApplyGateCandidateAssessment]) -> str:
    if context.get("expand004_overall_status") != EXPAND004_READY_STATUS:
        return BLOCKED_STATUS
    if not assessments or not any(item.selected_for_creation_dry_run for item in assessments):
        return NO_CANDIDATES_STATUS
    if any(not item.blocker_reasons for item in assessments if item.selected_for_creation_dry_run):
        return APPLY_GATE_DESIGN_STATUS
    return BLOCKED_STATUS


def build_apply_gate_boundary(overall_status: str, context: Mapping[str, Any]) -> dict[str, Any]:
    design_allowed = overall_status == APPLY_GATE_DESIGN_STATUS
    return {
        "decision_boundary": "apply_gate_readiness_not_apply_execution",
        "apply_gate_design_allowed_by_this_report": design_allowed,
        "candidate_creation_execution_allowed_by_this_report": False,
        "operator_confirmation_required_before_any_future_write": True,
        "separate_apply_command_required": True,
        "expected_future_apply_mode": "dry_run_first_then_explicit_apply_only_after_review",
        "minimum_requirements_before_future_apply_execution": [
            "EXPAND-004 selected candidate creation dry-run items exist",
            "GENERIC-005 / GENERIC-001 final proof gaps are closed",
            "EXPAND-006 evidence review has inspectable DB-backed signal",
            "duplicate and normalization risk is reviewed for each selected candidate",
            "operator explicitly approves the exact candidate keys and intended write scope",
            "future apply command writes only candidate-review state and audit evidence, not connector activation or scheduler state",
        ],
        "current_blockers": derive_global_blockers(context),
    }


def derive_global_blockers(context: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if context.get("expand004_overall_status") != EXPAND004_READY_STATUS:
        blockers.append("EXPAND-004 is not ready")
    if not context.get("expand004_generics_ready"):
        blockers.append("GENERIC-005 final rerun has not passed")
    gap_ids = _string_list(context.get("generic_gap_ids"))
    if gap_ids:
        blockers.append("Generic proof gaps remain: " + ", ".join(gap_ids))
    if int(context.get("expand004_selected_count") or 0) <= 0:
        blockers.append("No selected candidate creation dry-run items")
    if context.get("expand006_review_signal_strength") != "inspectable":
        blockers.append("EXPAND-006 evidence review is not DB-inspectable")
    return blockers


def build_summary(
    context: Mapping[str, Any],
    assessments: Sequence[ApplyGateCandidateAssessment],
) -> dict[str, Any]:
    readiness_counts = Counter(item.apply_gate_readiness for item in assessments)
    lane_counts = Counter(item.dry_run_lane for item in assessments)
    selected = [item.company_key for item in assessments if item.selected_for_creation_dry_run]
    ready_for_design = [item.company_key for item in assessments if not item.blocker_reasons]
    blocker_counts = Counter(reason for item in assessments for reason in item.blocker_reasons)
    return {
        "candidate_assessment_count": len(assessments),
        "selected_candidate_creation_dry_run_count": len(selected),
        "selected_candidate_creation_dry_run_keys": selected,
        "ready_for_manual_apply_gate_design_count": len(ready_for_design),
        "ready_for_manual_apply_gate_design_keys": ready_for_design,
        "blocked_candidate_count": sum(1 for item in assessments if item.blocker_reasons),
        "readiness_counts": dict(sorted(readiness_counts.items())),
        "lane_counts": dict(sorted(lane_counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "generic_gap_ids": _string_list(context.get("generic_gap_ids")),
        "expand004_overall_status": context.get("expand004_overall_status"),
        "expand006_database_status": context.get("expand006_database_status"),
        "expand006_review_signal_strength": context.get("expand006_review_signal_strength"),
        "mutation_counts": mutation_counts(),
    }


def build_next_action(overall_status: str, summary: Mapping[str, Any]) -> str:
    if overall_status == APPLY_GATE_DESIGN_STATUS:
        keys = ", ".join(_string_list(summary.get("ready_for_manual_apply_gate_design_keys"))) or "<none>"
        return (
            "Design the separate controlled candidate creation apply gate for the listed keys only, still dry-run first and "
            f"without connector activation: {keys}."
        )
    gap_ids = _string_list(summary.get("generic_gap_ids"))
    if gap_ids:
        return (
            "Do not design or run candidate creation apply yet. Close generic proof gaps first: "
            + ", ".join(gap_ids)
            + "."
        )
    if int(summary.get("selected_candidate_creation_dry_run_count") or 0) <= 0:
        return "Do not design apply yet. Rerun EXPAND-004 only after the generic proof chain can select dry-run candidates."
    return "Do not apply. Review EXPAND-006 evidence strength and candidate blockers before designing the apply gate."


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = _mapping(report.get("summary"))
    boundary = _mapping(report.get("apply_gate_boundary"))
    lines = [
        "# EXPAND-007 Controlled Candidate Creation Apply-Gate Readiness",
        "",
        f"Generated: `{report.get('generated_at_utc')}`",
        f"Overall status: `{report.get('overall_status')}`",
        "",
        "## Boundary",
        "",
        f"- Decision boundary: `{boundary.get('decision_boundary')}`",
        f"- Apply-gate design allowed: `{boundary.get('apply_gate_design_allowed_by_this_report')}`",
        f"- Candidate creation execution allowed: `{boundary.get('candidate_creation_execution_allowed_by_this_report')}`",
        f"- Separate apply command required: `{boundary.get('separate_apply_command_required')}`",
        "",
        "## Summary",
        "",
        f"- Candidate assessments: `{summary.get('candidate_assessment_count')}`",
        f"- Selected dry-run candidates: `{summary.get('selected_candidate_creation_dry_run_count')}`",
        f"- Ready for manual apply-gate design: `{summary.get('ready_for_manual_apply_gate_design_count')}`",
        f"- Generic gap IDs: `{summary.get('generic_gap_ids')}`",
        f"- EXPAND-004 status: `{summary.get('expand004_overall_status')}`",
        f"- EXPAND-006 database status: `{summary.get('expand006_database_status')}`",
        f"- EXPAND-006 review signal: `{summary.get('expand006_review_signal_strength')}`",
        "",
        "## Global blockers",
        "",
    ]
    blockers = _string_list(boundary.get("current_blockers"))
    if blockers:
        lines.extend([f"- {blocker}" for blocker in blockers])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Candidate assessments",
            "",
            "| Company | Selected | Apply-gate readiness | Blockers |",
            "| --- | ---: | --- | --- |",
        ]
    )
    for item in _mapping_list(report.get("candidate_apply_gate_assessments")):
        blockers_text = ", ".join(_string_list(item.get("blocker_reasons"))) or "none"
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{_md_cell(item.get('company_key'))}`",
                    str(item.get("selected_for_creation_dry_run")),
                    f"`{_md_cell(item.get('apply_gate_readiness'))}`",
                    _md_cell(blockers_text),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Next action",
            "",
            str(report.get("next_action")),
            "",
            "This report is intentionally not an apply mechanism. It may only authorize a future apply-gate design review, never candidate creation execution.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "expand007_controlled_candidate_creation_apply_gate_readiness.json"
    csv_path = output_dir / "expand007_candidate_apply_gate_readiness.csv"
    md_path = output_dir / "expand007_controlled_candidate_creation_apply_gate_readiness.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_assessments_csv(csv_path, _mapping_list(report.get("candidate_apply_gate_assessments")))
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def write_assessments_csv(path: Path, assessments: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = [
        "company_key",
        "company_name",
        "dry_run_lane",
        "dry_run_readiness",
        "selected_for_creation_dry_run",
        "apply_gate_readiness",
        "blocker_reasons",
        "next_action",
        "candidate_creation_allowed_by_this_report",
        "apply_execution_allowed_by_this_report",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for assessment in assessments:
            row = {key: assessment.get(key) for key in fieldnames}
            row["blocker_reasons"] = ";".join(_string_list(assessment.get("blocker_reasons")))
            writer.writerow(row)


def _required_operator_checks(item: Mapping[str, Any], context: Mapping[str, Any]) -> list[str]:
    checks = _string_list(item.get("required_operator_checks"))
    checks.extend(
        [
            "confirm_exact_candidate_key_scope_before_future_apply",
            "confirm_no_candidate_or_gate_mutation_in_readiness_report",
            "confirm_future_apply_command_has_dry_run_mode",
        ]
    )
    if context.get("expand006_review_signal_strength") != "inspectable":
        checks.append("rerun_expand006_with_db_available_before_apply_gate_design")
    return _unique(checks)


def _required_apply_artifacts(item: Mapping[str, Any], context: Mapping[str, Any]) -> list[str]:
    artifacts = _string_list(item.get("expected_artifacts"))
    artifacts.extend(
        [
            "operator_approval_token_preview",
            "candidate_identity_duplicate_check",
            "future_apply_audit_record_plan",
            "rollback_or_disable_plan_before_any_future_write",
        ]
    )
    if _string_list(context.get("generic_gap_ids")):
        artifacts.append("closed_generic_proof_gap_evidence")
    return _unique(artifacts)


def _find_latest_report(exports_dir: Path, patterns: Sequence[str]) -> Path | None:
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(path for path in exports_dir.glob(pattern) if path.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda path: (_timestamp_from_path(path), path.stat().st_mtime, str(path)))


def _timestamp_from_path(path: Path) -> str:
    match_text = str(path)
    # Keep this parser intentionally simple and stable: YYYYMMDD-HHMMSS or YYYYMMDD-HHMM inside path names.
    import re

    matches = re.findall(r"(20\d{6}-\d{4,6})", match_text)
    return matches[-1] if matches else ""


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [str(item) for item in value if str(item).strip()]


def _unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _text(value: Any, *, default: str = "") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
