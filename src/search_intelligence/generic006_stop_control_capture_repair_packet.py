from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "generic006.stop_control_capture_repair_packet.v2"
WORK_ITEM = "GENERIC-006 Stop-Control Evidence Repair Packet"
GENERIC004_SCHEMA_PREFIX = "generic004.stop_control_evidence_capture_plan"
GENERIC005_SCHEMA_PREFIX = "generic005.stop_control_final_rerun"

STOP_CONTROL_GAPS = ("no_actionable_evidence_coverage", "negative_control_coverage")
SAFE_STOP_ACTIONS = frozenset(
    {
        "no_useful_external_hint_no_candidate_creation",
        "provider_auth_failed_requires_key_review",
        "probe_error_requires_retry_or_review",
    }
)
EXPLICIT_STOP_CONTROL_TYPES = frozenset(
    {
        "new_clean_no_actionable_negative_control",
        "existing_safe_stop_negative_control",
    }
)
BOUNDARY = "review_artifact_only_no_candidate_or_gate_write"
PLACEHOLDER_SUMMARY_PREFIX = "describe why no company-origin/detail/provider evidence"

READY_STATUS = "ready_for_generic005_rerun_after_operator_review"
BLOCKED_STATUS = "operator_stop_control_capture_repair_required"
NO_ROWS_STATUS = "blocked_no_capture_rows_found"


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
class CaptureRepairAssessment:
    row_number: int
    control_type: str
    company_key: str
    company_name: str
    review_action: str
    evidence_strength: str
    required_for_gap_ids: tuple[str, ...]
    missing_or_invalid_fields: tuple[str, ...]
    repair_status: str
    repair_instruction: str
    reviewer: str = ""
    review_date: str = ""
    boundary: str = ""
    evidence_summary_preview: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["required_for_gap_ids"] = list(self.required_for_gap_ids)
        data["missing_or_invalid_fields"] = list(self.missing_or_invalid_fields)
        return data


def load_json_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Input report must be a JSON object: {path}")
    return payload


