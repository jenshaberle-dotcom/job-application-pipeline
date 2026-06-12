from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.search_intelligence.generic_pipeline_proof_gate import build_generic_pipeline_proof_report, write_outputs as write_generic001_outputs
from src.search_intelligence.generic004_stop_control_evidence_capture_plan import (
    find_latest_expand003_report,
    load_expand003_report,
)

SCHEMA_VERSION = "generic005.stop_control_final_rerun.v1"
WORK_ITEM = "GENERIC-005 Stop-Control Evidence / GENERIC-001 Final Rerun"
GENERIC003_SCHEMA_PREFIX = "generic003.benchmark_control_rerun_review"
GENERIC004_SCHEMA_PREFIX = "generic004.stop_control_evidence_capture_plan"

SAFE_STOP_ACTIONS = frozenset(
    {
        "no_useful_external_hint_no_candidate_creation",
        "provider_auth_failed_requires_key_review",
        "probe_error_requires_retry_or_review",
    }
)
STOP_CONTROL_GAPS = ("no_actionable_evidence_coverage", "negative_control_coverage")
PLACEHOLDER_SUMMARY_PREFIX = "describe why no company-origin/detail/provider evidence"
BOUNDARY = "review_artifact_only_no_candidate_or_gate_write"


@dataclass(frozen=True)
class StopControlEvidenceRow:
    control_type: str
    required_for_gap_ids: tuple[str, ...]
    company_key: str
    company_name: str
    review_action: str
    evidence_strength: str
    evidence_summary: str
    reviewer: str
    review_date: str
    boundary: str
    status: str
    rejection_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["required_for_gap_ids"] = list(self.required_for_gap_ids)
        return data


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


