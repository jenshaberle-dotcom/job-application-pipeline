from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "provider001a.provider_backed_origin_preflight.v1"
WORK_ITEM = "PROVIDER-001A Provider-backed Origin Coverage Preflight"
PROVIDER_HINTS = (
    "personio",
    "onlyfy",
    "workday",
    "greenhouse",
    "lever",
    "smartrecruiters",
    "zohorecruit",
    "successfactors",
    "ashbyhq",
    "bamboohr",
    "join.com",
    "recruitee",
    "softgarden",
    "teamtailor",
)


def safety_boundary() -> dict[str, bool | str]:
    return {
        "read_only_preflight": True,
        "database_reads": True,
        "database_writes": False,
        "external_requests": False,
        "candidate_creation": False,
        "candidate_promotion": False,
        "gate_decision": False,
        "connector_activation": False,
        "scheduler_change": False,
        "bronze_silver_gold_mutation": False,
        "csv_excel_or_export_as_input": False,
        "decision_boundary": "provider_coverage_preflight_not_gate_truth_not_apply",
    }


def build_provider_backed_origin_preflight(
    rows: Sequence[Mapping[str, Any]],
    *,
    generated_at: str | None = None,
    source: str = "employer_origin_source_candidates",
) -> dict[str, Any]:
    items = [_classify_row(row) for row in rows]
    provider_items = [item for item in items if item["provider_backed_hint"]]
    provider_counts = Counter(item["provider_hint"] for item in provider_items)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "source": source,
        "overall_status": "provider_backed_origin_candidates_found" if provider_items else "provider_backed_origin_coverage_missing",
        "safety_boundary": safety_boundary(),
        "summary": {
            "input_row_count": len(rows),
            "provider_backed_candidate_count": len(provider_items),
            "provider_hint_counts": dict(sorted(provider_counts.items())),
            "provider_backed_candidate_keys": [item["company_key"] for item in provider_items],
            "missing_gap_ids": [] if provider_items else ["provider_backed_origin_coverage"],
        },
        "provider_backed_origin_items": provider_items,
        "all_items": items,
        "next_action": _next_action(provider_items),
    }


def _classify_row(row: Mapping[str, Any]) -> dict[str, Any]:
    candidate_url = _text(row.get("candidate_url"))
    source_name = _text(row.get("source_name_candidate"))
    source_family = _text(row.get("source_family_candidate"))
    source_type = _text(row.get("source_type_candidate"))
    notes = _text(row.get("notes"))
    haystack = " ".join([candidate_url, source_name, source_family, source_type, notes]).lower()
    hint = next((provider for provider in PROVIDER_HINTS if provider in haystack), "")
    return {
        "company_key": _text(row.get("company_key")),
        "company_name": _text(row.get("company_name")),
        "candidate_url": candidate_url or None,
        "source_name_candidate": source_name or None,
        "source_family_candidate": source_family or None,
        "source_type_candidate": source_type or None,
        "status": _text(row.get("status")) or None,
        "risk_level": _text(row.get("risk_level")) or None,
        "provider_backed_hint": bool(hint),
        "provider_hint": hint or None,
        "boundary": "preflight_only_not_provider_truth_not_gate_truth",
    }


def _next_action(provider_items: Sequence[Mapping[str, Any]]) -> str:
    if provider_items:
        return "Review provider-backed candidates and decide whether one can be used as explicit provider coverage evidence."
    return "No provider-backed origin candidate is visible in the inspected employer-origin rows; run bounded provider/source evidence discovery before closing provider_backed_origin_coverage."


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    lines = [
        "# PROVIDER-001A Provider-backed Origin Coverage Preflight",
        "",
        f"Generated: `{report.get('generated_at_utc')}`",
        f"Overall status: `{report.get('overall_status')}`",
        "",
        "Boundary: `provider_coverage_preflight_not_gate_truth_not_apply`",
        "",
        "## Summary",
        "",
        f"- Input rows: `{summary.get('input_row_count')}`",
        f"- Provider-backed candidates: `{summary.get('provider_backed_candidate_count')}`",
        f"- Provider-backed keys: `{summary.get('provider_backed_candidate_keys')}`",
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
    json_path = export_dir / "provider001a_provider_backed_origin_preflight.json"
    md_path = export_dir / "provider001a_provider_backed_origin_preflight.md"
    json_path.write_text(json.dumps(report, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""
