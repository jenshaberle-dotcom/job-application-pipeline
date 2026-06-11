from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "market003f.expand001_controlled_manual_candidate_pipeline_trial.v1"
WORK_ITEM = "MARKET-003F / EXPAND-001 Controlled Manual Candidate Pipeline Trial"
INPUT_SCHEMA_PREFIX = "market003e.candidate_expansion_review_ui_queue_readiness"
NO_MUTATION_BOUNDARY = (
    "trial_plan_only_no_automatic_candidate_creation_no_gate_decision_no_connector_activation"
)

EXPLICITLY_DISALLOWED_ACTIONS = (
    "create_candidate_automatically",
    "promote_candidate_automatically",
    "write_gate_decision",
    "activate_connector",
    "mutate_bronze_silver_gold",
    "change_scheduler",
    "persist_pipeline_state_without_apply_gate",
)

DEFAULT_PLANNED_STAGES = (
    "review_queue_context_intake",
    "company_identity_checkpoint",
    "origin_url_discovery_probe",
    "detail_page_evidence_probe",
    "pipeline_stop_or_progress_measurement",
    "human_review_summary",
)

EXTERNAL_STAGE_NAMES = (
    "origin_url_discovery_probe",
    "detail_page_evidence_probe",
)

ALLOWED_OPERATOR_ACTIONS = (
    "run_explicit_trial_plan",
    "collect_external_origin_url_evidence",
    "collect_external_detail_page_evidence",
    "record_trial_result_as_review_artifact",
    "classify_stop_reason_for_follow_up",
)


@dataclass(frozen=True)
class ControlledTrialCandidate:
    trial_id: str
    company_key: str
    company_name: str
    source_queue_lane: str
    source_ui_status: str
    source_priority_rank: int
    source_evidence_badge: str
    trial_lane: str
    trial_readiness: str
    trial_priority_rank: int
    eligible_for_explicit_external_probe: bool
    planned_stages: tuple[str, ...]
    external_probe_stages: tuple[str, ...]
    allowed_operator_actions: tuple[str, ...]
    explicitly_disallowed_actions: tuple[str, ...]
    expected_stop_conditions: tuple[str, ...]
    measurement_questions: tuple[str, ...]
    trial_note: str
    no_mutation_boundary: str = NO_MUTATION_BOUNDARY
    candidate_creation_allowed: bool = False
    automatic_promotion_allowed: bool = False
    gate_decision_allowed: bool = False
    connector_activation_allowed: bool = False
    scheduler_change_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["planned_stages"] = list(self.planned_stages)
        data["external_probe_stages"] = list(self.external_probe_stages)
        data["allowed_operator_actions"] = list(self.allowed_operator_actions)
        data["explicitly_disallowed_actions"] = list(self.explicitly_disallowed_actions)
        data["expected_stop_conditions"] = list(self.expected_stop_conditions)
        data["measurement_questions"] = list(self.measurement_questions)
        return data


def safety_boundary() -> dict[str, bool]:
    return {
        "read_only_default": True,
        "external_requests_executed_by_this_command": False,
        "external_requests_allowed_only_after_explicit_operator_run": True,
        "database_writes": False,
        "pipeline_mutation": False,
        "candidate_creation": False,
        "candidate_or_gate_mutation": False,
        "gate_decision": False,
        "connector_activation": False,
        "scheduler_mutation": False,
        "bronze_silver_gold_mutation": False,
    }


def build_trial_candidate(source_card: Mapping[str, Any]) -> ControlledTrialCandidate:
    company_key = _text(source_card.get("company_key"), default="unknown_company")
    company_name = _text(source_card.get("company_name"), default="<missing>")
    source_lane = _text(source_card.get("queue_lane"), default="unknown_lane")
    source_status = _text(source_card.get("ui_status"), default="unknown_status")
    source_rank = _int(source_card.get("ui_priority_rank"), default=999)
    evidence_badge = _text(source_card.get("evidence_badge"), default="unknown_evidence")

    lane, readiness, eligible, note = _trial_classification(source_lane, source_status, evidence_badge)
    priority_rank = _trial_priority_rank(source_rank, lane, eligible)

    return ControlledTrialCandidate(
        trial_id=f"expand001::{company_key}::{lane}",
        company_key=company_key,
        company_name=company_name,
        source_queue_lane=source_lane,
        source_ui_status=source_status,
        source_priority_rank=source_rank,
        source_evidence_badge=evidence_badge,
        trial_lane=lane,
        trial_readiness=readiness,
        trial_priority_rank=priority_rank,
        eligible_for_explicit_external_probe=eligible,
        planned_stages=DEFAULT_PLANNED_STAGES,
        external_probe_stages=EXTERNAL_STAGE_NAMES if eligible else (),
        allowed_operator_actions=ALLOWED_OPERATOR_ACTIONS if eligible else ("record_trial_result_as_review_artifact",),
        explicitly_disallowed_actions=EXPLICITLY_DISALLOWED_ACTIONS,
        expected_stop_conditions=_expected_stop_conditions(lane),
        measurement_questions=_measurement_questions(lane),
        trial_note=note,
    )