def load_generic004_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("GENERIC-004 input JSON root must be an object.")
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(GENERIC004_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected GENERIC-004 schema_version: {schema_version or '<missing>'}")
    return payload


def find_latest_generic003_report(exports_dir: Path = Path("exports")) -> Path | None:
    return _find_latest_report(
        exports_dir,
        [
            "generic003_benchmark_control_rerun_review/generic003_benchmark_control_rerun_review.json",
            "generic003_benchmark_control_rerun_review_*/generic003_benchmark_control_rerun_review.json",
        ],
    )


def find_latest_generic004_report(exports_dir: Path = Path("exports")) -> Path | None:
    return _find_latest_report(
        exports_dir,
        [
            "generic004_stop_control_evidence_capture_plan/generic004_stop_control_evidence_capture_plan.json",
            "generic004_stop_control_evidence_capture_plan_*/generic004_stop_control_evidence_capture_plan.json",
        ],
    )


def find_latest_capture_csv(exports_dir: Path = Path("exports")) -> Path | None:
    return _find_latest_report(
        exports_dir,
        [
            "generic004_stop_control_evidence_capture_plan/generic004_stop_control_capture_template.csv",
            "generic004_stop_control_evidence_capture_plan_*/generic004_stop_control_capture_template.csv",
        ],
    )


def build_stop_control_final_rerun_report(
    generic003_report: Mapping[str, Any],
    generic004_report: Mapping[str, Any],
    expand003_report: Mapping[str, Any],
    capture_rows: Sequence[Mapping[str, Any]],
    *,
    generic003_path: str | None = None,
    generic004_path: str | None = None,
    expand003_path: str | None = None,
    capture_path: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    positive_control_keys = _positive_control_keys(generic003_report)
    evidence_rows = evaluate_capture_rows(capture_rows)
    accepted_rows = [row for row in evidence_rows if row.status == "accepted_stop_control"]
    rejected_rows = [row for row in evidence_rows if row.status != "accepted_stop_control"]
    negative_control_keys = _unique([row.company_key for row in accepted_rows])
    augmented_expand003 = augment_expand003_with_stop_controls(expand003_report, accepted_rows)

    generic001_final = build_generic_pipeline_proof_report(
        augmented_expand003,
        expand003_path=expand003_path,
        positive_control_keys=positive_control_keys,
        negative_control_keys=negative_control_keys,
        generated_at=generated_at,
    )
    final_gap_ids = _string_list(generic001_final.get("gap_ids"))
    closed_stop_gap_ids = [gap_id for gap_id in STOP_CONTROL_GAPS if gap_id not in final_gap_ids and accepted_rows]

    overall_status = _overall_status(
        positive_control_keys=positive_control_keys,
        negative_control_keys=negative_control_keys,
        final_gap_ids=final_gap_ids,
        accepted_rows=accepted_rows,
    )
    next_action = build_next_action(overall_status, final_gap_ids, rejected_rows)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "overall_status": overall_status,
        "generic003_input_path": generic003_path,
        "generic003_input_schema_version": generic003_report.get("schema_version"),
        "generic004_input_path": generic004_path,
        "generic004_input_schema_version": generic004_report.get("schema_version"),
        "generic004_input_overall_status": generic004_report.get("overall_status"),
        "expand003_input_path": expand003_path,
        "expand003_input_schema_version": expand003_report.get("schema_version"),
        "capture_input_path": capture_path,
        "safety_boundary": no_mutation_boundary(),
        "mutation_counts": mutation_counts(),
        "interpretation_boundary": (
            "GENERIC-005 validates explicit operator stop-control evidence and reruns GENERIC-001 in memory with a "
            "benchmark-only augmented review artifact. It does not create candidates, write gates, activate connectors, "
            "mutate Bronze/Silver/Gold, change scheduler behavior, read the database, or perform external requests. "
            "A CSV row is accepted only as a review artifact, never as pipeline truth."
        ),
        "summary": {
            "positive_control_keys": positive_control_keys,
            "negative_control_keys": negative_control_keys,
            "accepted_stop_control_count": len(accepted_rows),
            "rejected_stop_control_count": len(rejected_rows),
            "closed_stop_gap_ids": closed_stop_gap_ids,
            "final_gap_ids": final_gap_ids,
            "generic001_final_overall_status": generic001_final.get("overall_status"),
            "generic001_final_failed_check_count": _mapping(generic001_final.get("summary")).get("failed_check_count"),
            "generic001_final_candidate_count": _mapping(generic001_final.get("summary")).get("candidate_count"),
        },
        "capture_row_assessments": [row.as_dict() for row in evidence_rows],
        "accepted_stop_controls": [row.as_dict() for row in accepted_rows],
        "generic001_final_summary": _generic001_summary(generic001_final),
        "generic001_final_report": generic001_final,
        "next_action": next_action,
    }


def evaluate_capture_rows(capture_rows: Sequence[Mapping[str, Any]]) -> list[StopControlEvidenceRow]:
    evaluated: list[StopControlEvidenceRow] = []
    for raw in capture_rows:
        row = _normalise_capture_row(raw)
        rejection_reason = _capture_rejection_reason(row)
        status = "rejected_capture_row" if rejection_reason else "accepted_stop_control"
        evaluated.append(
            StopControlEvidenceRow(
                control_type=row.control_type,
                required_for_gap_ids=row.required_for_gap_ids,
                company_key=row.company_key,
                company_name=row.company_name,
                review_action=row.review_action,
                evidence_strength=row.evidence_strength,
                evidence_summary=row.evidence_summary,
                reviewer=row.reviewer,
                review_date=row.review_date,
                boundary=row.boundary,
                status=status,
                rejection_reason=rejection_reason,
            )
        )
    return evaluated


def read_capture_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def augment_expand003_with_stop_controls(
    expand003_report: Mapping[str, Any],
    accepted_rows: Sequence[StopControlEvidenceRow],
) -> dict[str, Any]:
    augmented = dict(expand003_report)
    existing_items = _mapping_list(expand003_report.get("candidate_review_items"))
    by_key = {str(item.get("company_key") or "").strip().lower(): dict(item) for item in existing_items}
    ordered_items = [dict(item) for item in existing_items]

    for row in accepted_rows:
        key = row.company_key.strip().lower()
        benchmark_item = {
            "company_key": row.company_key,
            "company_name": row.company_name,
            "review_action": row.review_action,
            "evidence_strength": row.evidence_strength or "none",
            "top_strong_urls": [],
            "top_weak_urls": [],
            "benchmark_control_source": "generic005_operator_stop_control_evidence",
            "benchmark_evidence_summary": row.evidence_summary,
        }
        if key in by_key:
            for index, item in enumerate(ordered_items):
                if str(item.get("company_key") or "").strip().lower() == key:
                    merged = dict(item)
                    merged.update(benchmark_item)
                    ordered_items[index] = merged
                    break
        else:
            ordered_items.append(benchmark_item)
    augmented["candidate_review_items"] = ordered_items
    augmented["generic005_benchmark_augmentation"] = {
        "added_or_overlaid_stop_control_count": len(accepted_rows),
        "boundary": "benchmark_review_artifact_only_no_candidate_or_gate_write",
    }
    return augmented


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = _mapping(report.get("summary"))
    lines = [
        "# GENERIC-005 Stop-Control Evidence / GENERIC-001 Final Rerun",
        "",
        f"- overall_status: `{report.get('overall_status')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        f"- generic003_input_path: `{report.get('generic003_input_path')}`",
        f"- generic004_input_path: `{report.get('generic004_input_path')}`",
        f"- expand003_input_path: `{report.get('expand003_input_path')}`",
        f"- capture_input_path: `{report.get('capture_input_path')}`",
        "",
        "## Safety boundary",
        "",
    ]
    for key, value in _mapping(report.get("safety_boundary")).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Summary", ""])
    for key in [
        "positive_control_keys",
        "negative_control_keys",
        "accepted_stop_control_count",
        "rejected_stop_control_count",
        "closed_stop_gap_ids",
        "final_gap_ids",
        "generic001_final_overall_status",
        "generic001_final_failed_check_count",
        "generic001_final_candidate_count",
    ]:
        lines.append(f"- {key}: `{summary.get(key)}`")
    lines.extend(["", "## Capture row assessments", ""])
    lines.append("| Company | Action | Status | Rejection reason |")
    lines.append("|---|---|---|---|")
    assessments = _mapping_list(report.get("capture_row_assessments"))
    if assessments:
        for item in assessments:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md_cell(item.get("company_name") or item.get("company_key")),
                        _md_cell(item.get("review_action")),
                        _md_cell(item.get("status")),
                        _md_cell(item.get("rejection_reason") or "-"),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| - | - | no_capture_rows | No capture rows were provided. |")
    lines.extend(["", "## GENERIC-001 final rerun", ""])
    final_summary = _mapping(report.get("generic001_final_summary"))
    for key in ["overall_status", "candidate_count", "passed_check_count", "failed_check_count", "failed_checks", "gap_ids"]:
        lines.append(f"- {key}: `{final_summary.get(key)}`")
    lines.extend(["", "## Next action", "", str(report.get("next_action") or ""), ""])
    return "\n".join(lines)


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "generic005_stop_control_final_rerun.json"
    md_path = output_dir / "generic005_stop_control_final_rerun.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    generic001_report = _mapping(report.get("generic001_final_report"))
    generic001_outputs = write_generic001_outputs(generic001_report, output_dir / "generic001_final_rerun")
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "generic001_final_json": generic001_outputs["json"],
        "generic001_final_csv": generic001_outputs["csv"],
        "generic001_final_markdown": generic001_outputs["markdown"],
    }