def load_generic004_report(path: Path) -> dict[str, Any]:
    payload = load_json_report(path)
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(GENERIC004_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected GENERIC-004 schema_version: {schema_version or '<missing>'}")
    return payload


def load_generic005_report(path: Path) -> dict[str, Any]:
    payload = load_json_report(path)
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(GENERIC005_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected GENERIC-005 schema_version: {schema_version or '<missing>'}")
    return payload


def find_latest_generic004_report(exports_dir: Path = Path("exports")) -> Path | None:
    return _find_latest_report(
        exports_dir,
        [
            "generic004_stop_control_evidence_capture_plan/generic004_stop_control_evidence_capture_plan.json",
            "generic004_stop_control_evidence_capture_plan_*/generic004_stop_control_evidence_capture_plan.json",
        ],
    )


def find_latest_generic005_report(exports_dir: Path = Path("exports")) -> Path | None:
    return _find_latest_report(
        exports_dir,
        [
            "generic005_stop_control_final_rerun/generic005_stop_control_final_rerun.json",
            "generic005_stop_control_final_rerun_*/generic005_stop_control_final_rerun.json",
        ],
    )


def stop_control_rows_from_generic004_report(generic004_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = _mapping_list(generic004_report.get("stop_control_evidence_requirements"))
    if rows:
        return rows
    return _mapping_list(generic004_report.get("capture_template_rows"))


def build_stop_control_capture_repair_packet(
    generic004_report: Mapping[str, Any],
    generic005_report: Mapping[str, Any],
    stop_control_rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    generic004_path: str | None = None,
    generic005_path: str | None = None,
    stop_control_source: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    rows = list(stop_control_rows) if stop_control_rows is not None else stop_control_rows_from_generic004_report(generic004_report)
    assessments = [assess_capture_row(row, index + 1) for index, row in enumerate(rows)]
    ready_rows = [row for row in assessments if row.repair_status == "ready_for_generic005_rerun"]
    blocked_rows = [row for row in assessments if row.repair_status != "ready_for_generic005_rerun"]
    missing_counter = Counter(field for row in assessments for field in row.missing_or_invalid_fields)
    overall_status = derive_overall_status(assessments)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "overall_status": overall_status,
        "generic004_input_path": generic004_path,
        "generic004_input_schema_version": generic004_report.get("schema_version"),
        "generic004_input_overall_status": generic004_report.get("overall_status"),
        "generic005_input_path": generic005_path,
        "generic005_input_schema_version": generic005_report.get("schema_version"),
        "generic005_input_overall_status": generic005_report.get("overall_status"),
        "stop_control_source": stop_control_source or "generic004_report_stop_control_evidence_requirements",
        "safety_boundary": no_mutation_boundary(),
        "mutation_counts": mutation_counts(),
        "interpretation_boundary": (
            "GENERIC-006 is a repair packet for DB/code-backed operator stop-control evidence only. It diagnoses missing or invalid "
            "fields in the GENERIC-004 evidence requirements and tells the operator what must be modeled before rerunning "
            "GENERIC-005. It never fills evidence on behalf of the operator, creates candidates, writes gates, reads "
            "CSV/Excel/export files as process input, calls external services, mutates Bronze/Silver/Gold, activates connectors, or changes the scheduler."
        ),
        "summary": {
            "capture_row_count": len(assessments),
            "ready_for_generic005_rerun_count": len(ready_rows),
            "blocked_capture_row_count": len(blocked_rows),
            "missing_or_invalid_field_counts": dict(sorted(missing_counter.items())),
            "generic004_overall_status": generic004_report.get("overall_status"),
            "generic005_overall_status": generic005_report.get("overall_status"),
            "generic005_final_gap_ids": _string_list(_mapping(generic005_report.get("summary")).get("final_gap_ids")),
            "generic005_rejected_stop_control_count": _mapping(generic005_report.get("summary")).get("rejected_stop_control_count"),
            "generic005_accepted_stop_control_count": _mapping(generic005_report.get("summary")).get("accepted_stop_control_count"),
            "safe_rerun_command_available": bool(ready_rows),
        },
        "manual_repair_checklist": manual_repair_checklist(),
        "capture_repair_assessments": [row.as_dict() for row in assessments],
        "blocked_field_help": blocked_field_help(),
        "safe_rerun_command": build_safe_rerun_command() if ready_rows else None,
        "next_action": build_next_action(overall_status),
    }


def assess_capture_row(row: Mapping[str, Any], row_number: int) -> CaptureRepairAssessment:
    control_type = _text(row.get("control_type"))
    required_for_gap_ids = tuple(_split_gap_ids(row.get("required_for_gap_ids")))
    company_key = _text(row.get("company_key"))
    company_name = _text(row.get("company_name"))
    review_action = _text(row.get("review_action"))
    evidence_strength = _text(row.get("evidence_strength"), default="none")
    evidence_summary = _text(row.get("evidence_summary"))
    reviewer = _text(row.get("reviewer"))
    review_date = _text(row.get("review_date"))
    boundary = _text(row.get("boundary"))

    missing: list[str] = []
    if control_type not in EXPLICIT_STOP_CONTROL_TYPES:
        missing.append("control_type")
    if set(STOP_CONTROL_GAPS) - set(required_for_gap_ids):
        missing.append("required_for_gap_ids")
    if not company_key:
        missing.append("company_key")
    if not company_name:
        missing.append("company_name")
    if review_action not in SAFE_STOP_ACTIONS:
        missing.append("review_action")
    if not evidence_summary or evidence_summary.lower().startswith(PLACEHOLDER_SUMMARY_PREFIX):
        missing.append("evidence_summary")
    if not reviewer:
        missing.append("reviewer")
    if not review_date:
        missing.append("review_date")
    if boundary != BOUNDARY:
        missing.append("boundary")

    repair_status = "ready_for_generic005_rerun" if not missing else "operator_repair_required"
    return CaptureRepairAssessment(
        row_number=row_number,
        control_type=control_type,
        company_key=company_key,
        company_name=company_name,
        review_action=review_action,
        evidence_strength=evidence_strength,
        required_for_gap_ids=required_for_gap_ids,
        missing_or_invalid_fields=tuple(missing),
        repair_status=repair_status,
        repair_instruction=build_row_repair_instruction(missing),
        reviewer=reviewer,
        review_date=review_date,
        boundary=boundary,
        evidence_summary_preview=evidence_summary[:160],
    )


def derive_overall_status(assessments: Sequence[CaptureRepairAssessment]) -> str:
    if not assessments:
        return NO_ROWS_STATUS
    if any(row.repair_status == "ready_for_generic005_rerun" for row in assessments):
        return READY_STATUS
    return BLOCKED_STATUS


def build_row_repair_instruction(missing_fields: Sequence[str]) -> str:
    if not missing_fields:
        return "Row is structurally ready for GENERIC-005 rerun from DB/code-backed evidence."
    return "Model or correct these fields in DB-backed or code-backed stop-control evidence before rerunning GENERIC-005: " + ", ".join(missing_fields) + "."


def manual_repair_checklist() -> list[dict[str, str]]:
    return [
        {
            "step_id": "choose_clean_negative_control",
            "required": "true",
            "description": "Select one company that is explicitly a no-actionable/safe-stop control from DB-backed or code-backed review evidence, not a weak positive or ambiguous origin candidate.",
        },
        {
            "step_id": "fill_identity_fields",
            "required": "true",
            "description": "Model company_key and company_name exactly as the reviewed evidence should be referenced; do not use literal None/null placeholders.",
        },
        {
            "step_id": "write_evidence_summary",
            "required": "true",
            "description": "Persist or code-review a concise operator-written explanation of why no actionable origin/detail/provider evidence exists.",
        },
        {
            "step_id": "record_reviewer_and_date",
            "required": "true",
            "description": "Record reviewer and ISO-style review_date so the stop-control evidence is auditable.",
        },
        {
            "step_id": "keep_boundary",
            "required": "true",
            "description": f"Keep boundary exactly `{BOUNDARY}`; this remains benchmark evidence only, not candidate creation or gate truth.",
        },
    ]


def blocked_field_help() -> dict[str, str]:
    return {
        "control_type": "Use new_clean_no_actionable_negative_control or existing_safe_stop_negative_control.",
        "required_for_gap_ids": "Must include both no_actionable_evidence_coverage and negative_control_coverage.",
        "company_key": "Required explicit stable key for the reviewed negative-control company.",
        "company_name": "Required human-readable company name for the reviewed negative-control company.",
        "review_action": "Must be one of the safe-stop actions; weak-only signals are not accepted.",
        "evidence_summary": "Must be operator-written evidence; the placeholder text is rejected.",
        "reviewer": "Required for auditability.",
        "review_date": "Required for auditability.",
        "boundary": f"Must remain {BOUNDARY}.",
    }


def build_safe_rerun_command() -> str:
    return "python scripts/run_generic005_stop_control_final_rerun.py"


def build_next_action(overall_status: str) -> str:
    if overall_status == READY_STATUS:
        return "Rerun GENERIC-005 with DB/code-backed stop-control evidence, then rerun EXPAND-004 and EXPAND-007 before any apply-gate design."
    if overall_status == NO_ROWS_STATUS:
        return "Model one explicit DB-backed or code-backed safe-stop/no-actionable negative-control row; do not use CSV/Excel/export handoffs."
    return "Repair the DB/code-backed stop-control evidence fields listed in this packet, rerun GENERIC-005, then rerun EXPAND-004 and EXPAND-007."


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = _mapping(report.get("summary"))
    lines = [
        "# GENERIC-006 Stop-Control Evidence Repair Packet",
        "",
        f"- overall_status: `{report.get('overall_status')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        f"- generic004_input_path: `{report.get('generic004_input_path')}`",
        f"- generic005_input_path: `{report.get('generic005_input_path')}`",
        f"- stop_control_source: `{report.get('stop_control_source')}`",
        "",
        "## Safety boundary",
        "",
    ]
    for key, value in _mapping(report.get("safety_boundary")).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Summary", ""])
    for key in [
        "capture_row_count",
        "ready_for_generic005_rerun_count",
        "blocked_capture_row_count",
        "missing_or_invalid_field_counts",
        "generic005_final_gap_ids",
        "safe_rerun_command_available",
    ]:
        lines.append(f"- {key}: `{summary.get(key)}`")
    lines.extend(["", "## Manual repair checklist", ""])
    for item in _mapping_list(report.get("manual_repair_checklist")):
        lines.append(f"- `{item.get('step_id')}`: {item.get('description')}")
    lines.extend(["", "## Stop-control evidence repair assessments", ""])
    lines.append("| Row | Company | Status | Missing/invalid fields | Instruction |")
    lines.append("|---:|---|---|---|---|")
    assessments = _mapping_list(report.get("capture_repair_assessments"))
    if assessments:
        for item in assessments:
            fields = "; ".join(_string_list(item.get("missing_or_invalid_fields"))) or "-"
            company = item.get("company_name") or item.get("company_key") or "-"
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md_cell(item.get("row_number")),
                        _md_cell(company),
                        _md_cell(item.get("repair_status")),
                        _md_cell(fields),
                        _md_cell(item.get("repair_instruction")),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| - | - | blocked_no_capture_rows_found | - | No DB/code-backed stop-control rows were found. |")
    lines.extend(["", "## Safe rerun command", ""])
    lines.append(str(report.get("safe_rerun_command") or "No rerun command is available until at least one row is structurally ready."))
    lines.extend(["", "## Next action", "", str(report.get("next_action") or ""), ""])
    return "\n".join(lines)


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "generic006_stop_control_capture_repair_packet.json"
    md_path = output_dir / "generic006_stop_control_capture_repair_packet.md"
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
        "generic004_stop_control_evidence_capture_plan_",
        "generic005_stop_control_final_rerun_",
    ):
        if parent.startswith(prefix):
            return parent.removeprefix(prefix)
    return ""


def _split_gap_ids(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = value.replace(",", ";").split(";")
        return [item.strip() for item in raw if item.strip()]
    return _string_list(value)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        return []
    return [str(item) for item in value if str(item).strip()]


def _text(value: Any, *, default: str = "") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _md_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
