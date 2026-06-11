from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "market003c.candidate_expansion_review_no_promotion.v1"
WORK_ITEM = "MARKET-003C Candidate Expansion Review without automatic promotion"
NO_PROMOTION_BOUNDARY = "review_only_no_candidate_creation_no_gate_decision_no_connector_activation"

COMPANY_NAME_FIELDS = (
    "company_name",
    "employer_name",
    "observed_company_name",
    "observed_employer_name",
    "company",
    "organization_name",
    "organisation_name",
)
COMPANY_KEY_FIELDS = ("company_key", "employer_key", "normalized_company_key")
URL_FIELDS = ("source_url", "evidence_url", "url", "job_url", "posting_url", "linkedin_url")
TITLE_FIELDS = ("job_title", "title", "role_title", "posting_title")
SOURCE_FIELDS = ("evidence_origin", "observation_origin", "evidence_source", "source", "source_family", "origin")
NOTES_FIELDS = ("notes", "comment", "reason", "description", "evidence_notes")
PROFILE_FIELDS = ("profile_terms", "matched_terms", "relevance_signals", "skills", "tags")
MANUAL_MARKERS = ("manual_market_observation", "manual_observation", "manual", "human_observed")


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


@dataclass(frozen=True)
class CandidateExpansionReviewItem:
    market_evidence_id: str | None
    company_key: str
    company_name: str
    evidence_origin: str
    evidence_kind: str
    source_reference: str | None
    observed_job_title: str | None
    evidence_strength_score: int
    known_candidate_id: str | None
    known_candidate_status: str | None
    review_recommendation: str
    recommended_next_safe_action: str
    promotion_blocker: str
    rationale: str
    candidate_creation_allowed: bool = False
    gate_decision_allowed: bool = False
    connector_activation_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_company_key(value: Any) -> str:
    """Create a conservative key without asserting company equivalence.

    The function intentionally does not strip legal suffixes. Removing suffixes can
    collapse distinct entities and would turn an unvalidated simplification into a
    decision fact. The key is only a review/grouping helper.
    """
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "unknown_company"


def first_text(payload: Mapping[str, Any], fields: Sequence[str]) -> str | None:
    for field in fields:
        value = payload.get(field)
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            rendered = "; ".join(str(item).strip() for item in value if str(item).strip())
        elif isinstance(value, dict):
            rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            rendered = str(value).strip()
        if rendered:
            return rendered
    return None


def extract_company_name(payload: Mapping[str, Any]) -> str:
    return first_text(payload, COMPANY_NAME_FIELDS) or ""


def extract_company_key(payload: Mapping[str, Any]) -> str:
    explicit = first_text(payload, COMPANY_KEY_FIELDS)
    if explicit:
        return normalize_company_key(explicit)
    return normalize_company_key(extract_company_name(payload))


def has_manual_marker(payload: Mapping[str, Any]) -> bool:
    values = " ".join(str(value).lower() for value in payload.values() if value is not None)
    return any(marker in values for marker in MANUAL_MARKERS)


def evidence_strength_score(payload: Mapping[str, Any], *, company_name: str) -> int:
    score = 0
    if company_name:
        score += 1
    if first_text(payload, URL_FIELDS):
        score += 1
    if first_text(payload, TITLE_FIELDS):
        score += 1
    if first_text(payload, SOURCE_FIELDS):
        score += 1
    if first_text(payload, NOTES_FIELDS):
        score += 1
    if first_text(payload, PROFILE_FIELDS):
        score += 1
    if has_manual_marker(payload):
        score += 1
    return score


