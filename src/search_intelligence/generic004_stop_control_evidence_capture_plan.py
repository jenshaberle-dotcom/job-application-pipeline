from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "generic004.stop_control_evidence_capture_plan.v1"
WORK_ITEM = "GENERIC-004 Stop-Control Evidence Capture Plan"
GENERIC003_SCHEMA_PREFIX = "generic003.benchmark_control_rerun_review"
EXPAND003_SCHEMA_PREFIX = "expand003.candidate_review_delta_report"

NEGATIVE_GAP = "negative_control_coverage"
NO_ACTIONABLE_GAP = "no_actionable_evidence_coverage"
STOP_CONTROL_GAPS = (NO_ACTIONABLE_GAP, NEGATIVE_GAP)
SAFE_STOP_ACTIONS = frozenset(
    {
        "no_useful_external_hint_no_candidate_creation",
        "provider_auth_failed_requires_key_review",
        "probe_error_requires_retry_or_review",
    }
)
WEAK_ONLY_ACTION = "weak_external_hint_no_candidate_creation"


@dataclass(frozen=True)
class CandidateStopAssessment:
    company_key: str
    company_name: str
    review_action: str
    evidence_strength: str
    assessment_status: str
    can_close_gap_ids: tuple[str, ...]
    required_operator_action: str
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["can_close_gap_ids"] = list(self.can_close_gap_ids)
        return data


@dataclass(frozen=True)
class CaptureTemplateRow:
    control_type: str
    required_for_gap_ids: str
    company_key: str
    company_name: str
    review_action: str
    evidence_strength: str
    evidence_summary: str
    reviewer: str
    review_date: str
    boundary: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


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


