"""Pure contracts for the default origin-URL repair cascade.

The URL finder is a critical product dependency. A deterministic ``not_found``
result is therefore not terminal until the bounded provider and evidence-review
stages have either completed or reported an explicit configuration/budget blocker.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

SELECTED_DECISIONS = {
    "origin_url_candidate_selected",
    "selected",
    "select_candidate",
}
MANUAL_REVIEW_DECISIONS = {
    "manual_review_required",
    "manual_review_candidate",
}


@dataclass(frozen=True)
class RepairStage:
    name: str
    attempted: bool
    status: str
    decision: str | None
    selected_url: str | None
    recommended_url: str | None
    confidence_score: float
    candidate_count: int
    provider_request_count: int
    reason: str
    blocker: str | None = None

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class OriginUrlRepairOutcome:
    company_key: str
    company_name: str
    final_state: str
    selected_url: str | None
    recommended_url: str | None
    selected_stage: str | None
    operator_review_required: bool
    repair_exhausted: bool
    configuration_blocked: bool
    stages: tuple[RepairStage, ...]
    boundary: Mapping[str, object]

    def to_json(self) -> dict[str, object]:
        return {
            "company_key": self.company_key,
            "company_name": self.company_name,
            "final_state": self.final_state,
            "selected_url": self.selected_url,
            "recommended_url": self.recommended_url,
            "selected_stage": self.selected_stage,
            "operator_review_required": self.operator_review_required,
            "repair_exhausted": self.repair_exhausted,
            "configuration_blocked": self.configuration_blocked,
            "stages": [item.to_json() for item in self.stages],
            "boundary": dict(self.boundary),
        }


def _text(value: object) -> str:
    return str(value or "").strip()


def _float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _count_candidates(payload: Mapping[str, object]) -> int:
    explicit = payload.get("candidate_count")
    try:
        if explicit is not None:
            return int(explicit)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        pass
    seen: set[str] = set()
    for key in ("alternatives", "rejected", "search_results"):
        values = payload.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, Mapping):
                url = _text(item.get("final_url") or item.get("url") or item.get("link"))
                if url:
                    seen.add(url)
    return len(seen)


def selected_url(payload: Mapping[str, object]) -> str | None:
    decision = _text(payload.get("decision"))
    url = _text(payload.get("selected_url"))
    if url and decision in SELECTED_DECISIONS:
        return url
    return None


def stage_from_discovery(
    name: str,
    payload: Mapping[str, object],
    *,
    provider_request_count: int = 0,
) -> RepairStage:
    chosen = selected_url(payload)
    decision = _text(payload.get("decision")) or None
    confidence = _float(payload.get("confidence_score"))
    if chosen:
        status = "selected"
    elif decision in MANUAL_REVIEW_DECISIONS:
        status = "manual_review"
    else:
        status = "not_found"
    return RepairStage(
        name=name,
        attempted=True,
        status=status,
        decision=decision,
        selected_url=chosen,
        recommended_url=None,
        confidence_score=confidence,
        candidate_count=_count_candidates(payload),
        provider_request_count=max(0, int(provider_request_count)),
        reason=_text(payload.get("reason")),
    )


def skipped_stage(name: str, reason: str) -> RepairStage:
    return RepairStage(
        name=name,
        attempted=False,
        status="skipped",
        decision=None,
        selected_url=None,
        recommended_url=None,
        confidence_score=0.0,
        candidate_count=0,
        provider_request_count=0,
        reason=reason,
    )


def blocked_stage(name: str, blocker: str, reason: str) -> RepairStage:
    return RepairStage(
        name=name,
        attempted=False,
        status="configuration_blocked",
        decision=None,
        selected_url=None,
        recommended_url=None,
        confidence_score=0.0,
        candidate_count=0,
        provider_request_count=0,
        reason=reason,
        blocker=blocker,
    )


def evidence_stage(
    payload: Mapping[str, object],
    *,
    llm_attempted: bool,
    llm_status: str | None,
    llm_recommended_url: str | None,
    llm_provider_request_count: int,
    blocker: str | None = None,
) -> RepairStage:
    deterministic_url = _text(payload.get("selected_url")) or None
    deterministic_decision = _text(payload.get("deterministic_decision")) or None
    confidence = _float(payload.get("confidence_score"))
    manual_required = bool(payload.get("manual_review_required"))
    if deterministic_url and deterministic_decision == "origin_url_candidate_selected":
        status = "selected"
        reason = "Deep evidence grading selected an origin URL deterministically."
    elif llm_recommended_url:
        status = "manual_review"
        reason = (
            "Bounded LLM adjudication recommended an already observed candidate; "
            "operator review remains required."
        )
    elif blocker:
        status = "configuration_blocked"
        reason = _text(payload.get("reason")) or "Evidence review could not complete."
    elif manual_required or llm_status == "completed":
        status = "manual_review"
        reason = _text(payload.get("reason")) or "Evidence remains ambiguous."
    else:
        status = "not_found"
        reason = _text(payload.get("reason")) or "No validated origin survived deep evidence grading."
    return RepairStage(
        name="evidence_and_llm_repair",
        attempted=True,
        status=status,
        decision=deterministic_decision,
        selected_url=deterministic_url,
        recommended_url=llm_recommended_url,
        confidence_score=confidence,
        candidate_count=len(payload.get("assessments", []))
        if isinstance(payload.get("assessments"), list)
        else 0,
        provider_request_count=max(0, int(llm_provider_request_count)),
        reason=reason,
        blocker=blocker,
    )


def finalize_outcome(
    *,
    company_key: str,
    company_name: str,
    stages: Sequence[RepairStage],
) -> OriginUrlRepairOutcome:
    ordered = tuple(stages)
    for stage in ordered:
        if stage.selected_url:
            return OriginUrlRepairOutcome(
                company_key=company_key,
                company_name=company_name,
                final_state=f"selected_{stage.name}",
                selected_url=stage.selected_url,
                recommended_url=None,
                selected_stage=stage.name,
                operator_review_required=False,
                repair_exhausted=False,
                configuration_blocked=False,
                stages=ordered,
                boundary=default_boundary(),
            )

    recommendations = [
        stage.recommended_url for stage in ordered if stage.recommended_url
    ]
    if recommendations:
        return OriginUrlRepairOutcome(
            company_key=company_key,
            company_name=company_name,
            final_state="operator_review_required",
            selected_url=None,
            recommended_url=recommendations[-1],
            selected_stage=None,
            operator_review_required=True,
            repair_exhausted=False,
            configuration_blocked=False,
            stages=ordered,
            boundary=default_boundary(),
        )

    blockers = [stage for stage in ordered if stage.status == "configuration_blocked"]
    if blockers:
        return OriginUrlRepairOutcome(
            company_key=company_key,
            company_name=company_name,
            final_state="repair_configuration_blocked",
            selected_url=None,
            recommended_url=None,
            selected_stage=None,
            operator_review_required=True,
            repair_exhausted=False,
            configuration_blocked=True,
            stages=ordered,
            boundary=default_boundary(),
        )

    manual = [stage for stage in ordered if stage.status == "manual_review"]
    if manual:
        return OriginUrlRepairOutcome(
            company_key=company_key,
            company_name=company_name,
            final_state="operator_review_required",
            selected_url=None,
            recommended_url=None,
            selected_stage=None,
            operator_review_required=True,
            repair_exhausted=False,
            configuration_blocked=False,
            stages=ordered,
            boundary=default_boundary(),
        )

    attempted_names = {stage.name for stage in ordered if stage.attempted}
    full_attempted = {
        "deterministic_baseline",
        "tavily_repair",
        "evidence_and_llm_repair",
    }.issubset(attempted_names)
    return OriginUrlRepairOutcome(
        company_key=company_key,
        company_name=company_name,
        final_state="repair_exhausted" if full_attempted else "repair_incomplete",
        selected_url=None,
        recommended_url=None,
        selected_stage=None,
        operator_review_required=True,
        repair_exhausted=full_attempted,
        configuration_blocked=False,
        stages=ordered,
        boundary=default_boundary(),
    )


def compatibility_payload(
    outcome: OriginUrlRepairOutcome,
    *,
    last_discovery_payload: Mapping[str, object],
) -> dict[str, object]:
    """Return a URL-Finder-compatible payload with the repair trace attached."""

    payload = dict(last_discovery_payload)
    payload["default_repair"] = outcome.to_json()
    payload["repair_final_state"] = outcome.final_state
    payload["repair_exhausted"] = outcome.repair_exhausted
    payload["repair_configuration_blocked"] = outcome.configuration_blocked
    payload["operator_review_required"] = outcome.operator_review_required
    if outcome.selected_url:
        payload["decision"] = "origin_url_candidate_selected"
        payload["selected_url"] = outcome.selected_url
    elif outcome.recommended_url:
        payload["decision"] = "manual_review_required"
        payload["selected_url"] = None
        payload["recommended_url"] = outcome.recommended_url
    else:
        payload["selected_url"] = None
        if outcome.configuration_blocked:
            payload["decision"] = "repair_configuration_blocked"
        elif outcome.repair_exhausted:
            payload["decision"] = "repair_exhausted"
        else:
            payload["decision"] = "manual_review_required"
    return payload


def default_boundary() -> dict[str, object]:
    return {
        "default_product_path": True,
        "bounded_deterministic_baseline": True,
        "bounded_tavily_repair": True,
        "bounded_evidence_regrading": True,
        "bounded_llm_adjudication": True,
        "llm_may_only_reference_observed_candidate_ids": True,
        "llm_may_not_invent_or_persist_url": True,
        "candidate_url_write": False,
        "connector_registration": False,
        "source_activation": False,
        "bronze_silver_write": False,
        "scheduler_change": False,
        "fail_closed_after_full_repair": True,
    }
