"""DB-backed Agent Monitor v1 read model.

The module converts existing lifecycle, gate-review, gate-event and orchestrator
signals into presentation-ready health cards. It is deliberately read-only and
never executes agents or mutates candidate, source, connector, scheduler or
pipeline state.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence


class GateSignalCollection(list[object]):
    """Gate reviews plus their append-only event/audit context."""

    def __init__(
        self,
        reviews: Iterable[object] = (),
        *,
        events: Iterable[Mapping[str, object]] = (),
        relations: Mapping[str, bool] | None = None,
    ) -> None:
        super().__init__(reviews)
        self.events = tuple(dict(event) for event in events)
        self.relations = dict(relations or {})

    def __bool__(self) -> bool:
        return bool(len(self) or self.events or any(self.relations.values()))


class OrchestratorSignalCollection(list[object]):
    """Latest-run attention list plus the complete latest-run step context."""

    def __init__(
        self,
        attention_steps: Iterable[object] = (),
        *,
        latest_run: Mapping[str, object] | None = None,
        all_steps: Iterable[object] = (),
        relations: Mapping[str, bool] | None = None,
    ) -> None:
        super().__init__(attention_steps)
        self.latest_run = dict(latest_run) if latest_run else None
        self.all_steps = tuple(all_steps)
        self.relations = dict(relations or {})

    def __bool__(self) -> bool:
        return bool(
            len(self)
            or self.latest_run
            or self.all_steps
            or any(self.relations.values())
        )


def _value(item: object, name: str, default: object = None) -> object:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _as_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _record_time(item: object) -> datetime | None:
    for field in ("updated_at", "reviewed_at", "created_at", "completed_at"):
        parsed = _timestamp(_value(item, field))
        if parsed is not None:
            return parsed
    return None


def _format_time(value: object) -> str:
    parsed = _timestamp(value)
    if parsed is not None:
        return parsed.isoformat().replace("+00:00", "Z")
    raw = str(value or "").strip()
    return raw or "No persisted timestamp"


def _latest(items: Iterable[object]) -> object | None:
    values = list(items)
    if not values:
        return None
    dated = [(item, _record_time(item)) for item in values]
    if any(timestamp is not None for _, timestamp in dated):
        return max(
            dated,
            key=lambda pair: pair[1] or datetime.min,
        )[0]
    return values[0]


def _latest_reviews(gate_reviews: Iterable[object]) -> dict[tuple[str, str], object]:
    grouped: dict[tuple[str, str], list[object]] = {}
    for review in gate_reviews:
        key = (
            str(_value(review, "candidate_id", "")),
            str(_value(review, "gate_name", "")),
        )
        grouped.setdefault(key, []).append(review)
    return {
        key: latest
        for key, values in grouped.items()
        if (latest := _latest(values)) is not None
    }


def _candidate_name(item: object) -> str:
    return str(
        _value(item, "company_name", "")
        or _value(item, "display_company_name", "")
        or _value(item, "company_key", "")
    ).strip()


def _names(items: Iterable[object], *, empty: str) -> str:
    names = [_candidate_name(item) for item in items]
    unique = list(dict.fromkeys(name for name in names if name))
    return ", ".join(unique) if unique else empty


def _is_active(candidate: object) -> bool:
    return str(_value(candidate, "status", "")) == "active_controlled"


def _is_blocked(candidate: object) -> bool:
    return bool(_value(candidate, "latest_blocking_gate"))


def _event_gate_name(event: object) -> str:
    new_state = _as_mapping(_value(event, "new_state", {}))
    return str(
        _value(event, "gate_name", "")
        or new_state.get("gate_name")
        or new_state.get("name")
        or ""
    )


def _event_decision(event: object) -> str:
    new_state = _as_mapping(_value(event, "new_state", {}))
    return str(
        _value(event, "decision", "")
        or new_state.get("decision")
        or new_state.get("status")
        or _value(event, "event_type", "")
        or "unknown"
    )


def _events_for_gate(events: Iterable[object], gate_name: str) -> list[object]:
    return [event for event in events if _event_gate_name(event) == gate_name]


def _relation_state(collection: object, relation: str) -> bool | None:
    relations = getattr(collection, "relations", None)
    if not isinstance(relations, Mapping) or relation not in relations:
        return None
    return bool(relations[relation])


def _card(
    *,
    name: str,
    group: str,
    status: str,
    output_quality: str,
    latest_decision: str,
    summary: str,
    evidence: str,
    next_action: str,
    boundary: str,
    tone: str,
    affected_candidates: str,
    signal_scope: str,
    truth_sources: str,
    last_signal_at: str,
) -> dict[str, str]:
    return {
        "name": name,
        "group": group,
        "status": status,
        "output_quality": output_quality,
        "latest_decision": latest_decision,
        "summary": summary,
        "evidence": evidence,
        "next_action": next_action,
        "boundary": boundary,
        "tone": tone,
        "affected_candidates": affected_candidates,
        "signal_scope": signal_scope,
        "truth_sources": truth_sources,
        "last_signal_at": last_signal_at,
    }


def _gate_card_state(
    *,
    current_candidates: Sequence[object],
    latest_gate_reviews: Sequence[object],
    relation_available: bool | None,
    unavailable_quality: str,
    missing_status: str,
    missing_quality: str,
) -> tuple[str, str, str]:
    if current_candidates or latest_gate_reviews:
        return "Passed persisted signal", "ok", "Persisted gate outcome available"
    if relation_available is False:
        return "Signal unavailable", "neutral", unavailable_quality
    return missing_status, "neutral", missing_quality


def build_agent_monitor_cards(
    candidates: list[object],
    orchestrator_steps: list[object],
    gate_reviews: list[object],
) -> list[dict[str, str]]:
    """Build Agent Monitor cards from current and historical DB truth.

    Current lifecycle state is authoritative for active blockers. Gate reviews
    describe the latest persisted gate state, while gate events provide an audit
    trail only; an old passed event never overrides a newer blocking review.
    """

    gate_events = list(getattr(gate_reviews, "events", ()))
    latest_review_map = _latest_reviews(gate_reviews)
    latest_reviews = list(latest_review_map.values())

    blocked_candidates = [candidate for candidate in candidates if _is_blocked(candidate)]
    active_candidates = [candidate for candidate in candidates if _is_active(candidate)]
    detail_blocked = [
        candidate
        for candidate in blocked_candidates
        if str(_value(candidate, "latest_blocking_gate", ""))
        == "detail_evidence_gate"
    ]
    artifact_candidates = [
        candidate
        for candidate in candidates
        if str(_value(candidate, "build_status", ""))
        == "artifact_generation_allowed"
    ]
    validation_current = [
        candidate
        for candidate in candidates
        if str(_value(candidate, "connector_validation_status", "")) == "passed"
    ]
    approval_current = [
        candidate
        for candidate in candidates
        if str(_value(candidate, "final_approval_decision", ""))
        == "approve_connector_registration"
    ]
    validation_reviews = [
        review
        for review in latest_reviews
        if str(_value(review, "gate_name", "")) == "connector_validation_gate"
        and str(_value(review, "gate_status", "")) == "passed"
        and str(_value(review, "decision", "")) == "ready_for_final_approval"
    ]
    approval_reviews = [
        review
        for review in latest_reviews
        if str(_value(review, "gate_name", "")) == "final_approval_gate"
        and str(_value(review, "gate_status", "")) == "passed"
        and str(_value(review, "decision", ""))
        == "approve_connector_registration"
    ]

    latest_gate_event = _latest(gate_events)
    latest_detail_event = _latest(_events_for_gate(gate_events, "detail_evidence_gate"))
    latest_validation_event = _latest(
        _events_for_gate(gate_events, "connector_validation_gate")
    )
    latest_approval_event = _latest(
        _events_for_gate(gate_events, "final_approval_gate")
    )

    cards: list[dict[str, str]] = []
    cards.append(
        _card(
            name="Candidate Lifecycle Agent",
            group="Lifecycle & Gold Read Models",
            status="Healthy" if candidates else "No current lifecycle signal",
            output_quality=(
                "Usable current lifecycle state"
                if candidates
                else "No persisted lifecycle rows supplied"
            ),
            latest_decision=(
                f"{len(active_candidates)} active · {len(blocked_candidates)} blocked · "
                f"{len(candidates)} total candidates"
            ),
            summary=(
                "Builds the current candidate surface and keeps live blockers "
                "separate from historical gate success."
            ),
            evidence=(
                f"gold_candidate_lifecycle_status supplied {len(candidates)} row(s); "
                f"the gate audit trail supplied {len(gate_events)} event(s)."
            ),
            next_action="Prioritize current blockers; use history only as supporting evidence.",
            boundary=(
                "Read-only Gold/ViewModel interpretation. No connector registration, "
                "activation, scheduler mutation or Bronze write."
            ),
            tone="ok" if candidates else "neutral",
            affected_candidates=_names(candidates, empty="No candidate signal"),
            signal_scope="Current lifecycle + audit context",
            truth_sources="gold_candidate_lifecycle_status; employer_origin_candidate_gate_events",
            last_signal_at=_format_time(
                _value(latest_gate_event, "created_at") if latest_gate_event else None
            ),
        )
    )

    if detail_blocked:
        detail_status = "Needs review"
        detail_tone = "warn"
        detail_quality = "Current weak or incomplete evidence"
        detail_decision = str(
            _value(detail_blocked[0], "latest_blocking_decision", "")
            or "manual_review_required"
        )
        detail_summary = str(
            _value(
                detail_blocked[0],
                "latest_blocking_reason",
                "Detail evidence requires review.",
            )
        )
        detail_next = "Review detail evidence or run only the bounded repair workflow."
    else:
        detail_status = "Healthy"
        detail_tone = "ok"
        detail_quality = "No current detail-evidence blocker"
        detail_decision = "no_active_blocker"
        detail_summary = (
            "No active detail-evidence blocker is visible in the current lifecycle view."
        )
        detail_next = "Monitor future candidate evidence."

    cards.append(
        _card(
            name="Detail Evidence Repair Agent",
            group="Evidence & Gate Agents",
            status=detail_status,
            output_quality=detail_quality,
            latest_decision=detail_decision,
            summary=detail_summary,
            evidence=(
                f"Current blockers: {_names(detail_blocked, empty='none')}. "
                f"Persisted detail-gate events: "
                f"{len(_events_for_gate(gate_events, 'detail_evidence_gate'))}."
            ),
            next_action=detail_next,
            boundary="May recommend repair/review only. No source activation or Bronze persistence.",
            tone=detail_tone,
            affected_candidates=_names(
                detail_blocked, empty="No current detail-evidence blocker"
            ),
            signal_scope="Current blocker wins over historical gate state",
            truth_sources="gold_candidate_lifecycle_status; gate reviews; gate events",
            last_signal_at=_format_time(
                _value(latest_detail_event, "created_at")
                if latest_detail_event
                else None
            ),
        )
    )

    cards.append(
        _card(
            name="Connector Artifact Generation Agent",
            group="Connector Agents",
            status="Ready signal" if artifact_candidates else "No build-ready signal",
            output_quality=(
                "Artifact generation allowed"
                if artifact_candidates
                else "No current build permission"
            ),
            latest_decision=(
                f"{len(artifact_candidates)} candidate(s) with "
                "artifact_generation_allowed"
            ),
            summary=(
                "Identifies candidates where connector artifacts may be generated "
                "inside the existing approval-gated boundary."
            ),
            evidence=f"Candidates: {_names(artifact_candidates, empty='none')}.",
            next_action="Generate or review artifacts only through the approval-gated workflow.",
            boundary=(
                "Artifact generation is not registration, activation, scheduler change "
                "or Bronze write."
            ),
            tone="ok" if artifact_candidates else "neutral",
            affected_candidates=_names(
                artifact_candidates, empty="No build-ready candidate"
            ),
            signal_scope="Current lifecycle build state",
            truth_sources="gold_candidate_lifecycle_status",
            last_signal_at="Current lifecycle snapshot",
        )
    )

    validation_status, validation_tone, validation_quality = _gate_card_state(
        current_candidates=validation_current,
        latest_gate_reviews=validation_reviews,
        relation_available=_relation_state(
            gate_reviews, "employer_origin_candidate_gate_reviews"
        ),
        unavailable_quality="Gate-review relation unavailable",
        missing_status="No current validation signal",
        missing_quality="No persisted validation result in current view",
    )
    cards.append(
        _card(
            name="Connector Validation Agent",
            group="Connector Agents",
            status=validation_status,
            output_quality=validation_quality,
            latest_decision=(
                f"{len(validation_current)} current candidate signal(s) · "
                f"{len(validation_reviews)} latest passed gate-review signal(s)"
            ),
            summary=(
                "Checks connector importability, expected artifacts, bounded preview "
                "behavior and regression evidence before final approval."
            ),
            evidence=(
                f"Current candidates: {_names(validation_current, empty='none')}. "
                f"Latest passed reviews: {_names(validation_reviews, empty='none')}. "
                f"Validation events: "
                f"{len(_events_for_gate(gate_events, 'connector_validation_gate'))}."
            ),
            next_action="Run or review validation before any registration approval.",
            boundary="Validation does not register connectors, activate sources or write Bronze rows.",
            tone=validation_tone,
            affected_candidates=_names(
                [*validation_current, *validation_reviews],
                empty="No persisted validation signal",
            ),
            signal_scope="Current candidate fields + latest persisted gate review",
            truth_sources="gold_candidate_lifecycle_status; employer_origin_candidate_gate_reviews; gate events",
            last_signal_at=_format_time(
                _value(latest_validation_event, "created_at")
                if latest_validation_event
                else _value(_latest(validation_reviews), "created_at")
                if validation_reviews
                else None
            ),
        )
    )

    approval_status, approval_tone, approval_quality = _gate_card_state(
        current_candidates=approval_current,
        latest_gate_reviews=approval_reviews,
        relation_available=_relation_state(
            gate_reviews, "employer_origin_candidate_gate_reviews"
        ),
        unavailable_quality="Gate-review relation unavailable",
        missing_status="No current final approval signal",
        missing_quality="No final approval in current view",
    )
    cards.append(
        _card(
            name="Final Approval Gate Agent",
            group="Approval & Governance",
            status=approval_status,
            output_quality=approval_quality,
            latest_decision=(
                f"{len(approval_current)} current candidate signal(s) · "
                f"{len(approval_reviews)} latest passed gate-review signal(s)"
            ),
            summary=(
                "Requires an explicit human approval decision before connector "
                "registration can be prepared."
            ),
            evidence=(
                f"Current candidates: {_names(approval_current, empty='none')}. "
                f"Latest passed reviews: {_names(approval_reviews, empty='none')}. "
                f"Final-approval events: "
                f"{len(_events_for_gate(gate_events, 'final_approval_gate'))}."
            ),
            next_action="Keep registration and controlled activation as separate gates.",
            boundary=(
                "Final approval may allow registration planning; it still does not "
                "allow activation, ingestion or Bronze writes."
            ),
            tone=approval_tone,
            affected_candidates=_names(
                [*approval_current, *approval_reviews],
                empty="No persisted final-approval signal",
            ),
            signal_scope="Current candidate fields + latest persisted gate review",
            truth_sources="gold_candidate_lifecycle_status; employer_origin_candidate_gate_reviews; gate events",
            last_signal_at=_format_time(
                _value(latest_approval_event, "created_at")
                if latest_approval_event
                else _value(_latest(approval_reviews), "created_at")
                if approval_reviews
                else None
            ),
        )
    )

    gate_relation = _relation_state(
        gate_reviews, "employer_origin_candidate_gate_events"
    )
    if gate_events:
        audit_status = "Healthy"
        audit_tone = "ok"
        audit_quality = "Append-only gate transition evidence available"
        latest_audit_decision = (
            f"{len(gate_events)} event(s) · latest "
            f"{_value(latest_gate_event, 'event_type', 'unknown')} / "
            f"{_event_decision(latest_gate_event)}"
        )
    elif gate_relation is False:
        audit_status = "Signal unavailable"
        audit_tone = "neutral"
        audit_quality = "Gate-event relation unavailable"
        latest_audit_decision = "No queryable gate-event relation"
    else:
        audit_status = "No persisted event signal"
        audit_tone = "neutral"
        audit_quality = "No gate transition event supplied"
        latest_audit_decision = "0 gate events"

    cards.append(
        _card(
            name="Gate State Audit Agent",
            group="Approval & Governance",
            status=audit_status,
            output_quality=audit_quality,
            latest_decision=latest_audit_decision,
            summary=(
                "Surfaces the append-only gate transition trail without treating "
                "history as current approval authority."
            ),
            evidence=(
                f"Latest affected candidate: "
                f"{_candidate_name(latest_gate_event) if latest_gate_event else 'none'}; "
                f"latest gate: "
                f"{_event_gate_name(latest_gate_event) if latest_gate_event else 'unknown'}."
            ),
            next_action="Use events for audit and diagnosis; use the latest review/current lifecycle for decisions.",
            boundary="Audit visibility only. No gate write, approval, registration or activation.",
            tone=audit_tone,
            affected_candidates=_names(
                gate_events, empty="No gate-event candidate signal"
            ),
            signal_scope="Historical append-only audit trail",
            truth_sources="employer_origin_candidate_gate_events",
            last_signal_at=_format_time(
                _value(latest_gate_event, "created_at") if latest_gate_event else None
            ),
        )
    )

    latest_run = getattr(orchestrator_steps, "latest_run", None)
    all_steps = list(getattr(orchestrator_steps, "all_steps", ()))
    attention_steps = list(orchestrator_steps)
    if latest_run:
        run_status = str(_value(latest_run, "run_status", "") or _value(latest_run, "status", ""))
        run_id = _value(latest_run, "run_id", _value(latest_run, "id", "-"))
        if run_status in {"failed", "blocked"}:
            orchestrator_status = "Blocked / failed"
            orchestrator_tone = "bad"
            orchestrator_quality = "Latest persisted run did not complete cleanly"
            orchestrator_next = "Inspect the latest persisted run and resolve its explicit blocker before another cycle."
        elif attention_steps:
            orchestrator_status = "Needs attention"
            orchestrator_tone = "warn"
            orchestrator_quality = "Latest run completed with an actionable attention queue"
            orchestrator_next = "Review the latest-run attention steps before the next cycle."
        else:
            orchestrator_status = "Healthy"
            orchestrator_tone = "ok"
            orchestrator_quality = "Latest persisted run completed without attention steps"
            orchestrator_next = "Monitor the next audit-only cycle."
        orchestrator_decision = (
            f"run #{run_id} · {run_status or 'unknown'} · "
            f"{len(all_steps)} total step(s) · {len(attention_steps)} attention step(s)"
        )
        orchestrator_last_signal = _format_time(
            _value(latest_run, "completed_at", _value(latest_run, "created_at"))
        )
    else:
        run_relation = _relation_state(
            orchestrator_steps, "gold_search_intelligence_orchestrator_latest_run"
        )
        orchestrator_status = (
            "Signal unavailable" if run_relation is False else "No persisted run signal"
        )
        orchestrator_tone = "neutral"
        orchestrator_quality = (
            "Latest-run relation unavailable"
            if run_relation is False
            else "No latest orchestrator run supplied"
        )
        orchestrator_next = "Persist an audit-only orchestrator run before inferring health."
        orchestrator_decision = (
            f"{len(attention_steps)} attention step(s) without latest-run context"
        )
        orchestrator_last_signal = _format_time(
            _value(_latest(attention_steps), "completed_at")
            if attention_steps
            else None
        )

    cards.append(
        _card(
            name="Nightly Intelligence Orchestrator",
            group="Orchestration",
            status=orchestrator_status,
            output_quality=orchestrator_quality,
            latest_decision=orchestrator_decision,
            summary=(
                "Separates latest-run health, the complete persisted step set and "
                "the smaller attention queue."
            ),
            evidence=(
                "Uses gold_search_intelligence_orchestrator_latest_run, "
                "search_intelligence_orchestrator_steps and "
                "gold_search_intelligence_orchestrator_attention_steps."
            ),
            next_action=orchestrator_next,
            boundary=(
                "Audit/control workflow only. No auto-PR, scheduler mutation, "
                "source activation or ingestion side effect."
            ),
            tone=orchestrator_tone,
            affected_candidates="System-level",
            signal_scope="Latest run + all latest-run steps + attention subset",
            truth_sources=(
                "gold_search_intelligence_orchestrator_latest_run; "
                "search_intelligence_orchestrator_steps; "
                "gold_search_intelligence_orchestrator_attention_steps"
            ),
            last_signal_at=orchestrator_last_signal,
        )
    )

    return cards


def build_agent_monitor_summary(agent_cards: list[dict[str, str]]) -> dict[str, int]:
    return {
        "total": len(agent_cards),
        "healthy": sum(1 for card in agent_cards if card["tone"] == "ok"),
        "needs_review": sum(1 for card in agent_cards if card["tone"] == "warn"),
        "blocked": sum(1 for card in agent_cards if card["tone"] == "bad"),
        "no_signal": sum(1 for card in agent_cards if card["tone"] == "neutral"),
    }


def install_agent_health_read_model() -> None:
    """Install v1 builders into the retained Control Center ViewModel module.

    The server-rendered Control Center still owns a large legacy ViewModel file.
    Keeping the bounded health model in this dedicated module avoids expanding
    that file while preserving the existing render/API contract.
    """

    from src.search_intelligence.control_center import view_model

    view_model.build_agent_monitor_cards = build_agent_monitor_cards
    view_model.build_agent_monitor_summary = build_agent_monitor_summary
