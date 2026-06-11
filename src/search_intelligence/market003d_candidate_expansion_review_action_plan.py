from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "market003d.candidate_expansion_review_action_plan.v1"
WORK_ITEM = "MARKET-003D Candidate Expansion Review Action Plan"
INPUT_SCHEMA_PREFIX = "market003c.candidate_expansion_review_no_promotion"
NO_MUTATION_BOUNDARY = "review_action_plan_only_no_candidate_creation_no_gate_decision_no_connector_activation"

MANUAL_REVIEW_ACTION = "manual_candidate_expansion_review"
KNOWN_CONTEXT_ACTION = "link_as_review_context_without_candidate_creation"
RETAIN_CONTEXT_ACTION = "retain_as_market_context_without_candidate_creation"
IGNORE_UNTIL_CLEAR_ACTION = "ignore_until_company_identity_is_clear"

ALLOWED_REVIEW_ACTIONS = (
    "inspect_company_identity",
    "collect_origin_url_evidence",
    "collect_detail_page_evidence",
    "confirm_known_candidate_context",
    "park_as_insufficient_evidence",
    "request_assumption_review",
)

DISALLOWED_ACTIONS = (
    "create_candidate",
    "write_gate_decision",
    "activate_connector",
    "mutate_bronze_silver_gold",
    "change_scheduler",
)


@dataclass(frozen=True)
class CandidateExpansionReviewActionItem:
    company_key: str
    company_name: str
    source_review_recommendation: str
    source_next_safe_action: str
    source_evidence_strength_score: int
    review_bucket: str
    review_priority: str
    allowed_review_actions: tuple[str, ...]
    disallowed_actions: tuple[str, ...]
    human_review_question: str
    evidence_gap: str | None
    no_mutation_boundary: str = NO_MUTATION_BOUNDARY
    candidate_creation_allowed: bool = False
    gate_decision_allowed: bool = False
    connector_activation_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["allowed_review_actions"] = list(self.allowed_review_actions)
        data["disallowed_actions"] = list(self.disallowed_actions)
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
    }


def build_action_item(source_item: Mapping[str, Any]) -> CandidateExpansionReviewActionItem:
    company_key = _text(source_item.get("company_key"), default="unknown_company")
    company_name = _text(source_item.get("company_name"), default="<missing>")
    recommendation = _text(source_item.get("review_recommendation"), default="unknown")
    next_action = _text(source_item.get("recommended_next_safe_action"), default="unknown")
    strength = _int(source_item.get("evidence_strength_score"))
    known_candidate_id = _text(source_item.get("known_candidate_id"), default="")

    if next_action == MANUAL_REVIEW_ACTION:
        bucket = "candidate_expansion_human_review_queue"
        priority = _priority_for_strength(strength)
        allowed = (
            "inspect_company_identity",
            "collect_origin_url_evidence",
            "collect_detail_page_evidence",
            "request_assumption_review",
        )
        question = (
            "Should this market signal become a candidate-expansion proposal in a separate, "
            "explicitly approved future workflow?"
        )
        evidence_gap = _evidence_gap_for_strength(strength)
    elif next_action == KNOWN_CONTEXT_ACTION or known_candidate_id:
        bucket = "known_candidate_context_queue"
        priority = "medium"
        allowed = ("confirm_known_candidate_context", "collect_detail_page_evidence")
        question = "Does this evidence add useful context to an existing candidate without creating a new one?"
        evidence_gap = None
    elif next_action == IGNORE_UNTIL_CLEAR_ACTION:
        bucket = "identity_gap_queue"
        priority = "low"
        allowed = ("inspect_company_identity", "park_as_insufficient_evidence", "request_assumption_review")
        question = "Can the company identity be established without unsafe name-equivalence assumptions?"
        evidence_gap = "company_identity_missing"
    else:
        bucket = "insufficient_evidence_context_queue"
        priority = "low"
        allowed = ("park_as_insufficient_evidence", "collect_origin_url_evidence")
        question = "Is there enough additional evidence to keep observing this signal manually?"
        evidence_gap = _evidence_gap_for_strength(strength)

    return CandidateExpansionReviewActionItem(
        company_key=company_key,
        company_name=company_name,
        source_review_recommendation=recommendation,
        source_next_safe_action=next_action,
        source_evidence_strength_score=strength,
        review_bucket=bucket,
        review_priority=priority,
        allowed_review_actions=allowed,
        disallowed_actions=DISALLOWED_ACTIONS,
        human_review_question=question,
        evidence_gap=evidence_gap,
    )


def build_action_items(source_items: Sequence[Mapping[str, Any]]) -> list[CandidateExpansionReviewActionItem]:
    return [build_action_item(item) for item in source_items]


def build_action_plan(
    source_report: Mapping[str, Any],
    *,
    generated_at: str | None = None,
    input_path: str | None = None,
    input_status: str = "ok",
    input_warning: str | None = None,
) -> dict[str, Any]:
    source_items = _ensure_mapping_list(source_report.get("items"))
    items = build_action_items(source_items) if input_status == "ok" else []
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
            "This is a human review action plan derived from MARKET-003C review output. It is not a promotion plan, "
            "not an apply command, not a gate decision, and not connector activation. Every action remains review-only."
        ),
        "mutation_counts": {
            "created_candidates": 0,
            "written_gate_decisions": 0,
            "activated_connectors": 0,
            "scheduler_changes": 0,
            "bronze_silver_gold_writes": 0,
        },
        "summary": build_summary(items),
        "items": [item.as_dict() for item in items],
    }


