from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "generic009a.positive_proof_inventory.v1"
WORK_ITEM = "GENERIC-009A Positive Proof Gap Closure Inventory"
PROOF_GAPS = (
    "benchmark_candidate_count",
    "strong_candidate_count",
    "weak_candidate_count",
    "clear_career_origin_coverage",
    "provider_backed_origin_coverage",
    "positive_control_coverage",
)
ATS_PROVIDER_HINTS = (
    "greenhouse",
    "personio",
    "lever",
    "workday",
    "successfactors",
    "smartrecruiters",
    "teamtailor",
    "recruitee",
    "softgarden",
)


def safety_boundary() -> dict[str, bool | str]:
    return {
        "read_only_inventory": True,
        "database_reads": True,
        "database_writes": False,
        "external_requests": False,
        "csv_excel_or_export_as_input": False,
        "candidate_creation": False,
        "candidate_promotion": False,
        "gate_decision": False,
        "connector_activation": False,
        "scheduler_change": False,
        "bronze_silver_gold_mutation": False,
        "decision_boundary": "positive_proof_inventory_not_gate_truth_not_apply",
    }


def build_positive_proof_inventory(
    rows: Sequence[Mapping[str, Any]],
    *,
    generated_at: str | None = None,
    source: str = "employer_origin_source_candidates",
) -> dict[str, Any]:
    items = [_classify_row(row) for row in rows]
    gap_to_keys: dict[str, list[str]] = {gap: [] for gap in PROOF_GAPS}
    for item in items:
        for gap in item["candidate_gap_coverage"]:
            gap_to_keys[gap].append(item["company_key"])

    lane_counts = Counter(item["positive_control_lane"] for item in items)
    status_counts = Counter(str(item.get("status") or "unknown") for item in items)
    covered_gaps = [gap for gap, keys in gap_to_keys.items() if keys]
    missing_gaps = [gap for gap, keys in gap_to_keys.items() if not keys]
    recommended_keys = [
        item["company_key"]
        for item in items
        if "positive_control_coverage" in item["candidate_gap_coverage"]
    ][:10]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "source": source,
        "overall_status": "ready_for_positive_control_review" if recommended_keys else "needs_positive_control_candidates",
        "safety_boundary": safety_boundary(),
        "summary": {
            "input_row_count": len(rows),
            "inventory_item_count": len(items),
            "recommended_positive_control_count": len(recommended_keys),
            "recommended_positive_control_keys": recommended_keys,
            "covered_gap_ids": covered_gaps,
            "missing_gap_ids": missing_gaps,
            "lane_counts": dict(lane_counts),
            "status_counts": dict(status_counts),
            "gap_candidate_counts": {gap: len(keys) for gap, keys in gap_to_keys.items()},
        },
        "gap_to_candidate_keys": gap_to_keys,
        "positive_control_inventory_items": items,
        "next_action": _next_action(recommended_keys, missing_gaps),
    }


def _classify_row(row: Mapping[str, Any]) -> dict[str, Any]:
    company_key = str(row.get("company_key") or "").strip()
    company_name = str(row.get("company_name") or company_key).strip()
    url = str(row.get("candidate_url") or "").strip()
    source_type = str(row.get("source_type_candidate") or "").strip()
    source_family = str(row.get("source_family_candidate") or "").strip()
    source_name = str(row.get("source_name_candidate") or "").strip()
    status = str(row.get("status") or "").strip()
    risk_level = str(row.get("risk_level") or "").strip()
    notes = str(row.get("notes") or "")
    notes_lower = notes.lower()
    url_lower = url.lower()
    source_type_lower = source_type.lower()

    has_origin_url = bool(url)
    provider_backed = any(hint in url_lower or hint in source_type_lower or hint in source_name.lower() for hint in ATS_PROVIDER_HINTS)
    create_recommended = "create_candidate_recommended" in notes_lower
    manual_review = status == "manual_review_required" or "manual_review_required" in notes_lower
    discovery_candidate = status in {"discovery", "manual_review_required", "active_controlled"}

    gap_coverage = []
    if company_key:
        gap_coverage.append("benchmark_candidate_count")
    if create_recommended:
        gap_coverage.append("strong_candidate_count")
        gap_coverage.append("positive_control_coverage")
    elif discovery_candidate:
        gap_coverage.append("weak_candidate_count")
    if has_origin_url and "career" in source_type_lower:
        gap_coverage.append("clear_career_origin_coverage")
        gap_coverage.append("positive_control_coverage")
    if provider_backed:
        gap_coverage.append("provider_backed_origin_coverage")
        gap_coverage.append("positive_control_coverage")

    if create_recommended and has_origin_url:
        lane = "strong_positive_origin_candidate"
    elif create_recommended:
        lane = "strong_positive_candidate_needs_origin_url"
    elif has_origin_url:
        lane = "weak_positive_origin_candidate"
    elif discovery_candidate:
        lane = "weak_positive_candidate_needs_origin_url"
    else:
        lane = "not_positive_control_candidate"

    return {
        "company_key": company_key,
        "company_name": company_name,
        "candidate_url": url or None,
        "source_type_candidate": source_type or None,
        "source_family_candidate": source_family or None,
        "source_name_candidate": source_name or None,
        "status": status or None,
        "risk_level": risk_level or None,
        "positive_control_lane": lane,
        "candidate_gap_coverage": _unique(gap_coverage),
        "evidence_signals": {
            "has_candidate_url": has_origin_url,
            "provider_backed_hint": provider_backed,
            "create_candidate_recommended_in_notes": create_recommended,
            "manual_review_signal": manual_review,
            "discovery_candidate_status": discovery_candidate,
        },
        "boundary": "inventory_only_not_candidate_creation_not_gate_truth",
    }


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _next_action(recommended_keys: Sequence[str], missing_gaps: Sequence[str]) -> str:
    if not recommended_keys:
        return "No positive controls are ready from the inspected DB rows; inspect origin candidates or source evidence before candidate creation."
    if missing_gaps:
        return "Review recommended positive-control keys and close remaining missing gap coverage before EXPAND-004/007 can progress."
    return "Positive proof inventory has candidate coverage for all known GENERIC-001 gaps; operator review is required before any registry or gate step."


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    lines = [
        "# GENERIC-009A Positive Proof Inventory",
        "",
        f"Generated: `{report.get('generated_at_utc')}`",
        f"Overall status: `{report.get('overall_status')}`",
        "",
        "Boundary: `inventory_only_not_candidate_creation_not_gate_truth`",
        "",
        "## Summary",
        "",
        f"- Input rows: `{summary.get('input_row_count')}`",
        f"- Recommended positive controls: `{summary.get('recommended_positive_control_count')}`",
        f"- Recommended keys: `{summary.get('recommended_positive_control_keys')}`",
        f"- Covered gaps: `{summary.get('covered_gap_ids')}`",
        f"- Missing gaps: `{summary.get('missing_gap_ids')}`",
        "",
        "## Next action",
        "",
        str(report.get("next_action")),
        "",
    ]
    return "\n".join(lines)


def write_outputs(report: Mapping[str, Any], export_dir: Path) -> dict[str, Path]:
    export_dir.mkdir(parents=True, exist_ok=True)
    json_path = export_dir / "generic009a_positive_proof_inventory.json"
    md_path = export_dir / "generic009a_positive_proof_inventory.md"
    json_path.write_text(json.dumps(report, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