def build_known_candidate_index(candidate_payloads: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for candidate in candidate_payloads:
        keys = {
            normalize_company_key(candidate.get("company_key")),
            normalize_company_key(candidate.get("company_name")),
        }
        for key in keys:
            if key and key != "unknown_company":
                index.setdefault(key, candidate)
    return index


def classify_review_item(
    *,
    payload: Mapping[str, Any],
    known_candidate: Mapping[str, Any] | None,
) -> CandidateExpansionReviewItem:
    company_name = extract_company_name(payload)
    company_key = extract_company_key(payload)
    strength = evidence_strength_score(payload, company_name=company_name)
    evidence_origin = first_text(payload, SOURCE_FIELDS) or "unknown"
    source_reference = first_text(payload, URL_FIELDS)
    observed_job_title = first_text(payload, TITLE_FIELDS)
    market_evidence_id_value = payload.get("id") or payload.get("market_evidence_id") or payload.get("evidence_id")
    market_evidence_id = str(market_evidence_id_value) if market_evidence_id_value is not None else None
    known_candidate_id_value = known_candidate.get("id") if known_candidate else None
    known_candidate_id = str(known_candidate_id_value) if known_candidate_id_value is not None else None
    known_candidate_status = str(known_candidate.get("status")) if known_candidate and known_candidate.get("status") is not None else None
    is_manual = has_manual_marker(payload)

    if not company_name:
        recommendation = "insufficient_evidence_missing_company"
        next_action = "ignore_until_company_identity_is_clear"
        rationale = "No explicit company name was found in the market evidence payload."
        evidence_kind = "unattributed_market_evidence"
    elif known_candidate_id:
        recommendation = "known_candidate_review_context_only"
        next_action = "link_as_review_context_without_candidate_creation"
        rationale = "A matching employer-origin candidate already exists; this evidence is context only."
        evidence_kind = "known_candidate_context"
    elif is_manual and strength >= 3:
        recommendation = "manual_review_required_manual_market_signal"
        next_action = "manual_candidate_expansion_review"
        rationale = "Manual market observation has enough context for human review, but not for automatic promotion."
        evidence_kind = "manual_market_observation"
    elif strength >= 4:
        recommendation = "manual_review_required_evidence_rich_market_signal"
        next_action = "manual_candidate_expansion_review"
        rationale = "Market evidence is relatively rich, but candidate creation still requires explicit human review."
        evidence_kind = "market_signal"
    else:
        recommendation = "insufficient_evidence_review_context_only"
        next_action = "retain_as_market_context_without_candidate_creation"
        rationale = "Evidence is not strong enough for a candidate-expansion review decision."
        evidence_kind = "weak_market_signal"

    return CandidateExpansionReviewItem(
        market_evidence_id=market_evidence_id,
        company_key=company_key,
        company_name=company_name or "<missing>",
        evidence_origin=evidence_origin,
        evidence_kind=evidence_kind,
        source_reference=source_reference,
        observed_job_title=observed_job_title,
        evidence_strength_score=strength,
        known_candidate_id=known_candidate_id,
        known_candidate_status=known_candidate_status,
        review_recommendation=recommendation,
        recommended_next_safe_action=next_action,
        promotion_blocker=NO_PROMOTION_BOUNDARY,
        rationale=rationale,
    )


def build_review_items(
    market_evidence_payloads: Sequence[Mapping[str, Any]],
    existing_candidate_payloads: Sequence[Mapping[str, Any]],
) -> list[CandidateExpansionReviewItem]:
    known_candidates = build_known_candidate_index(existing_candidate_payloads)
    items: list[CandidateExpansionReviewItem] = []
    for payload in market_evidence_payloads:
        company_key = extract_company_key(payload)
        known_candidate = known_candidates.get(company_key)
        items.append(classify_review_item(payload=payload, known_candidate=known_candidate))
    return items


def build_summary(items: Sequence[CandidateExpansionReviewItem]) -> dict[str, Any]:
    recommendation_counts = Counter(item.review_recommendation for item in items)
    next_action_counts = Counter(item.recommended_next_safe_action for item in items)
    known_count = sum(1 for item in items if item.known_candidate_id)
    manual_review_count = sum(
        1 for item in items if item.recommended_next_safe_action == "manual_candidate_expansion_review"
    )
    return {
        "item_count": len(items),
        "known_candidate_context_count": known_count,
        "manual_review_required_count": manual_review_count,
        "candidate_creation_count": 0,
        "gate_decision_count": 0,
        "connector_activation_count": 0,
        "recommendation_counts": dict(sorted(recommendation_counts.items())),
        "next_action_counts": dict(sorted(next_action_counts.items())),
    }


def build_report(
    *,
    market_evidence_payloads: Sequence[Mapping[str, Any]],
    existing_candidate_payloads: Sequence[Mapping[str, Any]],
    generated_at: str | None = None,
    db_access_method: str | None = None,
    input_status: str = "ok",
    input_warning: str | None = None,
) -> dict[str, Any]:
    items = build_review_items(market_evidence_payloads, existing_candidate_payloads)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "overall_status": input_status,
        "input_warning": input_warning,
        "db_access_method": db_access_method,
        "safety_boundary": safety_boundary(),
        "interpretation_boundary": (
            "This is a review-only candidate expansion report. It does not create employer-origin "
            "candidates, write gate decisions, activate connectors, mutate Bronze/Silver/Gold, or "
            "change scheduler state. Recommendations are review queues, not approvals."
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


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    lines: list[str] = []
    lines.append("# MARKET-003C Candidate Expansion Review")
    lines.append("")
    lines.append("## Boundary")
    lines.append("")
    lines.append("Review-only. No automatic candidate creation, no gate decision, no connector activation.")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- Items: {summary.get('item_count', 0)}")
    lines.append(f"- Manual review required: {summary.get('manual_review_required_count', 0)}")
    lines.append(f"- Known candidate context: {summary.get('known_candidate_context_count', 0)}")
    lines.append(f"- Created candidates: {summary.get('candidate_creation_count', 0)}")
    lines.append(f"- Gate decisions: {summary.get('gate_decision_count', 0)}")
    lines.append(f"- Connector activations: {summary.get('connector_activation_count', 0)}")
    lines.append("")
    lines.append("## Recommendation Counts")
    lines.append("")
    recommendation_counts = summary.get("recommendation_counts", {})
    if isinstance(recommendation_counts, Mapping) and recommendation_counts:
        for key, value in recommendation_counts.items():
            lines.append(f"- `{key}`: {value}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Review Items")
    lines.append("")
    lines.append("| Company | Recommendation | Next Action | Known Candidate | Strength | Rationale |")
    lines.append("|---|---|---|---|---:|---|")
    for item in report.get("items", []):
        if not isinstance(item, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                _md_cell(value)
                for value in (
                    item.get("company_name"),
                    item.get("review_recommendation"),
                    item.get("recommended_next_safe_action"),
                    item.get("known_candidate_id") or "no",
                    item.get("evidence_strength_score"),
                    item.get("rationale"),
                )
            )
            + " |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(str(report.get("interpretation_boundary") or ""))
    return "\n".join(lines) + "\n"


def _md_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")


def write_outputs(report: Mapping[str, Any], export_dir: Path) -> dict[str, str]:
    export_dir.mkdir(parents=True, exist_ok=True)
    json_path = export_dir / "market003c_candidate_expansion_review.json"
    csv_path = export_dir / "market003c_candidate_expansion_review_items.csv"
    md_path = export_dir / "market003c_candidate_expansion_review.md"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    write_items_csv(csv_path, report.get("items", []))
    md_path.write_text(render_markdown(report), encoding="utf-8")

    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def write_items_csv(path: Path, items: Any) -> None:
    fieldnames = [
        "market_evidence_id",
        "company_key",
        "company_name",
        "evidence_origin",
        "evidence_kind",
        "source_reference",
        "observed_job_title",
        "evidence_strength_score",
        "known_candidate_id",
        "known_candidate_status",
        "review_recommendation",
        "recommended_next_safe_action",
        "promotion_blocker",
        "rationale",
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
            writer.writerow({field: row.get(field) for field in fieldnames})