def build_next_action(overall_status: str, final_gap_ids: Sequence[str], rejected_rows: Sequence[StopControlEvidenceRow]) -> str:
    if overall_status == "passed_all_generics_checks_review_artifact_only":
        return "GENERIC-001 final rerun passes as review artifact only; proceed to EXPAND-004 controlled candidate creation dry-run design, not broad apply."
    if overall_status == "stop_control_capture_missing_or_invalid":
        rejected_note = ""
        if rejected_rows:
            rejected_note = " Rejected capture rows must be fixed before rerun."
        return (
            "Keep EXPAND-004, Wave Search scaling, scheduler changes, and TOP5 product claims blocked. "
            "Fill the GENERIC-004 capture CSV with one explicit reviewed stop/no-actionable negative control and rerun GENERIC-005."
            + rejected_note
        )
    if overall_status == "final_rerun_still_has_gaps":
        return (
            "GENERIC-005 accepted stop-control evidence but GENERIC-001 still has benchmark gaps: "
            f"{', '.join(final_gap_ids) or '<unknown>'}. Review the final nested GENERIC-001 report before continuing."
        )
    return "Review GENERIC-005 inputs and rerun before continuing."


def _overall_status(
    *,
    positive_control_keys: Sequence[str],
    negative_control_keys: Sequence[str],
    final_gap_ids: Sequence[str],
    accepted_rows: Sequence[StopControlEvidenceRow],
) -> str:
    if not accepted_rows or not negative_control_keys:
        return "stop_control_capture_missing_or_invalid"
    if not positive_control_keys:
        return "final_rerun_still_has_gaps"
    if not final_gap_ids:
        return "passed_all_generics_checks_review_artifact_only"
    return "final_rerun_still_has_gaps"


