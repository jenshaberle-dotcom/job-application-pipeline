"""Deterministic Detail Discovery gap classification for LLM-BOOST-001.

DETAIL-001 historically combines bounded local/detail probing and optional
external search.  LLM-BOOST-001 needs a cleaner authority boundary: first run
DETAIL-001 with external search disabled, then decide whether the deterministic
result is resolved, an operational failure, a candidate-validation ambiguity,
or a genuine external-information gap.

This module is pure.  It performs no HTTP, provider, model, database, lifecycle,
gate, ranking, or product mutation.  Provider/model stages remain hypothesis
only and concrete-detail truth stays with the existing deterministic validators.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from typing import Any, Mapping, Sequence

from src.search_intelligence.llm_booster_policy import (
    BoosterPlan,
    BoosterStage,
    BoosterSurface,
    TavilyState,
    build_booster_plan,
)

DETAIL_DISCOVERY_GAP_CONTRACT_VERSION = "LLM-BOOST-001.detail-discovery-gap.v1"


@dataclass(frozen=True)
class DetailDiscoveryGapDecision:
    contract_version: str
    classification: str
    deterministic_attempted: bool
    deterministic_resolved: bool
    external_information_gap: bool
    semantic_booster_eligible: bool
    unchanged_gap_skip: bool
    operational_gap: bool
    preliminary_candidate_count: int
    supported_detail_count: int
    next_action: str
    evidence_fingerprint: str
    booster_plan: BoosterPlan
    detail_authority: bool = False
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["booster_plan"] = self.booster_plan.to_json()
        return payload


def _list(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _normalized_url(value: object) -> str:
    return str(value or "").strip()


def _candidate_urls(evidence: Mapping[str, object]) -> tuple[str, ...]:
    candidates = (
        _list(evidence.get("preliminary_detail_candidates"))
        or _list(evidence.get("candidate_links"))
    )
    urls: set[str] = set()
    for item in candidates:
        record = _mapping(item)
        url = _normalized_url(record.get("url") or record.get("final_url"))
        if url:
            urls.add(url)
    return tuple(sorted(urls))


def _supported_urls(evidence: Mapping[str, object]) -> tuple[str, ...]:
    collections: Sequence[object] = (
        evidence.get("supported_detail_evidence"),
        evidence.get("supported_details"),
        evidence.get("details"),
    )
    urls: set[str] = set()
    for collection in collections:
        for item in _list(collection):
            record = _mapping(item)
            url = _normalized_url(record.get("final_url") or record.get("url"))
            if url:
                urls.add(url)
        if urls:
            break
    return tuple(sorted(urls))


def _assessment_identity(evidence: Mapping[str, object]) -> tuple[tuple[str, str, str], ...]:
    assessments = (
        _list(evidence.get("authoritative_detail_assessments"))
        or _list(evidence.get("detail_assessments"))
    )
    result: set[tuple[str, str, str]] = set()
    for item in assessments:
        record = _mapping(item)
        url = _normalized_url(record.get("url") or record.get("final_url"))
        decision = str(record.get("decision") or "").strip()
        failure = str(record.get("failure_reason") or "").strip()
        if url or decision or failure:
            result.add((url, decision, failure))
    return tuple(sorted(result))


def _checked_origin_identity(evidence: Mapping[str, object]) -> tuple[tuple[object, ...], ...]:
    origins = _list(evidence.get("checked_origin_candidates"))
    result: set[tuple[object, ...]] = set()
    for item in origins:
        record = _mapping(item)
        reasons = tuple(sorted(str(value) for value in _list(record.get("rejection_reasons"))))
        result.add(
            (
                _normalized_url(record.get("url")),
                _normalized_url(record.get("final_url")),
                str(record.get("status") or "").strip(),
                record.get("status_code"),
                reasons,
            )
        )
    return tuple(sorted(result, key=repr))


def detail_discovery_gap_fingerprint(
    *,
    candidate_id: int,
    company_key: str,
    candidate_url: str,
    deterministic_evidence: Mapping[str, object],
) -> str:
    """Stable semantic identity for one deterministic Detail Discovery result."""

    payload = {
        "contract_version": DETAIL_DISCOVERY_GAP_CONTRACT_VERSION,
        "candidate_id": int(candidate_id),
        "company_key": str(company_key or "").strip().lower(),
        "candidate_url": str(candidate_url or "").strip(),
        "repair_attempted": bool(deterministic_evidence.get("repair_attempted")),
        "search_discovery_enabled": bool(
            deterministic_evidence.get("search_discovery_enabled")
        ),
        "detail_link_discovery_version": str(
            deterministic_evidence.get("detail_link_discovery_version") or ""
        ),
        "detail_url_shape_version": str(
            deterministic_evidence.get("detail_url_shape_version") or ""
        ),
        "decision_taxonomy": str(
            deterministic_evidence.get("decision_taxonomy") or ""
        ),
        "candidate_urls": _candidate_urls(deterministic_evidence),
        "supported_urls": _supported_urls(deterministic_evidence),
        "assessments": _assessment_identity(deterministic_evidence),
        "checked_origins": _checked_origin_identity(deterministic_evidence),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _shared_plan(
    *,
    tavily_state: TavilyState,
    deterministic_resolved: bool,
    external_information_gap: bool,
) -> BoosterPlan:
    return build_booster_plan(
        surface=BoosterSurface.DETAIL_DISCOVERY,
        tavily_state=tavily_state,
        deterministic_resolved=deterministic_resolved,
        external_information_gap=external_information_gap,
    )


def _gate_external_stages(plan: BoosterPlan, *, reason_code: str) -> BoosterPlan:
    return replace(
        plan,
        stages=tuple(
            stage
            if stage.stage == BoosterStage.DETERMINISTIC
            else replace(stage, eligible=False, reason_code=reason_code)
            for stage in plan.stages
        ),
    )


def _all_origin_fetches_failed(evidence: Mapping[str, object]) -> bool:
    checked = _list(evidence.get("checked_origin_candidates"))
    if not checked:
        return False
    statuses = [str(_mapping(item).get("status") or "").strip() for item in checked]
    return bool(statuses) and all(status == "fetch_error" for status in statuses)


def _decision(
    *,
    classification: str,
    deterministic_attempted: bool,
    deterministic_resolved: bool,
    external_information_gap: bool,
    semantic_booster_eligible: bool,
    unchanged_gap_skip: bool,
    operational_gap: bool,
    preliminary_candidate_count: int,
    supported_detail_count: int,
    next_action: str,
    evidence_fingerprint: str,
    booster_plan: BoosterPlan,
) -> DetailDiscoveryGapDecision:
    return DetailDiscoveryGapDecision(
        contract_version=DETAIL_DISCOVERY_GAP_CONTRACT_VERSION,
        classification=classification,
        deterministic_attempted=deterministic_attempted,
        deterministic_resolved=deterministic_resolved,
        external_information_gap=external_information_gap,
        semantic_booster_eligible=semantic_booster_eligible,
        unchanged_gap_skip=unchanged_gap_skip,
        operational_gap=operational_gap,
        preliminary_candidate_count=preliminary_candidate_count,
        supported_detail_count=supported_detail_count,
        next_action=next_action,
        evidence_fingerprint=evidence_fingerprint,
        booster_plan=booster_plan,
    )


def analyze_detail_discovery_gap(
    *,
    candidate_id: int,
    company_key: str,
    candidate_url: str,
    deterministic_evidence: Mapping[str, object],
    tavily_state: TavilyState,
    previous_gap_fingerprint: str | None = None,
) -> DetailDiscoveryGapDecision:
    """Classify the post-D0 Detail Discovery state and booster eligibility.

    ``deterministic_evidence`` must come from a DETAIL-001 repair run with
    external search disabled.  A mixed run cannot establish D0 exhaustion,
    because provider search would already have occurred before the shared
    LLM-BOOST-001 budget/ordering policy could account for it.
    """

    fingerprint = detail_discovery_gap_fingerprint(
        candidate_id=candidate_id,
        company_key=company_key,
        candidate_url=candidate_url,
        deterministic_evidence=deterministic_evidence,
    )
    preliminary_count = len(_candidate_urls(deterministic_evidence))
    supported_count = len(_supported_urls(deterministic_evidence))
    attempted = bool(deterministic_evidence.get("repair_attempted"))

    if bool(deterministic_evidence.get("search_discovery_enabled")):
        plan = _gate_external_stages(
            _shared_plan(
                tavily_state=tavily_state,
                deterministic_resolved=False,
                external_information_gap=False,
            ),
            reason_code="detail_d0_external_search_not_isolated",
        )
        return _decision(
            classification="detail_d0_external_search_not_isolated",
            deterministic_attempted=attempted,
            deterministic_resolved=False,
            external_information_gap=False,
            semantic_booster_eligible=False,
            unchanged_gap_skip=False,
            operational_gap=False,
            preliminary_candidate_count=preliminary_count,
            supported_detail_count=supported_count,
            next_action="rerun_detail_d0_without_external_search",
            evidence_fingerprint=fingerprint,
            booster_plan=plan,
        )

    if not attempted:
        plan = _gate_external_stages(
            _shared_plan(
                tavily_state=tavily_state,
                deterministic_resolved=False,
                external_information_gap=False,
            ),
            reason_code="detail_d0_not_executed",
        )
        return _decision(
            classification="detail_d0_required",
            deterministic_attempted=False,
            deterministic_resolved=False,
            external_information_gap=False,
            semantic_booster_eligible=False,
            unchanged_gap_skip=False,
            operational_gap=False,
            preliminary_candidate_count=preliminary_count,
            supported_detail_count=supported_count,
            next_action="run_detail_d0_without_external_search",
            evidence_fingerprint=fingerprint,
            booster_plan=plan,
        )

    if supported_count > 0 or str(
        deterministic_evidence.get("decision_taxonomy") or ""
    ) == "accepted":
        return _decision(
            classification="detail_discovery_resolved",
            deterministic_attempted=True,
            deterministic_resolved=True,
            external_information_gap=False,
            semantic_booster_eligible=False,
            unchanged_gap_skip=False,
            operational_gap=False,
            preliminary_candidate_count=preliminary_count,
            supported_detail_count=supported_count,
            next_action="use_deterministically_validated_detail_evidence",
            evidence_fingerprint=fingerprint,
            booster_plan=_shared_plan(
                tavily_state=tavily_state,
                deterministic_resolved=True,
                external_information_gap=False,
            ),
        )

    if _all_origin_fetches_failed(deterministic_evidence):
        plan = _gate_external_stages(
            _shared_plan(
                tavily_state=tavily_state,
                deterministic_resolved=False,
                external_information_gap=False,
            ),
            reason_code="detail_d0_operational_fetch_gap",
        )
        return _decision(
            classification="detail_d0_operational_fetch_gap",
            deterministic_attempted=True,
            deterministic_resolved=False,
            external_information_gap=False,
            semantic_booster_eligible=False,
            unchanged_gap_skip=False,
            operational_gap=True,
            preliminary_candidate_count=preliminary_count,
            supported_detail_count=supported_count,
            next_action="retry_d0_after_runtime_condition_changes",
            evidence_fingerprint=fingerprint,
            booster_plan=plan,
        )

    external_gap = preliminary_count == 0
    base_classification = (
        "detail_external_information_gap"
        if external_gap
        else "detail_candidate_validation_gap"
    )
    unchanged = bool(
        previous_gap_fingerprint and previous_gap_fingerprint == fingerprint
    )
    plan = _shared_plan(
        tavily_state=tavily_state,
        deterministic_resolved=False,
        external_information_gap=external_gap,
    )
    if unchanged:
        plan = _gate_external_stages(
            plan,
            reason_code="unchanged_detail_discovery_gap_fingerprint",
        )

    return _decision(
        classification=(
            f"{base_classification}_unchanged" if unchanged else base_classification
        ),
        deterministic_attempted=True,
        deterministic_resolved=False,
        external_information_gap=external_gap,
        semantic_booster_eligible=not unchanged,
        unchanged_gap_skip=unchanged,
        operational_gap=False,
        preliminary_candidate_count=preliminary_count,
        supported_detail_count=supported_count,
        next_action=(
            "await_changed_detail_evidence"
            if unchanged
            else "search_for_detail_candidates"
            if external_gap
            else "interpret_or_propose_detail_candidates"
        ),
        evidence_fingerprint=fingerprint,
        booster_plan=plan,
    )


__all__ = [
    "DETAIL_DISCOVERY_GAP_CONTRACT_VERSION",
    "DetailDiscoveryGapDecision",
    "analyze_detail_discovery_gap",
    "detail_discovery_gap_fingerprint",
]
