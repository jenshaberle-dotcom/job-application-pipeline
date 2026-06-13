from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "generic009b.positive_proof_evidence.v1"
WORK_ITEM = "GENERIC-009B Positive Proof Evidence Integration"
BOUNDARY = "benchmark_review_artifact_only_no_candidate_or_gate_write"
POSITIVE_GAPS = (
    "benchmark_candidate_count",
    "strong_candidate_count",
    "weak_candidate_count",
    "clear_career_origin_coverage",
    "positive_control_coverage",
)
PROVIDER_GAP = "provider_backed_origin_coverage"


@dataclass(frozen=True)
class PositiveProofEvidenceRow:
    company_key: str
    company_name: str
    candidate_url: str
    positive_control_lane: str
    candidate_gap_coverage: tuple[str, ...]
    review_action: str
    evidence_strength: str
    top_strong_urls: tuple[str, ...]
    top_weak_urls: tuple[str, ...]
    benchmark_control_source: str
    benchmark_evidence_summary: str
    boundary: str
    status: str
    rejection_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["candidate_gap_coverage"] = list(self.candidate_gap_coverage)
        data["top_strong_urls"] = list(self.top_strong_urls)
        data["top_weak_urls"] = list(self.top_weak_urls)
        return data


def build_positive_proof_evidence_report(
    inventory_report: Mapping[str, Any],
    *,
    generated_at: str | None = None,
    max_positive_controls: int = 8,
) -> dict[str, Any]:
    rows = build_positive_proof_rows_from_inventory(
        inventory_report,
        max_positive_controls=max_positive_controls,
    )
    accepted = [row for row in rows if row.status == "accepted_positive_control"]
    rejected = [row for row in rows if row.status != "accepted_positive_control"]
    gap_counts = _gap_counts(accepted)
    covered_gaps = [gap for gap in (*POSITIVE_GAPS, PROVIDER_GAP) if gap_counts.get(gap, 0)]
    missing_gaps = [gap for gap in (*POSITIVE_GAPS, PROVIDER_GAP) if not gap_counts.get(gap, 0)]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "overall_status": "ready_for_generic005_positive_proof_rerun" if accepted else "no_positive_proof_evidence_ready",
        "safety_boundary": safety_boundary(),
        "summary": {
            "accepted_positive_control_count": len(accepted),
            "rejected_positive_control_count": len(rejected),
            "positive_control_keys": [row.company_key for row in accepted],
            "covered_gap_ids": covered_gaps,
            "missing_gap_ids": missing_gaps,
            "gap_candidate_counts": gap_counts,
        },
        "positive_proof_rows": [row.as_dict() for row in rows],
        "accepted_positive_proof_rows": [row.as_dict() for row in accepted],
        "rejected_positive_proof_rows": [row.as_dict() for row in rejected],
        "next_action": _next_action(accepted, missing_gaps),
    }


def safety_boundary() -> dict[str, bool | str]:
    return {
        "review_artifact_only": True,
        "database_reads": False,
        "database_writes": False,
        "external_requests": False,
        "candidate_creation": False,
        "candidate_promotion": False,
        "gate_decision": False,
        "connector_activation": False,
        "scheduler_change": False,
        "bronze_silver_gold_mutation": False,
        "csv_excel_or_export_as_input": False,
        "decision_boundary": "positive_proof_evidence_not_candidate_creation_not_gate_truth",
    }


def build_positive_proof_rows_from_inventory(
    inventory_report: Mapping[str, Any],
    *,
    max_positive_controls: int = 8,
) -> list[PositiveProofEvidenceRow]:
    items = _mapping_list(inventory_report.get("positive_control_inventory_items"))
    selected = _select_balanced_inventory_items(items, max_positive_controls=max_positive_controls)
    return [evaluate_inventory_item(item) for item in selected]


def evaluate_inventory_item(item: Mapping[str, Any]) -> PositiveProofEvidenceRow:
    company_key = _text(item.get("company_key"))
    company_name = _text(item.get("company_name"), default=company_key)
    candidate_url = _text(item.get("candidate_url"))
    lane = _text(item.get("positive_control_lane"))
    gaps = tuple(_string_list(item.get("candidate_gap_coverage")))
    review_action, evidence_strength, strong_urls, weak_urls = _review_projection(lane, candidate_url)
    rejection_reason = _positive_rejection_reason(company_key, company_name, lane, gaps)
    status = "rejected_positive_control" if rejection_reason else "accepted_positive_control"
    return PositiveProofEvidenceRow(
        company_key=company_key,
        company_name=company_name,
        candidate_url=candidate_url,
        positive_control_lane=lane,
        candidate_gap_coverage=gaps,
        review_action=review_action,
        evidence_strength=evidence_strength,
        top_strong_urls=tuple(strong_urls),
        top_weak_urls=tuple(weak_urls),
        benchmark_control_source="generic009b_positive_proof_evidence",
        benchmark_evidence_summary=(
            "DB-backed employer-origin candidate selected by GENERIC-009A/009B for positive benchmark proof only. "
            "This is not candidate creation, not a gate decision, and not connector activation."
        ),
        boundary=BOUNDARY,
        status=status,
        rejection_reason=rejection_reason,
    )


def build_positive_proof_expand003_report(
    expand003_report: Mapping[str, Any],
    accepted_rows: Sequence[PositiveProofEvidenceRow],
) -> dict[str, Any]:
    proof_items = [positive_row_to_expand003_item(row) for row in accepted_rows]
    augmented = dict(expand003_report)
    augmented["candidate_review_items"] = proof_items
    augmented["generic009b_benchmark_augmentation"] = {
        "positive_control_count": len(proof_items),
        "source": "generic009b_positive_proof_evidence",
        "boundary": BOUNDARY,
        "original_candidate_review_item_count": len(_mapping_list(expand003_report.get("candidate_review_items"))),
        "note": (
            "The broad EXPAND-003 review artifact is replaced by a bounded positive-control proof set for GENERIC-001 only. "
            "This avoids treating broad review volume as benchmark pass evidence."
        ),
    }
    return augmented