def _positive_control_keys(generic003_report: Mapping[str, Any]) -> list[str]:
    summary = _mapping(generic003_report.get("summary"))
    keys = _string_list(summary.get("positive_control_keys"))
    if keys:
        return _unique(keys)
    after = _mapping(generic003_report.get("generic001_after_report"))
    controls: list[str] = []
    for row in _mapping_list(after.get("candidate_decision_table")):
        if "positive_control_candidate" in _string_list(row.get("generics_dimensions")):
            key = str(row.get("company_key") or "").strip()
            if key:
                controls.append(key)
    return _unique(controls)


def _normalise_capture_row(row: Mapping[str, Any]) -> StopControlEvidenceRow:
    return StopControlEvidenceRow(
        control_type=_text(row.get("control_type")),
        required_for_gap_ids=tuple(_split_gap_ids(row.get("required_for_gap_ids"))),
        company_key=_text(row.get("company_key")),
        company_name=_text(row.get("company_name")),
        review_action=_text(row.get("review_action")),
        evidence_strength=_text(row.get("evidence_strength"), default="none"),
        evidence_summary=_text(row.get("evidence_summary")),
        reviewer=_text(row.get("reviewer")),
        review_date=_text(row.get("review_date")),
        boundary=_text(row.get("boundary")),
        status="pending_validation",
    )


def _capture_rejection_reason(row: StopControlEvidenceRow) -> str:
    if row.control_type not in {"new_clean_no_actionable_negative_control", "existing_safe_stop_negative_control"}:
        return "control_type must be an explicit stop-control type"
    if set(STOP_CONTROL_GAPS) - set(row.required_for_gap_ids):
        return "required_for_gap_ids must include no_actionable_evidence_coverage and negative_control_coverage"
    if not row.company_key or not row.company_name:
        return "company_key and company_name are required"
    if row.review_action not in SAFE_STOP_ACTIONS:
        return "review_action must be a safe-stop action"
    if not row.evidence_summary or row.evidence_summary.lower().startswith(PLACEHOLDER_SUMMARY_PREFIX):
        return "evidence_summary must describe the bounded stop-control review, not the template placeholder"
    if not row.reviewer or not row.review_date:
        return "reviewer and review_date are required for explicit operator control evidence"
    if row.boundary != BOUNDARY:
        return f"boundary must remain {BOUNDARY}"
    return ""


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


def _find_latest_report(exports_dir: Path, patterns: Sequence[str]) -> Path | None:
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(path for path in exports_dir.glob(pattern) if path.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda path: (_timestamp_from_parent(path), path.stat().st_mtime, str(path)))


def _timestamp_from_parent(path: Path) -> str:
    parent_name = path.parent.name
    parts = parent_name.rsplit("_", 1)
    if len(parts) == 2 and parts[1][:8].isdigit():
        return parts[1]
    return ""


def _split_gap_ids(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.replace(",", ";").split(";") if part.strip()]
    return _string_list(value)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [str(item) for item in value if str(item).strip()]


def _unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        item = str(value).strip()
        key = item.lower()
        if item and key not in seen:
            out.append(item)
            seen.add(key)
    return out


def _text(value: Any, *, default: str = "") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _md_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")
