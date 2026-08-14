"""Pure deterministic Detail Semantics gap contract for LLM-BOOST-001.

Detail Semantics starts only after concrete detail truth has already been
established by the existing deterministic DETAIL-001 validators.  This module
does not extract source truth itself.  It classifies semantic-field completeness
separately from the existing profile/geography product-support contracts.

That separation is intentional: a DETAIL-001 page can already be supported for
profile/geography while role, seniority, skills, location or remote semantics
remain unextracted or ambiguous.  Provider/model output remains hypothesis-only.
This module performs no HTTP, provider, model, database, lifecycle, gate,
ranking, application or product mutation and never grants semantic/product
authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from typing import Mapping, Sequence

from src.search_intelligence.llm_booster_policy import (
    BoosterPlan,
    BoosterStage,
    BoosterSurface,
    TavilyState,
    build_booster_plan,
)

DETAIL_SEMANTICS_GAP_CONTRACT_VERSION = "LLM-BOOST-001.detail-semantics-gap.v2"
SEMANTIC_FIELD_NAMES = ("role", "seniority", "skills", "location", "remote")


@dataclass(frozen=True)
class SemanticEvidenceReference:
    """Bounded evidence pointer retained with a semantic field hypothesis."""

    field: str
    source_url: str
    evidence: str
    value: str | None = None
    span_start: int | None = None
    span_end: int | None = None

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DetailSemanticsGapDecision:
    contract_version: str
    classification: str
    deterministic_attempted: bool
    deterministic_resolved: bool
    detail_supported: bool
    profile_contract_satisfied: bool
    geography_contract_satisfied: bool
    missing_contracts: tuple[str, ...]
    requested_semantic_fields: tuple[str, ...]
    resolved_semantic_fields: tuple[str, ...]
    missing_semantic_fields: tuple[str, ...]
    semantic_booster_eligible: bool
    unchanged_evidence_skip: bool
    external_information_gap: bool
    semantic_field_names: tuple[str, ...]
    evidence_references: tuple[SemanticEvidenceReference, ...]
    next_action: str
    evidence_fingerprint: str
    booster_plan: BoosterPlan
    semantic_authority: bool = False
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["evidence_references"] = [
            item.to_json() for item in self.evidence_references
        ]
        payload["booster_plan"] = self.booster_plan.to_json()
        return payload


def _normalize_scalar(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _normalize_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_json(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_json(item) for item in value]
    if isinstance(value, set):
        return sorted((_normalize_json(item) for item in value), key=repr)
    return _normalize_scalar(value)


def _semantic_fields(fields: Mapping[str, object]) -> dict[str, object]:
    return {
        field: _normalize_json(fields[field])
        for field in SEMANTIC_FIELD_NAMES
        if field in fields and fields[field] is not None
    }


def _requested_fields(values: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        field = str(value or "").strip().lower()
        if not field or field in seen:
            continue
        if field not in SEMANTIC_FIELD_NAMES:
            raise ValueError(f"unsupported requested Detail Semantics field: {field}")
        seen.add(field)
        normalized.append(field)
    if not normalized:
        raise ValueError("at least one requested Detail Semantics field is required")
    return tuple(normalized)


def _reference(record: Mapping[str, object]) -> SemanticEvidenceReference:
    field = str(record.get("field") or "").strip().lower()
    if field not in SEMANTIC_FIELD_NAMES:
        raise ValueError(
            f"unsupported Detail Semantics evidence field: {field or '<empty>'}"
        )

    source_url = str(record.get("source_url") or "").strip()
    evidence = str(record.get("evidence") or "").strip()
    if not source_url or not evidence:
        raise ValueError("semantic evidence references require source_url and evidence")

    value = str(record.get("value") or "").strip() or None
    span_start = record.get("span_start")
    span_end = record.get("span_end")
    if span_start is not None and not isinstance(span_start, int):
        raise ValueError("span_start must be an int when supplied")
    if span_end is not None and not isinstance(span_end, int):
        raise ValueError("span_end must be an int when supplied")
    if span_start is not None and span_start < 0:
        raise ValueError("span_start must be non-negative")
    if span_end is not None and span_end < 0:
        raise ValueError("span_end must be non-negative")
    if span_start is not None and span_end is not None and span_end < span_start:
        raise ValueError("span_end must be greater than or equal to span_start")

    return SemanticEvidenceReference(
        field=field,
        source_url=source_url,
        evidence=evidence,
        value=value,
        span_start=span_start,
        span_end=span_end,
    )


def _references(
    records: Sequence[Mapping[str, object]],
) -> tuple[SemanticEvidenceReference, ...]:
    return tuple(
        sorted(
            (_reference(record) for record in records),
            key=lambda item: (
                item.field,
                item.source_url,
                item.span_start if item.span_start is not None else -1,
                item.span_end if item.span_end is not None else -1,
                item.value or "",
                item.evidence,
            ),
        )
    )


def detail_semantics_gap_fingerprint(
    *,
    candidate_id: int,
    company_key: str,
    detail_url: str,
    deterministic_attempted: bool,
    detail_supported: bool,
    profile_contract_satisfied: bool,
    geography_contract_satisfied: bool,
    requested_semantic_fields: Sequence[str],
    deterministic_semantic_fields: Mapping[str, object],
    evidence_references: Sequence[Mapping[str, object]],
) -> str:
    """Stable identity for one already-normalized deterministic semantic state."""

    references = _references(evidence_references)
    requested = _requested_fields(requested_semantic_fields)
    payload = {
        "contract_version": DETAIL_SEMANTICS_GAP_CONTRACT_VERSION,
        "candidate_id": int(candidate_id),
        "company_key": str(company_key or "").strip().lower(),
        "detail_url": str(detail_url or "").strip(),
        "deterministic_attempted": bool(deterministic_attempted),
        "detail_supported": bool(detail_supported),
        "profile_contract_satisfied": bool(profile_contract_satisfied),
        "geography_contract_satisfied": bool(geography_contract_satisfied),
        "requested_semantic_fields": requested,
        "semantic_fields": _semantic_fields(deterministic_semantic_fields),
        "evidence_references": [item.to_json() for item in references],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def _missing_contracts(
    *,
    profile_contract_satisfied: bool,
    geography_contract_satisfied: bool,
) -> tuple[str, ...]:
    missing: list[str] = []
    if not profile_contract_satisfied:
        missing.append("profile")
    if not geography_contract_satisfied:
        missing.append("geography")
    return tuple(missing)


def analyze_detail_semantics_gap(
    *,
    candidate_id: int,
    company_key: str,
    detail_url: str,
    deterministic_attempted: bool,
    detail_supported: bool,
    profile_contract_satisfied: bool,
    geography_contract_satisfied: bool,
    deterministic_semantic_fields: Mapping[str, object],
    requested_semantic_fields: Sequence[str] = SEMANTIC_FIELD_NAMES,
    evidence_references: Sequence[Mapping[str, object]] = (),
    tavily_state: TavilyState = TavilyState.UNKNOWN,
    previous_semantic_fingerprint: str | None = None,
) -> DetailSemanticsGapDecision:
    """Classify deterministic semantic completeness and booster eligibility.

    Profile/geography observations remain authoritative product-support facts,
    but they do not define whether the Detail Semantics surface is complete.
    Semantic completeness is defined only by the bounded requested field set.
    This prevents an already-supported DETAIL-001 page from being incorrectly
    treated as semantically complete merely because product relevance is known.

    Ordinary semantic incompleteness is not an external-information acquisition
    gap, so Tavily stays ineligible while the bounded model cascade may become
    eligible. Unsupported detail truth, an unexecuted deterministic stage and
    unchanged semantic evidence remain fail-closed with zero external stages.
    """

    references = _references(evidence_references)
    semantic_fields = _semantic_fields(deterministic_semantic_fields)
    requested = _requested_fields(requested_semantic_fields)
    resolved_fields = tuple(field for field in requested if field in semantic_fields)
    missing_fields = tuple(field for field in requested if field not in semantic_fields)
    fingerprint = detail_semantics_gap_fingerprint(
        candidate_id=candidate_id,
        company_key=company_key,
        detail_url=detail_url,
        deterministic_attempted=deterministic_attempted,
        detail_supported=detail_supported,
        profile_contract_satisfied=profile_contract_satisfied,
        geography_contract_satisfied=geography_contract_satisfied,
        requested_semantic_fields=requested,
        deterministic_semantic_fields=semantic_fields,
        evidence_references=[item.to_json() for item in references],
    )
    missing_contracts = _missing_contracts(
        profile_contract_satisfied=profile_contract_satisfied,
        geography_contract_satisfied=geography_contract_satisfied,
    )
    resolved = bool(
        deterministic_attempted and detail_supported and not missing_fields
    )
    plan = build_booster_plan(
        surface=BoosterSurface.DETAIL_SEMANTICS,
        tavily_state=tavily_state,
        deterministic_resolved=resolved,
        external_information_gap=False,
    )

    if not deterministic_attempted:
        plan = _gate_external_stages(plan, reason_code="detail_semantics_d0_required")
        classification = "detail_semantics_d0_required"
        eligible = False
        unchanged = False
        next_action = "run_deterministic_detail_semantics"
    elif not detail_supported:
        plan = _gate_external_stages(
            plan,
            reason_code="supported_detail_truth_required",
        )
        classification = "detail_semantics_requires_supported_detail"
        eligible = False
        unchanged = False
        next_action = "preserve_detail_truth_and_stop_semantic_booster"
    elif resolved:
        classification = "detail_semantics_resolved"
        eligible = False
        unchanged = False
        next_action = "continue_with_existing_deterministic_product_contracts"
    elif previous_semantic_fingerprint and previous_semantic_fingerprint == fingerprint:
        plan = _gate_external_stages(
            plan,
            reason_code="unchanged_detail_semantic_evidence",
        )
        classification = "detail_semantics_gap_unchanged"
        eligible = False
        unchanged = True
        next_action = "await_changed_detail_semantic_evidence"
    else:
        classification = "detail_semantics_ambiguity_gap"
        eligible = True
        unchanged = False
        next_action = "run_bounded_model_semantic_hypothesis_cascade"

    return DetailSemanticsGapDecision(
        contract_version=DETAIL_SEMANTICS_GAP_CONTRACT_VERSION,
        classification=classification,
        deterministic_attempted=deterministic_attempted,
        deterministic_resolved=resolved,
        detail_supported=detail_supported,
        profile_contract_satisfied=profile_contract_satisfied,
        geography_contract_satisfied=geography_contract_satisfied,
        missing_contracts=missing_contracts,
        requested_semantic_fields=requested,
        resolved_semantic_fields=resolved_fields,
        missing_semantic_fields=missing_fields,
        semantic_booster_eligible=eligible,
        unchanged_evidence_skip=unchanged,
        external_information_gap=False,
        semantic_field_names=tuple(semantic_fields),
        evidence_references=references,
        next_action=next_action,
        evidence_fingerprint=fingerprint,
        booster_plan=plan,
    )
