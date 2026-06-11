from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "market003e.candidate_expansion_review_ui_queue_readiness.v1"
WORK_ITEM = "MARKET-003E Candidate Expansion Review UI/Queue Readiness"
INPUT_SCHEMA_PREFIX = "market003d.candidate_expansion_review_action_plan"
NO_MUTATION_BOUNDARY = "ui_queue_readmodel_only_no_candidate_creation_no_gate_decision_no_connector_activation"

DISPLAY_ACTIONS = (
    "open_read_only_review_dialog",
    "copy_company_name",
    "copy_company_key",
    "mark_for_manual_follow_up_outside_pipeline",
)

DISABLED_MUTATING_ACTIONS = (
    "create_candidate",
    "promote_candidate",
    "write_gate_decision",
    "activate_connector",
    "schedule_ingestion",
    "mutate_bronze_silver_gold",
    "write_database_state",
)

REVIEW_DIALOG_SECTIONS = (
    "company_identity",
    "market_evidence_context",
    "evidence_gaps",
    "allowed_review_actions",
    "explicit_non_actions_boundary",
)

PRIORITY_RANK = {
    "high": 10,
    "medium": 20,
    "low": 30,
}


@dataclass(frozen=True)
class CandidateExpansionReviewQueueCard:
    queue_id: str
    company_key: str
    company_name: str
    queue_lane: str
    ui_status: str
    ui_priority_rank: int
    priority_label: str
    evidence_badge: str
    headline: str
    subline: str
    display_actions: tuple[str, ...]
    disabled_mutating_actions: tuple[str, ...]
    review_dialog_sections: tuple[str, ...]
    source_review_bucket: str
    source_review_priority: str
    source_next_safe_action: str
    source_evidence_gap: str | None
    no_mutation_boundary: str = NO_MUTATION_BOUNDARY
    read_only: bool = True
    candidate_creation_allowed: bool = False
    gate_decision_allowed: bool = False
    connector_activation_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["display_actions"] = list(self.display_actions)
        data["disabled_mutating_actions"] = list(self.disabled_mutating_actions)
        data["review_dialog_sections"] = list(self.review_dialog_sections)
        return data


def safety_boundary() -> dict[str, bool]:
    return {
        "read_only": True,
        "external_requests": False,
        "database_writes": False,
        "pipeline_mutation": False,
        "candidate_creation": False,
        "candidate_or_gate_mutation": False,
        "gate_decision": False,
        "connector_activation": False,
        "scheduler_mutation": False,
        "bronze_silver_gold_mutation": False,
        "ui_write_actions": False,
    }


def build_queue_card(source_item: Mapping[str, Any]) -> CandidateExpansionReviewQueueCard:
    company_key = _text(source_item.get("company_key"), default="unknown_company")
    company_name = _text(source_item.get("company_name"), default="<missing>")
    bucket = _text(source_item.get("review_bucket"), default="unknown_bucket")
    source_priority = _text(source_item.get("review_priority"), default="low")
    next_action = _text(source_item.get("source_next_safe_action"), default="unknown")
    evidence_gap = _optional_text(source_item.get("evidence_gap"))
    lane, status = _lane_and_status(bucket)
    priority_rank = _priority_rank(source_priority, lane)
    evidence_badge = _evidence_badge(evidence_gap, bucket)

    return CandidateExpansionReviewQueueCard(
        queue_id=f"market003e::{company_key}::{lane}",
        company_key=company_key,
        company_name=company_name,
        queue_lane=lane,
        ui_status=status,
        ui_priority_rank=priority_rank,
        priority_label=source_priority if source_priority in PRIORITY_RANK else "low",
        evidence_badge=evidence_badge,
        headline=_headline(company_name, lane, evidence_badge),
        subline=_subline(status, evidence_gap),
        display_actions=DISPLAY_ACTIONS,
        disabled_mutating_actions=DISABLED_MUTATING_ACTIONS,
        review_dialog_sections=REVIEW_DIALOG_SECTIONS,
        source_review_bucket=bucket,
        source_review_priority=source_priority,
        source_next_safe_action=next_action,
        source_evidence_gap=evidence_gap,
    )


def build_queue_cards(source_items: Sequence[Mapping[str, Any]]) -> list[CandidateExpansionReviewQueueCard]:
    cards = [build_queue_card(item) for item in source_items]
    return sorted(cards, key=lambda card: (card.ui_priority_rank, card.queue_lane, card.company_name.lower(), card.company_key))


