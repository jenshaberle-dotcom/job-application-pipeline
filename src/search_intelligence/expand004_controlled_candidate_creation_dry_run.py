from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "expand004.controlled_candidate_creation_dry_run.v1"
WORK_ITEM = "EXPAND-004 Controlled Candidate Creation Dry-Run"
GENERIC005_SCHEMA_PREFIX = "generic005.stop_control_final_rerun"
EXPAND003_SCHEMA_PREFIX = "expand003.candidate_review_delta_report"

PASSED_GENERIC005_STATUS = "passed_all_generics_checks_review_artifact_only"
PASSED_GENERIC001_STATUS = "passed_review_artifact_only"
STRONG_DETAIL_ACTION = "ready_for_human_evidence_review"
STRONG_ORIGIN_ACTION = "ready_for_detail_followup_review"
WEAK_ACTION = "weak_external_hint_no_candidate_creation"
STOP_ACTIONS = frozenset(
    {
        "no_useful_external_hint_no_candidate_creation",
        "provider_auth_failed_requires_key_review",
        "probe_error_requires_retry_or_review",
    }
)
DEFAULT_MAX_DRY_RUN_CANDIDATES = 5

EXPLICITLY_DISALLOWED_ACTIONS = (
    "create_candidate_record",
    "promote_candidate_automatically",
    "write_gate_decision",
    "activate_connector",
    "mutate_bronze_silver_gold",
    "change_scheduler",
    "execute_external_requests",
    "persist_pipeline_state_without_apply_gate",
)

BASE_OPERATOR_CHECKS = (
    "confirm_company_identity_not_alias_collision",
    "confirm_origin_url_is_company_or_recruiting_provider_controlled",
    "confirm_job_or_career_signal_relevant_for_jens_profiles",
    "confirm_no_duplicate_active_or_blocked_candidate_exists",
    "confirm_creation_is_preview_only_until_separate_apply_gate",
)


@dataclass(frozen=True)
class CandidateCreationDryRunItem:
    company_key: str
    company_name: str
    source_review_action: str
    source_evidence_strength: str
    dry_run_lane: str
    dry_run_readiness: str
    dry_run_priority_rank: int
    planned_candidate_action: str
    selected_for_creation_dry_run: bool
    human_review_required: bool
    expected_artifacts: tuple[str, ...]
    required_operator_checks: tuple[str, ...]
    explicitly_disallowed_actions: tuple[str, ...]
    reason: str
    candidate_creation_allowed_by_this_report: bool = False
    automatic_promotion_allowed_by_this_report: bool = False
    gate_decision_allowed_by_this_report: bool = False
    connector_activation_allowed_by_this_report: bool = False
    scheduler_change_allowed_by_this_report: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["expected_artifacts"] = list(self.expected_artifacts)
        data["required_operator_checks"] = list(self.required_operator_checks)
        data["explicitly_disallowed_actions"] = list(self.explicitly_disallowed_actions)
        return data


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