def positive_row_to_expand003_item(row: PositiveProofEvidenceRow) -> dict[str, Any]:
    return {
        "company_key": row.company_key,
        "company_name": row.company_name,
        "review_action": row.review_action,
        "evidence_strength": row.evidence_strength,
        "top_strong_urls": list(row.top_strong_urls),
        "top_weak_urls": list(row.top_weak_urls),
        "benchmark_control_source": row.benchmark_control_source,
        "benchmark_evidence_summary": row.benchmark_evidence_summary,
        "positive_control_lane": row.positive_control_lane,
    }


def positive_control_keys_from_rows(rows: Sequence[PositiveProofEvidenceRow]) -> list[str]:
    return _unique([row.company_key for row in rows if row.status == "accepted_positive_control"])


def _select_balanced_inventory_items(
    items: Sequence[Mapping[str, Any]],
    *,
    max_positive_controls: int,
) -> list[Mapping[str, Any]]:
    eligible = [item for item in items if _eligible(item)]
    selected: list[Mapping[str, Any]] = []

    def add_where(predicate, limit: int) -> None:
        nonlocal selected
        for item in eligible:
            if len(selected) >= max_positive_controls:
                return
            if len([existing for existing in selected if predicate(existing)]) >= limit:
                return
            if item in selected or not predicate(item):
                continue
            selected.append(item)

    add_where(lambda item: _lane(item) == "strong_positive_origin_candidate", 3)
    add_where(lambda item: _lane(item) == "strong_positive_candidate_needs_origin_url" and _ambiguous_key(item), 2)
    add_where(lambda item: _lane(item).startswith("strong_positive"), 5)
    add_where(lambda item: _lane(item).startswith("weak_positive"), 3)

    for item in eligible:
        if len(selected) >= max_positive_controls:
            break
        if item not in selected:
            selected.append(item)
    return selected[:max_positive_controls]


def _eligible(item: Mapping[str, Any]) -> bool:
    lane = _lane(item)
    status = _text(item.get("status")).lower()
    risk = _text(item.get("risk_level")).lower()
    company_key = _text(item.get("company_key"))
    gaps = set(_string_list(item.get("candidate_gap_coverage")))
    if not company_key or lane == "not_positive_control_candidate":
        return False
    if status == "abort_documented" or risk == "blocked":
        return False
    if "benchmark_candidate_count" not in gaps or "positive_control_coverage" not in gaps:
        return False
    return True


def _lane(item: Mapping[str, Any]) -> str:
    return _text(item.get("positive_control_lane"))


def _ambiguous_key(item: Mapping[str, Any]) -> bool:
    key = _text(item.get("company_key")).replace("_", "").replace("-", "")
    name = _text(item.get("company_name"))
    return len(key) <= 5 or name[:1].isdigit() or any(token.isupper() and len(token) >= 2 for token in name.split())


def _review_projection(lane: str, candidate_url: str) -> tuple[str, str, list[str], list[str]]:
    if lane == "strong_positive_origin_candidate":
        return "ready_for_human_evidence_review", "strong_detail", [candidate_url] if candidate_url else [], []
    if lane == "strong_positive_candidate_needs_origin_url":
        return "ready_for_detail_followup_review", "strong_origin", [], []
    if lane == "weak_positive_origin_candidate":
        return "weak_external_hint_no_candidate_creation", "weak_market_signal", [], [candidate_url] if candidate_url else []
    if lane == "weak_positive_candidate_needs_origin_url":
        return "weak_external_hint_no_candidate_creation", "weak_market_signal", [], []
    return "human_review_required", "unknown_evidence_strength", [], []


def _positive_rejection_reason(company_key: str, company_name: str, lane: str, gaps: Sequence[str]) -> str:
    if not company_key or not company_name:
        return "company_key and company_name are required"
    if lane not in {
        "strong_positive_origin_candidate",
        "strong_positive_candidate_needs_origin_url",
        "weak_positive_origin_candidate",
        "weak_positive_candidate_needs_origin_url",
    }:
        return "positive_control_lane must be a positive-control lane"
    if "positive_control_coverage" not in gaps:
        return "candidate_gap_coverage must include positive_control_coverage"
    if "benchmark_candidate_count" not in gaps:
        return "candidate_gap_coverage must include benchmark_candidate_count"
    return ""


def _gap_counts(rows: Sequence[PositiveProofEvidenceRow]) -> dict[str, int]:
    counts = {gap: 0 for gap in (*POSITIVE_GAPS, PROVIDER_GAP)}
    for row in rows:
        for gap in row.candidate_gap_coverage:
            if gap in counts:
                counts[gap] += 1
    return counts


def _next_action(accepted: Sequence[PositiveProofEvidenceRow], missing_gaps: Sequence[str]) -> str:
    if not accepted:
        return "No positive proof evidence rows are accepted; rerun GENERIC-009A or inspect employer-origin candidates before GENERIC-005."
    if list(missing_gaps) == [PROVIDER_GAP]:
        return "Positive proof evidence can close general proof gaps; provider-backed origin coverage still needs PROVIDER-001A or explicit provider evidence."
    if missing_gaps:
        return f"Positive proof evidence is partial; remaining gaps: {', '.join(missing_gaps)}."
    return "Positive proof evidence covers all current positive proof gaps; rerun GENERIC-005 as review artifact only."


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


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        key = text.lower()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
    return result


def _text(value: Any, *, default: str = "") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default