def build_queue_readiness_report(
    source_report: Mapping[str, Any],
    *,
    generated_at: str | None = None,
    input_path: str | None = None,
    input_status: str = "ok",
    input_warning: str | None = None,
) -> dict[str, Any]:
    source_items = _ensure_mapping_list(source_report.get("items"))
    cards = build_queue_cards(source_items) if input_status == "ok" else []
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
            "This is a read-only UI/queue readiness model derived from MARKET-003D review action-plan output. "
            "It is display material for a future queue UI, not an apply workflow, not a candidate promotion, "
            "not a gate decision, and not connector activation."
        ),
        "ui_contract": build_ui_contract(),
        "mutation_counts": {
            "created_candidates": 0,
            "written_gate_decisions": 0,
            "activated_connectors": 0,
            "scheduler_changes": 0,
            "bronze_silver_gold_writes": 0,
            "database_writes": 0,
            "ui_write_actions": 0,
        },
        "summary": build_summary(cards),
        "cards": [card.as_dict() for card in cards],
    }


def build_missing_input_report(path: Path, *, generated_at: str | None = None) -> dict[str, Any]:
    return build_queue_readiness_report(
        {},
        generated_at=generated_at,
        input_path=str(path),
        input_status="input_missing",
        input_warning=(
            "MARKET-003D action-plan output was not found. Run "
            "scripts/run_market003d_candidate_expansion_review_action_plan.py first."
        ),
    )


def build_invalid_input_report(path: Path, warning: str, *, generated_at: str | None = None) -> dict[str, Any]:
    return build_queue_readiness_report(
        {},
        generated_at=generated_at,
        input_path=str(path),
        input_status="input_invalid",
        input_warning=warning,
    )


def build_ui_contract() -> dict[str, Any]:
    return {
        "read_only_queue_model": True,
        "allowed_frontend_capabilities": [
            "display_queue_lanes",
            "filter_by_lane_status_priority_or_evidence_gap",
            "open_read_only_review_dialog",
            "copy_review_context",
            "export_queue_cards",
        ],
        "disallowed_frontend_capabilities": [
            "create_candidate_button",
            "promote_candidate_button",
            "approve_gate_button",
            "activate_connector_button",
            "run_scheduler_button",
            "write_database_state",
        ],
        "future_write_workflows_require_separate_work_item": True,
    }


def build_summary(cards: Sequence[CandidateExpansionReviewQueueCard]) -> dict[str, Any]:
    lane_counts = Counter(card.queue_lane for card in cards)
    status_counts = Counter(card.ui_status for card in cards)
    evidence_badge_counts = Counter(card.evidence_badge for card in cards)
    review_required_count = sum(1 for card in cards if card.ui_status == "review_required")
    blocked_count = sum(1 for card in cards if card.ui_status.startswith("blocked"))
    return {
        "card_count": len(cards),
        "review_required_count": review_required_count,
        "blocked_count": blocked_count,
        "candidate_creation_count": 0,
        "gate_decision_count": 0,
        "connector_activation_count": 0,
        "ui_write_action_count": 0,
        "lane_counts": dict(sorted(lane_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "evidence_badge_counts": dict(sorted(evidence_badge_counts.items())),
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
    json_path = export_dir / "market003e_candidate_expansion_review_ui_queue_readiness.json"
    csv_path = export_dir / "market003e_candidate_expansion_review_ui_queue_cards.csv"
    md_path = export_dir / "market003e_candidate_expansion_review_ui_queue_readiness.md"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    write_cards_csv(csv_path, report.get("cards", []))
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def write_cards_csv(path: Path, cards: Any) -> None:
    fieldnames = [
        "queue_id",
        "company_key",
        "company_name",
        "queue_lane",
        "ui_status",
        "ui_priority_rank",
        "priority_label",
        "evidence_badge",
        "headline",
        "subline",
        "display_actions",
        "disabled_mutating_actions",
        "review_dialog_sections",
        "source_review_bucket",
        "source_review_priority",
        "source_next_safe_action",
        "source_evidence_gap",
        "no_mutation_boundary",
        "read_only",
        "candidate_creation_allowed",
        "gate_decision_allowed",
        "connector_activation_allowed",
    ]
    rows = cards if isinstance(cards, list) else []
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            rendered = dict(row)
            for list_field in ("display_actions", "disabled_mutating_actions", "review_dialog_sections"):
                value = rendered.get(list_field)
                if isinstance(value, list):
                    rendered[list_field] = "; ".join(str(item) for item in value)
            writer.writerow({field: rendered.get(field) for field in fieldnames})


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    mutation_counts = report.get("mutation_counts") if isinstance(report.get("mutation_counts"), Mapping) else {}
    ui_contract = report.get("ui_contract") if isinstance(report.get("ui_contract"), Mapping) else {}

    lines = [
        "# MARKET-003E Candidate Expansion Review UI Queue Readiness",
        "",
        f"Schema: `{report.get('schema_version')}`",
        "",
        "## Status",
        "",
        f"- Input status: `{report.get('input_status')}`",
        f"- Input path: `{report.get('input_path')}`",
    ]
    if report.get("input_warning"):
        lines.append(f"- Input warning: {report.get('input_warning')}")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Queue cards: {summary.get('card_count', 0)}",
            f"- Review required: {summary.get('review_required_count', 0)}",
            f"- Blocked cards: {summary.get('blocked_count', 0)}",
            f"- Created candidates: {summary.get('candidate_creation_count', 0)}",
            f"- Gate decisions: {summary.get('gate_decision_count', 0)}",
            f"- Connector activations: {summary.get('connector_activation_count', 0)}",
            "",
            "## Read-only UI queue model",
            "",
            "Mutation counts:",
            "",
        ]
    )
    for key, value in mutation_counts.items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "Important zero-counts:",
            "",
            f"- UI write actions: {mutation_counts.get('ui_write_actions', 0)}",
            f"- Database writes: {mutation_counts.get('database_writes', 0)}",
            f"- Bronze/Silver/Gold writes: {mutation_counts.get('bronze_silver_gold_writes', 0)}",
            "",
            "## Lanes",
            "",
        ]
    )
    lanes = summary.get("lane_counts", {}) if isinstance(summary, Mapping) else {}
    if isinstance(lanes, Mapping) and lanes:
        for key, value in lanes.items():
            lines.append(f"- `{key}`: {value}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Statuses",
            "",
        ]
    )
    statuses = summary.get("status_counts", {}) if isinstance(summary, Mapping) else {}
    if isinstance(statuses, Mapping) and statuses:
        for key, value in statuses.items():
            lines.append(f"- `{key}`: {value}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## UI Contract",
            "",
            "Allowed frontend capabilities:",
            "",
        ]
    )
    allowed = ui_contract.get("allowed_frontend_capabilities", [])
    for item in allowed if isinstance(allowed, list) else []:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "Disallowed frontend capabilities:",
            "",
        ]
    )
    disallowed = ui_contract.get("disallowed_frontend_capabilities", [])
    for item in disallowed if isinstance(disallowed, list) else []:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Queue Cards",
            "",
            "| Rank | Company | Lane | Status | Evidence | Headline |",
            "|---:|---|---|---|---|---|",
        ]
    )
    for card in report.get("cards", []):
        if not isinstance(card, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                _md_cell(value)
                for value in (
                    card.get("ui_priority_rank"),
                    card.get("company_name"),
                    card.get("queue_lane"),
                    card.get("ui_status"),
                    card.get("evidence_badge"),
                    card.get("headline"),
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            str(report.get("interpretation_boundary") or ""),
        ]
    )
    return "\n".join(lines) + "\n"

