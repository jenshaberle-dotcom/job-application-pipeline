"""Freeze-II artifact-backed promotion planning for resolved sensor companies.

This module deliberately reuses the existing market-sensor promotion planner.
It adds one prerequisite that did not exist in the older S7J flow: a company may
enter this bounded cohort only when the pre-candidate F1 origin proof selected a
low-risk direct employer/career URL.

The selected URL is evidence only. Candidate creation still leaves candidate_url
NULL so the existing Origin Source Discovery / validated persistence authority is
not bypassed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Iterable, Mapping

from src.search_intelligence.market_sensor_candidate_promotion_batch import (
    MarketSensorPromotionInput,
    PromotionBatchPlan,
    build_promotion_batch_plan,
)


SCHEMA = "job_application_pipeline.freeze2_resolved_candidate_promotion.v1"


@dataclass(frozen=True)
class ResolvedOriginEvidence:
    company_key: str
    company_name: str
    selected_url: str
    selected_domain: str
    origin_decision: str
    risk_level: str
    confidence_score: float
    sensor_decision: str
    sensor_evidence_count: int
    sensor_source_name: str


def _review_items(review_payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    review = review_payload.get("review")
    if not isinstance(review, Mapping):
        return {}
    raw_items = review.get("items")
    if not isinstance(raw_items, list):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for item in raw_items:
        if not isinstance(item, Mapping):
            continue
        key = str(item.get("company_key") or "").strip().lower()
        if key:
            result[key] = item
    return result


def select_resolved_origin_evidence(
    origin_payload: Mapping[str, Any],
) -> tuple[ResolvedOriginEvidence, ...]:
    raw_results = origin_payload.get("results")
    if not isinstance(raw_results, list):
        return ()

    selected: list[ResolvedOriginEvidence] = []
    seen: set[str] = set()
    for raw in raw_results:
        if not isinstance(raw, Mapping):
            continue
        company_key = str(raw.get("company_key") or "").strip().lower()
        selected_url = str(raw.get("selected_url") or "").strip()
        selected_domain = str(raw.get("selected_domain") or "").strip().lower()
        if (
            not company_key
            or company_key in seen
            or str(raw.get("resolution_state") or "") != "direct_source_resolved"
            or str(raw.get("origin_decision") or "") != "origin_url_candidate_selected"
            or str(raw.get("risk_level") or "") != "low"
            or not selected_url.startswith("https://")
            or not selected_domain
        ):
            continue
        seen.add(company_key)
        selected.append(
            ResolvedOriginEvidence(
                company_key=company_key,
                company_name=str(raw.get("company_name") or "").strip(),
                selected_url=selected_url,
                selected_domain=selected_domain,
                origin_decision=str(raw.get("origin_decision") or ""),
                risk_level=str(raw.get("risk_level") or ""),
                confidence_score=float(raw.get("confidence_score") or 0.0),
                sensor_decision=str(raw.get("sensor_decision") or ""),
                sensor_evidence_count=int(raw.get("sensor_evidence_count") or 0),
                sensor_source_name=str(raw.get("sensor_source_name") or ""),
            )
        )
    return tuple(selected)


def _promotion_inputs(
    review_payload: Mapping[str, Any],
    origins: Iterable[ResolvedOriginEvidence],
) -> tuple[MarketSensorPromotionInput, ...]:
    by_key = _review_items(review_payload)
    inputs: list[MarketSensorPromotionInput] = []
    for index, origin in enumerate(origins, start=1):
        raw = by_key.get(origin.company_key)
        if raw is None:
            continue
        decision = str(raw.get("decision") or "")
        if decision not in {"manual_review_required", "create_candidate_recommended"}:
            continue
        inputs.append(
            MarketSensorPromotionInput(
                item_id=index,
                review_id=0,
                company_key=origin.company_key,
                company_name=str(raw.get("company_name") or origin.company_name),
                source_name=str(raw.get("source_name") or origin.sensor_source_name),
                decision=decision,
                priority=int(raw.get("priority") or 0),
                evidence_count=int(raw.get("evidence_count") or 0),
                known_candidate_id=(
                    int(raw["known_candidate_id"])
                    if raw.get("known_candidate_id") is not None
                    else None
                ),
                known_candidate_status=str(raw.get("known_candidate_status") or ""),
                recommended_next_action=str(
                    raw.get("recommended_next_action") or ""
                ),
                reason=str(raw.get("reason") or ""),
            )
        )
    return tuple(inputs)


def build_resolved_promotion_plan(
    *,
    review_payload: Mapping[str, Any],
    origin_payload: Mapping[str, Any],
    existing_company_keys: set[str] | None = None,
) -> tuple[PromotionBatchPlan, tuple[ResolvedOriginEvidence, ...]]:
    origins = select_resolved_origin_evidence(origin_payload)
    inputs = _promotion_inputs(review_payload, origins)
    requested = tuple(item.company_key for item in inputs)
    plan = build_promotion_batch_plan(
        inputs,
        requested_company_keys=requested,
        include_manual_review_required=True,
        existing_company_keys=existing_company_keys or set(),
    )
    return plan, origins


def cohort_digest(
    plan: PromotionBatchPlan,
    origins: Iterable[ResolvedOriginEvidence],
) -> str:
    origin_by_key = {item.company_key: item for item in origins}
    rows: list[dict[str, object]] = []
    for item in plan.items:
        origin = origin_by_key.get(item.company_key)
        rows.append(
            {
                "company_key": item.company_key,
                "company_name": item.company_name,
                "source_decision": item.source_decision,
                "action": item.action,
                "create_allowed": item.create_allowed,
                "selected_url": origin.selected_url if origin else None,
                "selected_domain": origin.selected_domain if origin else None,
                "origin_risk_level": origin.risk_level if origin else None,
                "origin_confidence_score": (
                    origin.confidence_score if origin else None
                ),
            }
        )
    canonical = json.dumps(
        rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def report_payload(
    *,
    review_payload: Mapping[str, Any],
    origin_payload: Mapping[str, Any],
    existing_company_keys: set[str] | None = None,
) -> dict[str, object]:
    plan, origins = build_resolved_promotion_plan(
        review_payload=review_payload,
        origin_payload=origin_payload,
        existing_company_keys=existing_company_keys,
    )
    origin_by_key = {item.company_key: item for item in origins}
    items: list[dict[str, object]] = []
    for item in plan.items:
        origin = origin_by_key.get(item.company_key)
        row = asdict(item)
        row["resolved_origin"] = asdict(origin) if origin else None
        items.append(row)

    return {
        "schema": SCHEMA,
        "cohort_digest": cohort_digest(plan, origins),
        "summary": {
            "resolved_origin_count": len(origins),
            "requested_company_count": len(plan.requested_company_keys),
            "planned_create_count": plan.create_count,
            "blocked_or_skipped_count": plan.blocked_count,
            "manual_review_opt_in": plan.include_manual_review_required,
        },
        "requested_company_keys": list(plan.requested_company_keys),
        "items": items,
        "boundary": {
            "artifact_backed": True,
            "origin_resolution_required": True,
            "resolved_low_risk_https_only": True,
            "candidate_url_write": False,
            "connector_registration": False,
            "source_activation": False,
            "bronze_silver_product_writes": False,
            "scheduler_change": False,
        },
    }