def build_missing_input_plan(path: Path, *, generated_at: str | None = None) -> dict[str, Any]:
    return build_action_plan(
        {},
        generated_at=generated_at,
        input_path=str(path),
        input_status="input_missing",
        input_warning=(
            "MARKET-003C review output was not found. Run scripts/run_market003c_candidate_expansion_review.py first."
        ),
    )


def build_invalid_input_plan(path: Path, warning: str, *, generated_at: str | None = None) -> dict[str, Any]:
    return build_action_plan({}, generated_at=generated_at, input_path=str(path), input_status="input_invalid", input_warning=warning)


def build_summary(items: Sequence[CandidateExpansionReviewActionItem]) -> dict[str, Any]:
    bucket_counts = Counter(item.review_bucket for item in items)
    priority_counts = Counter(item.review_priority for item in items)
    human_review_queue_count = sum(1 for item in items if item.review_bucket == "candidate_expansion_human_review_queue")
    known_context_count = sum(1 for item in items if item.review_bucket == "known_candidate_context_queue")
    return {
        "item_count": len(items),
        "human_review_queue_count": human_review_queue_count,
        "known_candidate_context_count": known_context_count,
        "candidate_creation_count": 0,
        "gate_decision_count": 0,
        "connector_activation_count": 0,
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
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
    json_path = export_dir / "market003d_candidate_expansion_review_action_plan.json"
    csv_path = export_dir / "market003d_candidate_expansion_review_action_plan_items.csv"
    md_path = export_dir / "market003d_candidate_expansion_review_action_plan.md"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    write_items_csv(csv_path, report.get("items", []))
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def write_items_csv(path: Path, items: Any) -> None:
    fieldnames = [
        "company_key",
        "company_name",
        "source_review_recommendation",
        "source_next_safe_action",
        "source_evidence_strength_score",
        "review_bucket",
        "review_priority",
        "allowed_review_actions",
        "disallowed_actions",
        "human_review_question",
        "evidence_gap",
        "no_mutation_boundary",
        "candidate_creation_allowed",
        "gate_decision_allowed",
        "connector_activation_allowed",
    ]
    rows = items if isinstance(items, list) else []
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            rendered = dict(row)
            for list_field in ("allowed_review_actions", "disallowed_actions"):
                value = rendered.get(list_field)
                if isinstance(value, list):
                    rendered[list_field] = "; ".join(str(item) for item in value)
            writer.writerow({field: rendered.get(field) for field in fieldnames})


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    lines: list[str] = []
    lines.append("# MARKET-003D Candidate Expansion Review Action Plan")
    lines.append("")
    lines.append("## Boundary")
    lines.append("")
    lines.append("Review-only action planning. No automatic candidate creation, no gate decision, no connector activation.")
    lines.append("")
    if report.get("input_warning"):
        lines.append("## Input Warning")
        lines.append("")
        lines.append(str(report.get("input_warning")))
        lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- Items: {summary.get('item_count', 0)}")
    lines.append(f"- Human review queue: {summary.get('human_review_queue_count', 0)}")
    lines.append(f"- Known candidate context: {summary.get('known_candidate_context_count', 0)}")
    lines.append(f"- Created candidates: {summary.get('candidate_creation_count', 0)}")
    lines.append(f"- Gate decisions: {summary.get('gate_decision_count', 0)}")
    lines.append(f"- Connector activations: {summary.get('connector_activation_count', 0)}")
    lines.append("")
    lines.append("## Bucket Counts")
    lines.append("")
    bucket_counts = summary.get("bucket_counts", {})
    if isinstance(bucket_counts, Mapping) and bucket_counts:
        for key, value in bucket_counts.items():
            lines.append(f"- `{key}`: {value}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Review Action Items")
    lines.append("")
    lines.append("| Company | Bucket | Priority | Allowed review actions | Human review question | Evidence gap |")
    lines.append("|---|---|---|---|---|---|")
    for item in report.get("items", []):
        if not isinstance(item, Mapping):
            continue
        allowed = item.get("allowed_review_actions")
        if isinstance(allowed, list):
            allowed_text = ", ".join(str(value) for value in allowed)
        else:
            allowed_text = str(allowed or "")
        lines.append(
            "| "
            + " | ".join(
                _md_cell(value)
                for value in (
                    item.get("company_name"),
                    item.get("review_bucket"),
                    item.get("review_priority"),
                    allowed_text,
                    item.get("human_review_question"),
                    item.get("evidence_gap") or "none",
                )
            )
            + " |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(str(report.get("interpretation_boundary") or ""))
    return "\n".join(lines) + "\n"


def _priority_for_strength(strength: int) -> str:
    if strength >= 5:
        return "high"
    if strength >= 3:
        return "medium"
    return "low"


def _evidence_gap_for_strength(strength: int) -> str | None:
    if strength >= 5:
        return None
    if strength >= 3:
        return "needs_origin_or_detail_evidence"
    return "weak_market_signal"


def _text(value: Any, *, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _ensure_mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _md_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")