def _lane_and_status(bucket: str) -> tuple[str, str]:
    if bucket == "candidate_expansion_human_review_queue":
        return "needs_human_candidate_expansion_review", "review_required"
    if bucket == "known_candidate_context_queue":
        return "known_candidate_context_review", "context_review"
    if bucket == "identity_gap_queue":
        return "identity_resolution_needed", "blocked_identity_gap"
    if bucket == "insufficient_evidence_context_queue":
        return "parked_market_context", "insufficient_evidence"
    return "unclassified_review_context", "blocked_unclassified_input"


def _priority_rank(priority: str, lane: str) -> int:
    base = PRIORITY_RANK.get(priority, 30)
    lane_offset = {
        "needs_human_candidate_expansion_review": 0,
        "identity_resolution_needed": 5,
        "known_candidate_context_review": 10,
        "parked_market_context": 20,
        "unclassified_review_context": 30,
    }.get(lane, 30)
    return base + lane_offset


def _evidence_badge(evidence_gap: str | None, bucket: str) -> str:
    if bucket == "identity_gap_queue" or evidence_gap == "company_identity_missing":
        return "identity_gap"
    if evidence_gap in (None, "none", ""):
        return "evidence_ready_for_human_review"
    if evidence_gap == "needs_origin_or_detail_evidence":
        return "needs_origin_or_detail_evidence"
    if evidence_gap == "weak_market_signal":
        return "weak_signal"
    return "needs_review"


def _headline(company_name: str, lane: str, evidence_badge: str) -> str:
    if lane == "needs_human_candidate_expansion_review":
        return f"Review candidate-expansion signal for {company_name}"
    if lane == "known_candidate_context_review":
        return f"Review additional context for known candidate {company_name}"
    if lane == "identity_resolution_needed":
        return f"Resolve company identity before considering {company_name}"
    if lane == "parked_market_context":
        return f"Park weak market context for {company_name}"
    return f"Review unclassified market signal for {company_name} ({evidence_badge})"


def _subline(status: str, evidence_gap: str | None) -> str:
    if status == "review_required":
        return "Human review can inspect evidence and collect more context, but cannot create a candidate here."
    if status == "context_review":
        return "Context may support an existing candidate, but remains non-mutating review input."
    if status == "blocked_identity_gap":
        return "Company identity is not safe enough for decision use."
    if status == "insufficient_evidence":
        return "Signal is retained as weak context only."
    return f"Unclassified input requires inspection before UI use. Evidence gap: {evidence_gap or 'none'}."


def _text(value: Any, *, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "none":
        return None
    return text


def _ensure_mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _md_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")