def build_trial_candidates(source_cards: Sequence[Mapping[str, Any]]) -> list[ControlledTrialCandidate]:
    candidates = [build_trial_candidate(card) for card in source_cards]
    return sorted(
        candidates,
        key=lambda item: (
            item.trial_priority_rank,
            item.trial_lane,
            item.company_name.lower(),
            item.company_key,
        ),
    )


def build_trial_report(
    source_report: Mapping[str, Any],
    *,
    generated_at: str | None = None,
    input_path: str | None = None,
    input_status: str = "ok",
    input_warning: str | None = None,
) -> dict[str, Any]:
    source_cards = _ensure_mapping_list(source_report.get("cards"))
    candidates = build_trial_candidates(source_cards) if input_status == "ok" else []
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "input_path": input_path,
        "input_status": input_status,
        "input_warning": input_warning,
        "input_schema_version": source_report.get("schema_version"),
        "safety_boundary": safety_boundary(),
        "interpretation_boundary": (
            "This report is a controlled trial plan for manually discovered market candidates. "
            "It prepares an explicit operator-run manifest and measurement framework only. "
            "It does not execute external requests, create candidates, write gate decisions, "
            "activate connectors, mutate pipeline data, or change scheduler behavior."
        ),
        "trial_policy": build_trial_policy(),
        "mutation_counts": {
            "created_candidates": 0,
            "automatic_candidate_promotions": 0,
            "written_gate_decisions": 0,
            "activated_connectors": 0,
            "scheduler_changes": 0,
            "bronze_silver_gold_writes": 0,
            "database_writes": 0,
            "external_requests_executed_by_this_command": 0,
        },
        "summary": build_summary(candidates),
        "trial_candidates": [candidate.as_dict() for candidate in candidates],
    }


def build_missing_input_report(path: Path, *, generated_at: str | None = None) -> dict[str, Any]:
    return build_trial_report(
        {},
        generated_at=generated_at,
        input_path=str(path),
        input_status="input_missing",
        input_warning=(
            "MARKET-003E queue-readiness output was not found. Run "
            "scripts/run_market003e_candidate_expansion_review_queue_readiness.py first."
        ),
    )


def build_invalid_input_report(path: Path, warning: str, *, generated_at: str | None = None) -> dict[str, Any]:
    return build_trial_report(
        {},
        generated_at=generated_at,
        input_path=str(path),
        input_status="input_invalid",
        input_warning=warning,
    )


def build_trial_policy() -> dict[str, Any]:
    return {
        "default_mode": "plan_only_no_external_requests",
        "external_credit_policy": "operator_may_choose_generous_budget_for_next_explicit_trial_run",
        "external_request_boundary": (
            "External origin/detail probes are planned but not executed by this report command. "
            "A future explicit run command may spend Tavily/search credits after operator approval."
        ),
        "candidate_creation_policy": "forbidden_in_this_work_item",
        "gate_policy": "measure_progress_and_stop_reasons_only_no_gate_decision",
        "connector_policy": "no_connector_activation_or_registration",
        "scheduler_policy": "no_scheduler_change_or_background_run",
        "result_handling_policy": "write_review_artifacts_only_until_a_separate_apply_workflow_exists",
    }