def load_generic005_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("GENERIC-005 input JSON root must be an object.")
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(GENERIC005_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected GENERIC-005 schema_version: {schema_version or '<missing>'}")
    return payload


def load_expand003_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("EXPAND-003 input JSON root must be an object.")
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(EXPAND003_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected EXPAND-003 schema_version: {schema_version or '<missing>'}")
    return payload


def find_latest_generic005_report(exports_dir: Path = Path("exports")) -> Path | None:
    return _find_latest_report(
        exports_dir,
        [
            "generic005_stop_control_final_rerun/generic005_stop_control_final_rerun.json",
            "generic005_stop_control_final_rerun_*/generic005_stop_control_final_rerun.json",
        ],
    )


def find_latest_expand003_report(exports_dir: Path = Path("exports")) -> Path | None:
    return _find_latest_report(
        exports_dir,
        [
            "expand003_candidate_review_delta_report/expand003_candidate_review_delta_report.json",
            "expand003_candidate_review_delta_report_*/expand003_candidate_review_delta_report.json",
        ],
    )


def build_candidate_creation_dry_run_report(
    generic005_report: Mapping[str, Any],
    expand003_report: Mapping[str, Any],
    *,
    generic005_path: str | None = None,
    expand003_path: str | None = None,
    max_dry_run_candidates: int = DEFAULT_MAX_DRY_RUN_CANDIDATES,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generics_ready = _generic005_passed(generic005_report)
    items = build_dry_run_items(
        _mapping_list(expand003_report.get("candidate_review_items")),
        generics_ready=generics_ready,
        max_dry_run_candidates=max_dry_run_candidates,
    )
    summary = build_summary(items, generic005_report, generics_ready=generics_ready)
    overall_status = _overall_status(items, generics_ready)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "overall_status": overall_status,
        "generic005_input_path": generic005_path,
        "generic005_input_schema_version": generic005_report.get("schema_version"),
        "generic005_input_overall_status": generic005_report.get("overall_status"),
        "expand003_input_path": expand003_path,
        "expand003_input_schema_version": expand003_report.get("schema_version"),
        "safety_boundary": no_mutation_boundary(),
        "mutation_counts": mutation_counts(),
        "interpretation_boundary": (
            "EXPAND-004 is a controlled candidate creation dry-run manifest. It translates passed GENERIC-001/005 "
            "benchmark evidence into a preview-only candidate creation plan. It does not create candidate records, "
            "write gates, activate connectors, mutate Bronze/Silver/Gold, change scheduler behavior, read the database, "
            "or perform external requests. Any real write requires a separate explicit apply gate."
        ),
        "dry_run_policy": build_dry_run_policy(max_dry_run_candidates=max_dry_run_candidates),
        "summary": summary,
        "candidate_creation_dry_run_items": [item.as_dict() for item in items],
        "next_action": build_next_action(overall_status, summary),
    }


def build_dry_run_items(
    candidate_review_items: Sequence[Mapping[str, Any]],
    *,
    generics_ready: bool,
    max_dry_run_candidates: int = DEFAULT_MAX_DRY_RUN_CANDIDATES,
) -> list[CandidateCreationDryRunItem]:
    base_items = [_build_dry_run_item(row, generics_ready=generics_ready) for row in candidate_review_items]
    selected_count = 0
    final_items: list[CandidateCreationDryRunItem] = []
    for item in sorted(base_items, key=lambda item: (item.dry_run_priority_rank, item.company_name.lower(), item.company_key)):
        if _is_creation_dry_run_eligible(item) and selected_count < max_dry_run_candidates:
            selected_count += 1
            final_items.append(_replace_selection(item, selected=True))
        else:
            final_items.append(_replace_selection(item, selected=False))
    return final_items


def build_dry_run_policy(*, max_dry_run_candidates: int) -> dict[str, Any]:
    return {
        "mode": "dry_run_manifest_only_no_write",
        "max_selected_candidate_creation_dry_run_items": max_dry_run_candidates,
        "candidate_creation_apply_gate_required": True,
        "operator_confirmation_required_before_any_future_write": True,
        "allowed_scope": (
            "Preview candidate records and required checks for a small representative employer-origin cohort only. "
            "Do not broaden to 20+ candidates, Wave Search scaling, scheduler mutation, or TOP5 product claims in this work item."
        ),
        "explicitly_disallowed_actions": list(EXPLICITLY_DISALLOWED_ACTIONS),
    }


def build_summary(
    items: Sequence[CandidateCreationDryRunItem],
    generic005_report: Mapping[str, Any],
    *,
    generics_ready: bool,
) -> dict[str, Any]:
    lane_counts = Counter(item.dry_run_lane for item in items)
    readiness_counts = Counter(item.dry_run_readiness for item in items)
    selected = [item.company_key for item in items if item.selected_for_creation_dry_run]
    blocked_by_generics = [item.company_key for item in items if item.dry_run_readiness == "blocked_until_generic_final_pass"]
    generic005_summary = _mapping(generic005_report.get("summary"))
    return {
        "generics_ready_for_candidate_creation_dry_run": generics_ready,
        "generic005_overall_status": generic005_report.get("overall_status"),
        "generic001_final_overall_status": generic005_summary.get("generic001_final_overall_status"),
        "generic001_final_gap_ids": _string_list(generic005_summary.get("final_gap_ids")),
        "dry_run_item_count": len(items),
        "selected_candidate_creation_dry_run_count": len(selected),
        "selected_candidate_creation_dry_run_keys": selected,
        "blocked_by_generics_count": len(blocked_by_generics),
        "stop_only_item_count": sum(1 for item in items if item.dry_run_lane in {"weak_stop_only", "negative_stop_control"}),
        "lane_counts": dict(sorted(lane_counts.items())),
        "readiness_counts": dict(sorted(readiness_counts.items())),
        "mutation_counts": mutation_counts(),
    }


def build_next_action(overall_status: str, summary: Mapping[str, Any]) -> str:
    if overall_status == "ready_for_operator_candidate_creation_dry_run_review":
        keys = ", ".join(_string_list(summary.get("selected_candidate_creation_dry_run_keys"))) or "<none>"
        return (
            "Review the selected dry-run manifest before any future apply gate. Selected preview keys: "
            f"{keys}. The next implementation step must remain an explicit preview/apply decision, not broad automatic creation."
        )
    if overall_status == "blocked_by_generic005_final_rerun":
        return (
            "Do not create or preview candidate records yet. GENERIC-005 final rerun has not passed with positive and "
            "negative/no-actionable controls. Fill or fix the stop-control capture evidence, rerun GENERIC-005, then rerun EXPAND-004."
        )
    if overall_status == "no_candidate_creation_dry_run_items_selected":
        return "Generic proof passed, but no candidate creation dry-run items were selected. Review EXPAND-003 candidate evidence before continuing."
    return "Review EXPAND-004 inputs and rerun before continuing."


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = _mapping(report.get("summary"))
    lines = [
        "# EXPAND-004 Controlled Candidate Creation Dry-Run",
        "",
        f"- overall_status: `{report.get('overall_status')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        f"- generic005_input_path: `{report.get('generic005_input_path')}`",
        f"- expand003_input_path: `{report.get('expand003_input_path')}`",
        "",
        "## Safety boundary",
        "",
    ]
    for key, value in _mapping(report.get("safety_boundary")).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Summary", ""])
    for key in [
        "generics_ready_for_candidate_creation_dry_run",
        "generic005_overall_status",
        "generic001_final_overall_status",
        "generic001_final_gap_ids",
        "dry_run_item_count",
        "selected_candidate_creation_dry_run_count",
        "selected_candidate_creation_dry_run_keys",
        "blocked_by_generics_count",
        "stop_only_item_count",
    ]:
        lines.append(f"- {key}: `{summary.get(key)}`")
    lines.extend(["", "## Dry-run items", ""])
    lines.append("| Company | Lane | Readiness | Selected | Planned action | Reason |")
    lines.append("|---|---|---|---:|---|---|")
    for item in _mapping_list(report.get("candidate_creation_dry_run_items")):
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(item.get("company_name") or item.get("company_key")),
                    _md_cell(item.get("dry_run_lane")),
                    _md_cell(item.get("dry_run_readiness")),
                    _md_cell(item.get("selected_for_creation_dry_run")),
                    _md_cell(item.get("planned_candidate_action")),
                    _md_cell(item.get("reason")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Next action", "", str(report.get("next_action") or ""), ""])
    return "\n".join(lines)


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "expand004_controlled_candidate_creation_dry_run.json"
    csv_path = output_dir / "expand004_candidate_creation_dry_run_manifest.csv"
    md_path = output_dir / "expand004_controlled_candidate_creation_dry_run.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_manifest_csv(csv_path, _mapping_list(report.get("candidate_creation_dry_run_items")))
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def write_manifest_csv(path: Path, items: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = [
        "company_key",
        "company_name",
        "source_review_action",
        "source_evidence_strength",
        "dry_run_lane",
        "dry_run_readiness",
        "dry_run_priority_rank",
        "planned_candidate_action",
        "selected_for_creation_dry_run",
        "required_operator_checks",
        "explicitly_disallowed_actions",
        "reason",
        "candidate_creation_allowed_by_this_report",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            row = {key: item.get(key) for key in fieldnames}
            row["required_operator_checks"] = ";".join(_string_list(item.get("required_operator_checks")))
            row["explicitly_disallowed_actions"] = ";".join(_string_list(item.get("explicitly_disallowed_actions")))
            writer.writerow(row)


def _build_dry_run_item(row: Mapping[str, Any], *, generics_ready: bool) -> CandidateCreationDryRunItem:
    company_key = _text(row.get("company_key"), default="unknown_company")
    company_name = _text(row.get("company_name"), default=company_key)
    review_action = _text(row.get("review_action"), default="unknown_review_action")
    evidence_strength = _text(row.get("evidence_strength"), default="unknown_evidence_strength")

    lane, priority, action, artifacts, extra_checks, reason = _classify_candidate(row)
    readiness = _readiness(lane, generics_ready)
    if readiness == "blocked_until_generic_final_pass":
        action = "blocked_no_candidate_creation_preview_until_generic005_passes"
        reason = "GENERIC-005 final rerun has not passed; keep this candidate as read-only evidence context only."

    return CandidateCreationDryRunItem(
        company_key=company_key,
        company_name=company_name,
        source_review_action=review_action,
        source_evidence_strength=evidence_strength,
        dry_run_lane=lane,
        dry_run_readiness=readiness,
        dry_run_priority_rank=priority,
        planned_candidate_action=action,
        selected_for_creation_dry_run=False,
        human_review_required=True,
        expected_artifacts=tuple(artifacts),
        required_operator_checks=tuple(list(BASE_OPERATOR_CHECKS) + extra_checks),
        explicitly_disallowed_actions=EXPLICITLY_DISALLOWED_ACTIONS,
        reason=reason,
    )


def _classify_candidate(row: Mapping[str, Any]) -> tuple[str, int, str, list[str], list[str], str]:
    review_action = _text(row.get("review_action"))
    evidence_strength = _text(row.get("evidence_strength"))
    strong_urls = _string_list(row.get("top_strong_urls"))

    if review_action == STRONG_DETAIL_ACTION or evidence_strength == "strong_detail":
        return (
            "detail_ready_candidate_creation_preview",
            10,
            "preview_candidate_record_from_detail_evidence_after_operator_apply_gate",
            ["candidate_identity_preview", "origin_url_snapshot", "detail_evidence_snapshot", "duplicate_check_summary"],
            ["confirm_detail_page_is_current_and_relevant"],
            "Strong detail evidence is suitable for the first preview-only candidate creation dry-run after generic proof passes.",
        )
    if review_action == STRONG_ORIGIN_ACTION or evidence_strength == "strong_origin" or strong_urls:
        return (
            "origin_followup_candidate_preview",
            20,
            "preview_candidate_shell_for_detail_followup_after_operator_apply_gate",
            ["candidate_identity_preview", "origin_url_snapshot", "detail_followup_todo", "duplicate_check_summary"],
            ["confirm_detail_followup_is_required_before_activation"],
            "Origin/provider evidence exists, but detail evidence still needs follow-up before any stronger gate decision.",
        )
    if review_action == WEAK_ACTION or evidence_strength == "weak_market_signal":
        return (
            "weak_stop_only",
            80,
            "do_not_create_candidate_record_stop_as_weak_market_signal",
            ["stop_reason_preview", "weak_signal_snapshot"],
            ["confirm_aggregator_hint_is_not_used_as_origin_truth"],
            "Weak-only market evidence is retained as stop behavior coverage, not as candidate creation input.",
        )
    if review_action in STOP_ACTIONS:
        return (
            "negative_stop_control",
            90,
            "do_not_create_candidate_record_stop_as_negative_control",
            ["stop_reason_preview", "negative_control_evidence_snapshot"],
            ["confirm_no_actionable_origin_detail_or_provider_evidence_exists"],
            "Explicit no-actionable/negative-control evidence validates stop behavior and must not create a candidate.",
        )
    return (
        "manual_review_unknown",
        70,
        "manual_review_before_any_candidate_creation_preview",
        ["manual_review_todo"],
        ["classify_review_action_before_any_apply_gate"],
        "The source review action is not recognized for candidate creation dry-run selection.",
    )


def _readiness(lane: str, generics_ready: bool) -> str:
    if lane in {"weak_stop_only", "negative_stop_control"}:
        return "not_candidate_creation_eligible_stop_only"
    if not generics_ready:
        return "blocked_until_generic_final_pass"
    if lane == "detail_ready_candidate_creation_preview":
        return "ready_for_operator_creation_preview"
    if lane == "origin_followup_candidate_preview":
        return "ready_for_operator_creation_preview_with_detail_followup"
    return "manual_review_required_before_preview"


def _is_creation_dry_run_eligible(item: CandidateCreationDryRunItem) -> bool:
    return item.dry_run_readiness in {
        "ready_for_operator_creation_preview",
        "ready_for_operator_creation_preview_with_detail_followup",
    }


def _replace_selection(item: CandidateCreationDryRunItem, *, selected: bool) -> CandidateCreationDryRunItem:
    return CandidateCreationDryRunItem(
        company_key=item.company_key,
        company_name=item.company_name,
        source_review_action=item.source_review_action,
        source_evidence_strength=item.source_evidence_strength,
        dry_run_lane=item.dry_run_lane,
        dry_run_readiness=item.dry_run_readiness,
        dry_run_priority_rank=item.dry_run_priority_rank,
        planned_candidate_action=item.planned_candidate_action,
        selected_for_creation_dry_run=selected,
        human_review_required=item.human_review_required,
        expected_artifacts=item.expected_artifacts,
        required_operator_checks=item.required_operator_checks,
        explicitly_disallowed_actions=item.explicitly_disallowed_actions,
        reason=item.reason,
    )


def _generic005_passed(generic005_report: Mapping[str, Any]) -> bool:
    summary = _mapping(generic005_report.get("summary"))
    return (
        generic005_report.get("overall_status") == PASSED_GENERIC005_STATUS
        and summary.get("generic001_final_overall_status") == PASSED_GENERIC001_STATUS
        and not _string_list(summary.get("final_gap_ids"))
        and bool(_string_list(summary.get("positive_control_keys")))
        and bool(_string_list(summary.get("negative_control_keys")))
    )


def _overall_status(items: Sequence[CandidateCreationDryRunItem], generics_ready: bool) -> str:
    if not generics_ready:
        return "blocked_by_generic005_final_rerun"
    if not any(item.selected_for_creation_dry_run for item in items):
        return "no_candidate_creation_dry_run_items_selected"
    return "ready_for_operator_candidate_creation_dry_run_review"


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


def _text(value: Any, *, default: str = "") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