def load_generic003_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("GENERIC-003 input JSON root must be an object.")
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(GENERIC003_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected GENERIC-003 schema_version: {schema_version or '<missing>'}")
    return payload


def load_expand003_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("EXPAND-003 input JSON root must be an object.")
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(EXPAND003_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected EXPAND-003 schema_version: {schema_version or '<missing>'}")
    return payload


def find_latest_generic003_report(exports_dir: Path = Path("exports")) -> Path | None:
    patterns = [
        "generic003_benchmark_control_rerun_review/generic003_benchmark_control_rerun_review.json",
        "generic003_benchmark_control_rerun_review_*/generic003_benchmark_control_rerun_review.json",
    ]
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(path for path in exports_dir.glob(pattern) if path.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda path: (_timestamp_from_parent(path), path.stat().st_mtime, str(path)))


def find_latest_expand003_report(exports_dir: Path = Path("exports")) -> Path | None:
    patterns = [
        "expand003_candidate_review_delta_report/expand003_candidate_review_delta_report.json",
        "expand003_candidate_review_delta_report_*/expand003_candidate_review_delta_report.json",
    ]
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(path for path in exports_dir.glob(pattern) if path.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda path: (_timestamp_from_parent(path), path.stat().st_mtime, str(path)))


def build_stop_control_evidence_capture_plan(
    generic003_report: Mapping[str, Any],
    expand003_report: Mapping[str, Any],
    *,
    generic003_path: str | None = None,
    expand003_path: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    remaining_gap_ids = _remaining_stop_gap_ids(generic003_report)
    candidate_rows = _mapping_list(expand003_report.get("candidate_review_items"))
    assessments = build_candidate_stop_assessments(candidate_rows)
    safe_stop_candidates = [item for item in assessments if item.assessment_status == "eligible_safe_stop_control"]
    weak_only_candidates = [item for item in assessments if item.assessment_status == "not_eligible_weak_only_signal"]
    template_rows = build_capture_template_rows(remaining_gap_ids, safe_stop_candidates)
    runnable_follow_up_command = build_follow_up_command(safe_stop_candidates)

    if not remaining_gap_ids:
        overall_status = "no_remaining_stop_control_gaps"
    elif _all_remaining_gaps_closable(remaining_gap_ids, safe_stop_candidates):
        overall_status = "ready_to_close_stop_controls_with_existing_safe_stop_artifact"
    else:
        overall_status = "operator_capture_required_missing_stop_control_evidence"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "overall_status": overall_status,
        "generic003_input_path": generic003_path,
        "generic003_input_schema_version": generic003_report.get("schema_version"),
        "generic003_input_overall_status": generic003_report.get("overall_status"),
        "expand003_input_path": expand003_path,
        "expand003_input_schema_version": expand003_report.get("schema_version"),
        "safety_boundary": no_mutation_boundary(),
        "mutation_counts": mutation_counts(),
        "interpretation_boundary": (
            "GENERIC-004 is a capture-plan artifact only. It identifies whether remaining stop-control benchmark gaps can be "
            "closed from existing review artifacts, produces an operator intake template when evidence is missing, and keeps "
            "EXPAND-004/Wave/Scheduler/TOP5 work blocked until explicit safe-stop evidence exists. It does not create candidates, "
            "write gates, activate connectors, mutate Bronze/Silver/Gold, read the database, or perform external requests."
        ),
        "summary": {
            "remaining_gap_ids": remaining_gap_ids,
            "remaining_stop_gap_count": len(remaining_gap_ids),
            "candidate_count": len(candidate_rows),
            "eligible_safe_stop_candidate_count": len(safe_stop_candidates),
            "weak_only_not_eligible_candidate_count": len(weak_only_candidates),
            "capture_template_row_count": len(template_rows),
            "safe_stop_candidate_keys": [item.company_key for item in safe_stop_candidates],
            "weak_only_not_eligible_candidate_keys": [item.company_key for item in weak_only_candidates],
        },
        "evidence_acceptance_criteria": evidence_acceptance_criteria(),
        "candidate_stop_assessments": [item.as_dict() for item in assessments],
        "capture_template_rows": [row.as_dict() for row in template_rows],
        "follow_up_command_if_template_filled": runnable_follow_up_command,
        "next_action": build_next_action(overall_status, remaining_gap_ids),
    }


def build_candidate_stop_assessments(candidate_rows: Sequence[Mapping[str, Any]]) -> list[CandidateStopAssessment]:
    assessments: list[CandidateStopAssessment] = []
    for row in candidate_rows:
        company_key = _text(row.get("company_key"), default="unknown_company")
        company_name = _text(row.get("company_name"), default=company_key)
        review_action = _text(row.get("review_action"), default="unknown_review_action")
        evidence_strength = _text(row.get("evidence_strength"), default="unknown_evidence_strength")
        if review_action in SAFE_STOP_ACTIONS:
            assessments.append(
                CandidateStopAssessment(
                    company_key=company_key,
                    company_name=company_name,
                    review_action=review_action,
                    evidence_strength=evidence_strength,
                    assessment_status="eligible_safe_stop_control",
                    can_close_gap_ids=STOP_CONTROL_GAPS,
                    required_operator_action="mark_as_explicit_negative_control_and_rerun_generic001",
                    rationale=(
                        "This row already has a safe-stop review action. One explicit safe-stop control can close both "
                        "no-actionable-evidence and negative-control benchmark coverage."
                    ),
                )
            )
        elif review_action == WEAK_ONLY_ACTION:
            assessments.append(
                CandidateStopAssessment(
                    company_key=company_key,
                    company_name=company_name,
                    review_action=review_action,
                    evidence_strength=evidence_strength,
                    assessment_status="not_eligible_weak_only_signal",
                    can_close_gap_ids=(),
                    required_operator_action="do_not_use_as_negative_control_without_new_stop_evidence",
                    rationale=(
                        "Weak market evidence validates weak-signal stopping, but it is not a clean no-actionable or known-blocked "
                        "negative control. Using it as the negative control would hide an unvalidated assumption."
                    ),
                )
            )
        else:
            assessments.append(
                CandidateStopAssessment(
                    company_key=company_key,
                    company_name=company_name,
                    review_action=review_action,
                    evidence_strength=evidence_strength,
                    assessment_status="not_stop_control_candidate",
                    can_close_gap_ids=(),
                    required_operator_action="keep_for_positive_or_origin_review_not_stop_control",
                    rationale="This row has actionable evidence or a non-stop review action, so it must not be used as a negative control.",
                )
            )
    return sorted(assessments, key=lambda item: (item.assessment_status, item.company_name.lower(), item.company_key))


def evidence_acceptance_criteria() -> list[dict[str, str]]:
    return [
        {
            "criterion_id": "explicit_safe_stop_review_action",
            "required": "true",
            "description": "Review action must be one of the safe-stop actions: no useful external hint, provider auth blocked, or probe error requiring retry/review.",
        },
        {
            "criterion_id": "operator_named_control",
            "required": "true",
            "description": "The candidate key must be explicitly named as a negative/no-actionable control; weak-only status must not be silently reinterpreted.",
        },
        {
            "criterion_id": "no_apply_side_effect",
            "required": "true",
            "description": "The evidence capture remains a review artifact only and must not create candidates, gates, source targets, or connector changes.",
        },
        {
            "criterion_id": "rerunnable_generic001_command",
            "required": "true",
            "description": "After capture, GENERIC-001 must be rerunnable with --negative-control-key for the explicit safe-stop candidate.",
        },
    ]


def build_capture_template_rows(
    remaining_gap_ids: Sequence[str],
    safe_stop_candidates: Sequence[CandidateStopAssessment],
) -> list[CaptureTemplateRow]:
    if not any(gap_id in STOP_CONTROL_GAPS for gap_id in remaining_gap_ids):
        return []
    if safe_stop_candidates:
        return [
            CaptureTemplateRow(
                control_type="existing_safe_stop_negative_control",
                required_for_gap_ids=";".join(STOP_CONTROL_GAPS),
                company_key=candidate.company_key,
                company_name=candidate.company_name,
                review_action=candidate.review_action,
                evidence_strength=candidate.evidence_strength,
                evidence_summary="Existing EXPAND-003 safe-stop row; verify manually before using as explicit negative control.",
                reviewer="",
                review_date="",
                boundary="review_artifact_only_no_candidate_or_gate_write",
            )
            for candidate in safe_stop_candidates
        ]
    return [
        CaptureTemplateRow(
            control_type="new_clean_no_actionable_negative_control",
            required_for_gap_ids=";".join(STOP_CONTROL_GAPS),
            company_key="",
            company_name="",
            review_action="no_useful_external_hint_no_candidate_creation",
            evidence_strength="none",
            evidence_summary="Describe why no company-origin/detail/provider evidence was actionable after bounded review.",
            reviewer="",
            review_date="",
            boundary="review_artifact_only_no_candidate_or_gate_write",
        )
    ]


def build_follow_up_command(safe_stop_candidates: Sequence[CandidateStopAssessment]) -> str | None:
    if not safe_stop_candidates:
        return None
    key = safe_stop_candidates[0].company_key
    return (
        "python scripts/run_generic001_pipeline_generics_proof_gate.py "
        "--positive-control-key adesso_business_consulting "
        f"--negative-control-key {key}"
    )


def build_next_action(overall_status: str, remaining_gap_ids: Sequence[str]) -> str:
    if overall_status == "no_remaining_stop_control_gaps":
        return "No remaining stop-control benchmark gaps; proceed to EXPAND-004 dry-run design only after rerunning validation artifacts."
    if overall_status == "ready_to_close_stop_controls_with_existing_safe_stop_artifact":
        return "Rerun GENERIC-001/002/003 with the explicit negative-control key from the safe-stop artifact, then review whether GENERIC-001 passes."
    return (
        "Keep EXPAND-004, Wave Search scaling, scheduler changes, and TOP5 product claims blocked. Capture one explicit "
        f"safe-stop/no-actionable evidence row first for gaps: {', '.join(remaining_gap_ids) or '<unknown>'}."
    )


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = _mapping(report.get("summary"))
    lines = [
        "# GENERIC-004 Stop-Control Evidence Capture Plan",
        "",
        f"- overall_status: `{report.get('overall_status')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        f"- generic003_input_path: `{report.get('generic003_input_path')}`",
        f"- expand003_input_path: `{report.get('expand003_input_path')}`",
        "",
        "## Safety boundary",
        "",
    ]
    for key, value in _mapping(report.get("safety_boundary")).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Summary", ""])
    for key in [
        "remaining_gap_ids",
        "remaining_stop_gap_count",
        "candidate_count",
        "eligible_safe_stop_candidate_count",
        "weak_only_not_eligible_candidate_count",
        "capture_template_row_count",
        "safe_stop_candidate_keys",
        "weak_only_not_eligible_candidate_keys",
    ]:
        lines.append(f"- {key}: `{summary.get(key)}`")
    lines.extend(["", "## Evidence acceptance criteria", ""])
    for criterion in _mapping_list(report.get("evidence_acceptance_criteria")):
        lines.append(f"- `{criterion.get('criterion_id')}`: {criterion.get('description')}")
    lines.extend(["", "## Candidate stop assessments", ""])
    lines.append("| Company | Action | Evidence | Assessment | Closes gaps |")
    lines.append("|---|---|---|---|---|")
    for item in _mapping_list(report.get("candidate_stop_assessments")):
        closes = "; ".join(_string_list(item.get("can_close_gap_ids"))) or "-"
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(item.get("company_name")),
                    _md_cell(item.get("review_action")),
                    _md_cell(item.get("evidence_strength")),
                    _md_cell(item.get("assessment_status")),
                    _md_cell(closes),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Capture template", ""])
    lines.append("The CSV template is written next to this Markdown report. Fill it only after a bounded manual/operator review.")
    command = report.get("follow_up_command_if_template_filled")
    lines.extend(["", "## Follow-up command if an eligible safe-stop row exists", ""])
    lines.append(f"    {command}" if command else "No rerun command is available until explicit safe-stop evidence is captured.")
    lines.extend(["", "## Next action", "", str(report.get("next_action") or ""), ""])
    return "\n".join(lines)


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "generic004_stop_control_evidence_capture_plan.json"
    md_path = output_dir / "generic004_stop_control_evidence_capture_plan.md"
    csv_path = output_dir / "generic004_stop_control_capture_template.csv"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    write_capture_template_csv(csv_path, _mapping_list(report.get("capture_template_rows")))
    return {"json": str(json_path), "markdown": str(md_path), "capture_template_csv": str(csv_path)}


def write_capture_template_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = [
        "control_type",
        "required_for_gap_ids",
        "company_key",
        "company_name",
        "review_action",
        "evidence_strength",
        "evidence_summary",
        "reviewer",
        "review_date",
        "boundary",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _all_remaining_gaps_closable(
    remaining_gap_ids: Sequence[str], safe_stop_candidates: Sequence[CandidateStopAssessment]
) -> bool:
    if not remaining_gap_ids:
        return True
    closable = {gap_id for item in safe_stop_candidates for gap_id in item.can_close_gap_ids}
    return all(gap_id in closable for gap_id in remaining_gap_ids)


def _remaining_stop_gap_ids(generic003_report: Mapping[str, Any]) -> list[str]:
    summary = _mapping(generic003_report.get("summary"))
    gap_ids = _string_list(summary.get("still_blocked_gap_ids")) or _string_list(generic003_report.get("gap_ids"))
    return [gap_id for gap_id in STOP_CONTROL_GAPS if gap_id in set(gap_ids)]


def _timestamp_from_parent(path: Path) -> str:
    parent = path.parent.name
    for prefix in (
        "generic004_stop_control_evidence_capture_plan_",
        "generic003_benchmark_control_rerun_review_",
        "expand003_candidate_review_delta_report_",
    ):
        if parent.startswith(prefix):
            return parent.removeprefix(prefix)
    return ""


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
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