def build_summary(candidates: Sequence[ControlledTrialCandidate]) -> dict[str, Any]:
    lane_counts = Counter(candidate.trial_lane for candidate in candidates)
    readiness_counts = Counter(candidate.trial_readiness for candidate in candidates)
    eligible_count = sum(1 for candidate in candidates if candidate.eligible_for_explicit_external_probe)
    blocked_count = sum(1 for candidate in candidates if candidate.trial_readiness.startswith("blocked"))
    return {
        "candidate_count": len(candidates),
        "eligible_for_explicit_external_probe_count": eligible_count,
        "blocked_or_not_ready_count": blocked_count,
        "automatic_candidate_creation_count": 0,
        "automatic_promotion_count": 0,
        "gate_decision_count": 0,
        "connector_activation_count": 0,
        "external_requests_executed_by_this_command": 0,
        "trial_lane_counts": dict(sorted(lane_counts.items())),
        "trial_readiness_counts": dict(sorted(readiness_counts.items())),
    }


def load_source_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Input JSON root must be an object.")
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(INPUT_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected input schema_version: {schema_version or '<missing>'}")
    return payload


def write_outputs(report: Mapping[str, Any], export_dir: Path) -> dict[str, str]:
    export_dir.mkdir(parents=True, exist_ok=True)
    json_path = export_dir / "market003f_expand001_controlled_manual_candidate_pipeline_trial_plan.json"
    csv_path = export_dir / "market003f_expand001_controlled_manual_candidate_pipeline_trial_candidates.csv"
    md_path = export_dir / "market003f_expand001_controlled_manual_candidate_pipeline_trial_plan.md"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    write_candidates_csv(csv_path, report.get("trial_candidates", []))
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def write_candidates_csv(path: Path, candidates: Any) -> None:
    fieldnames = [
        "trial_id",
        "company_key",
        "company_name",
        "source_queue_lane",
        "source_ui_status",
        "source_priority_rank",
        "source_evidence_badge",
        "trial_lane",
        "trial_readiness",
        "trial_priority_rank",
        "eligible_for_explicit_external_probe",
        "planned_stages",
        "external_probe_stages",
        "allowed_operator_actions",
        "explicitly_disallowed_actions",
        "expected_stop_conditions",
        "measurement_questions",
        "trial_note",
        "no_mutation_boundary",
        "candidate_creation_allowed",
        "automatic_promotion_allowed",
        "gate_decision_allowed",
        "connector_activation_allowed",
        "scheduler_change_allowed",
    ]
    rows = candidates if isinstance(candidates, list) else []
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            rendered = dict(row)
            for list_field in (
                "planned_stages",
                "external_probe_stages",
                "allowed_operator_actions",
                "explicitly_disallowed_actions",
                "expected_stop_conditions",
                "measurement_questions",
            ):
                value = rendered.get(list_field)
                if isinstance(value, list):
                    rendered[list_field] = "; ".join(str(item) for item in value)
            writer.writerow({field: rendered.get(field) for field in fieldnames})


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    lines: list[str] = []
    lines.append("# MARKET-003F / EXPAND-001 Controlled Manual Candidate Pipeline Trial")
    lines.append("")
    lines.append("## Boundary")
    lines.append("")
    lines.append(
        "Plan-only controlled trial manifest. This command executes no external requests, creates no candidates, "
        "writes no gate decisions, activates no connectors, and changes no scheduler state."
    )
    lines.append("")
    if report.get("input_warning"):
        lines.append("## Input Warning")
        lines.append("")
        lines.append(str(report.get("input_warning")))
        lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Trial candidates: {summary.get('candidate_count', 0)}")
    lines.append(
        f"- Eligible for explicit external probe: {summary.get('eligible_for_explicit_external_probe_count', 0)}"
    )
    lines.append(f"- Blocked / not ready: {summary.get('blocked_or_not_ready_count', 0)}")
    lines.append(f"- Created candidates: {summary.get('automatic_candidate_creation_count', 0)}")
    lines.append(f"- Automatic promotions: {summary.get('automatic_promotion_count', 0)}")
    lines.append(f"- Gate decisions: {summary.get('gate_decision_count', 0)}")
    lines.append(f"- Connector activations: {summary.get('connector_activation_count', 0)}")
    lines.append(
        f"- External requests executed by this command: "
        f"{summary.get('external_requests_executed_by_this_command', 0)}"
    )
    lines.append("")
    lines.append("## Trial Policy")
    lines.append("")
    lines.append("External origin/detail probes may be intentionally expensive in a future explicit run, but this report only prepares the manifest.")
    lines.append("No Tavily/search credits are spent by this command.")
    lines.append("")
    lines.append("## Trial Candidates")
    lines.append("")
    candidates = report.get("trial_candidates", [])
    if not isinstance(candidates, list) or not candidates:
        lines.append("No trial candidates available.")
    else:
        lines.append("| Priority | Company | Trial lane | Readiness | External probe | Note |")
        lines.append("|---:|---|---|---|---|---|")
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue
            lines.append(
                "| "
                + str(candidate.get("trial_priority_rank", ""))
                + " | "
                + _md_cell(candidate.get("company_name"))
                + " | "
                + _md_cell(candidate.get("trial_lane"))
                + " | "
                + _md_cell(candidate.get("trial_readiness"))
                + " | "
                + _md_cell(str(candidate.get("eligible_for_explicit_external_probe", False)))
                + " | "
                + _md_cell(candidate.get("trial_note"))
                + " |"
            )
    lines.append("")
    lines.append("## Explicit Non-Actions")
    lines.append("")
    lines.append("- No automatic candidate creation")
    lines.append("- No automatic promotion")
    lines.append("- No gate decision")
    lines.append("- No connector activation")
    lines.append("- No scheduler mutation")
    lines.append("- No Bronze/Silver/Gold mutation")
    return "\n".join(lines) + "\n"


def _trial_classification(source_lane: str, source_status: str, evidence_badge: str) -> tuple[str, str, bool, str]:
    if source_lane == "needs_human_candidate_expansion_review" and source_status == "review_required":
        return (
            "ready_for_controlled_external_trial",
            "ready_for_trial_plan",
            True,
            "Candidate is suitable for a controlled explicit origin/detail evidence trial.",
        )
    if source_lane == "known_candidate_context_review":
        return (
            "known_candidate_context_revalidation",
            "context_only_trial_plan",
            True,
            "Evidence may be useful for existing candidate context; do not create a new candidate automatically.",
        )
    if source_lane == "identity_resolution_needed" or "identity" in evidence_badge:
        return (
            "blocked_until_identity_review",
            "blocked_identity_gap",
            False,
            "Company identity must be clarified before external pipeline trial.",
        )
    if source_lane == "parked_market_context":
        return (
            "parked_not_trial_ready",
            "not_trial_ready_insufficient_evidence",
            False,
            "Market context is retained but not strong enough for external trial yet.",
        )
    return (
        "unclassified_manual_review_needed",
        "blocked_unclassified_input",
        False,
        "Input could not be classified safely; manual review required before trial.",
    )


def _trial_priority_rank(source_rank: int, lane: str, eligible: bool) -> int:
    if not eligible:
        return 900 + max(source_rank, 0)
    if lane == "ready_for_controlled_external_trial":
        return max(source_rank, 1)
    if lane == "known_candidate_context_revalidation":
        return 100 + max(source_rank, 1)
    return 500 + max(source_rank, 1)


def _expected_stop_conditions(lane: str) -> tuple[str, ...]:
    if lane == "ready_for_controlled_external_trial":
        return (
            "no_origin_url_found",
            "origin_url_ambiguous_or_provider_only",
            "no_concrete_detail_pages_found",
            "detail_pages_do_not_show_target_or_remote_signal",
            "duplicate_or_known_company_context_detected",
        )
    if lane == "known_candidate_context_revalidation":
        return (
            "context_does_not_change_existing_candidate_state",
            "evidence_is_duplicate_of_existing_record",
            "detail_page_context_missing",
        )
    if lane == "blocked_until_identity_review":
        return ("company_identity_not_confirmed", "unsafe_name_equivalence_assumption")
    return ("insufficient_market_signal", "manual_review_required_before_probe")


def _measurement_questions(lane: str) -> tuple[str, ...]:
    base = (
        "How far did the candidate progress before a controlled stop?",
        "Which evidence class was missing at the stop?",
        "Did the result reveal a false-positive or false-negative risk?",
    )
    if lane == "ready_for_controlled_external_trial":
        return base + (
            "Was a plausible employer-origin URL discovered?",
            "Was concrete detail-page evidence discovered?",
            "Would a separate human-approved promotion workflow be justified?",
        )
    if lane == "known_candidate_context_revalidation":
        return base + ("Did the signal add new evidence to an already known candidate?",)
    return base + ("What manual clarification is required before external probing?",)


def _ensure_mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _text(value: Any, *, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _md_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
