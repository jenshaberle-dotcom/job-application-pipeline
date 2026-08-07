"""DB-backed Agent Monitor v1 read model.

The module converts existing lifecycle, gate-review, gate-event and orchestrator
signals into presentation-ready health cards. It is deliberately read-only and
never executes agents or mutates candidate, source, connector, scheduler or
pipeline state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Mapping, Sequence


class GateSignalCollection(list[object]):
    """Gate reviews plus append-only event and relation-availability context."""

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
        # Preserve explicit unavailable-relation truth through ``value or []``.
        return bool(len(self) or self.events or self.relations)


class OrchestratorSignalCollection(list[object]):
    """Attention steps plus complete latest-run context."""

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
        return bool(len(self) or self.latest_run or self.all_steps or self.relations)


def _value(item: object, name: str, default: object = None) -> object:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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
    return max(
        values,
        key=lambda item: (
            1 if _record_time(item) is not None else 0,
            (_record_time(item) or datetime.min.replace(tzinfo=timezone.utc)).timestamp(),
        ),
    )


def _latest_reviews(gate_reviews: Iterable[object]) -> list[object]:
    grouped: dict[tuple[str, str], list[object]] = {}
    for review in gate_reviews:
        key = (
            str(_value(review, "candidate_id", "")),
            str(_value(review, "gate_name", "")),
        )
        grouped.setdefault(key, []).append(review)
    return [
        latest
        for reviews in grouped.values()
        if (latest := _latest(reviews)) is not None
    ]


def _candidate_id(item: object) -> str:
    return str(_value(item, "candidate_id", ""))


def _candidate_name(item: object) -> str:
    return str(
        _value(item, "company_name", "")
        or _value(item, "display_company_name", "")
        or _value(item, "company_key", "")
    ).strip()


def _names(items: Iterable[object], *, empty: str) -> str:
    unique = list(
        dict.fromkeys(name for item in items if (name := _candidate_name(item)))
    )
    return ", ".join(unique) if unique else empty


def _relation_state(collection: object, relation: str) -> bool | None:
    relations = getattr(collection, "relations", None)
    if not isinstance(relations, Mapping) or relation not in relations:
        return None
    return bool(relations[relation])


def _event_gate_name(event: object) -> str:
    state = _mapping(_value(event, "new_state", {}))
    return str(
        _value(event, "gate_name", "")
        or state.get("gate_name")
        or state.get("name")
        or ""
    )


def _event_decision(event: object) -> str:
    state = _mapping(_value(event, "new_state", {}))
    return str(
        _value(event, "decision", "")
        or state.get("decision")
        or state.get("status")
        or _value(event, "event_type", "")
        or "unknown"
    )


def _events_for_gate(events: Iterable[object], gate_name: str) -> list[object]:
    return [event for event in events if _event_gate_name(event) == gate_name]


def _is_active(candidate: object) -> bool:
    return str(_value(candidate, "status", "")) == "active_controlled"


def _is_blocked(candidate: object) -> bool:
    return bool(_value(candidate, "latest_blocking_gate"))


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


def _gate_health(
    *,
    current: Sequence[object],
    passed: Sequence[object],
    superseded: Sequence[object],
    relation_available: bool | None,
    missing_status: str,
    missing_quality: str,
) -> tuple[str, str, str]:
    if current or passed:
        return "Passed persisted signal", "ok", "Latest gate outcome is usable"
    if superseded:
        return (
            "Historical pass superseded",
            "warn",
            "Current lifecycle blocker overrides older passed gate history",
        )
    if relation_available is False:
        return "Signal unavailable", "neutral", "Gate-review relation unavailable"
    return missing_status, "neutral", missing_quality


def build_agent_monitor_cards(
    candidates: list[object],
    orchestrator_steps: list[object],
    gate_reviews: list[object],
) -> list[dict[str, str]]:
    """Build current Agent Monitor cards from DB-backed read signals.

    Current lifecycle state is decision-authoritative. Gate reviews provide the
    latest persisted gate outcome and gate events provide audit history only.
    An older positive outcome can therefore never override a current blocker.
    """

    events = list(getattr(gate_reviews, "events", ()))
    latest_reviews = _latest_reviews(gate_reviews)
    blocked = [candidate for candidate in candidates if _is_blocked(candidate)]
    blocked_ids = {_candidate_id(candidate) for candidate in blocked}
    active = [candidate for candidate in candidates if _is_active(candidate)]
    detail_blocked = [
        candidate
        for candidate in blocked
        if str(_value(candidate, "latest_blocking_gate", ""))
        == "detail_evidence_gate"
    ]
    artifacts = [
        candidate
        for candidate in candidates
        if str(_value(candidate, "build_status", ""))
        == "artifact_generation_allowed"
    ]

    validation_current = [
        candidate
        for candidate in candidates
        if str(_value(candidate, "connector_validation_status", "")) == "passed"
        and _candidate_id(candidate) not in blocked_ids
    ]
    approval_current = [
        candidate
        for candidate in candidates
        if str(_value(candidate, "final_approval_decision", ""))
        == "approve_connector_registration"
        and _candidate_id(candidate) not in blocked_ids
    ]
    validation_history = [
        review
        for review in latest_reviews
        if str(_value(review, "gate_name", "")) == "connector_validation_gate"
        and str(_value(review, "gate_status", "")) == "passed"
        and str(_value(review, "decision", "")) == "ready_for_final_approval"
    ]
    approval_history = [
        review
        for review in latest_reviews
        if str(_value(review, "gate_name", "")) == "final_approval_gate"
        and str(_value(review, "gate_status", "")) == "passed"
        and str(_value(review, "decision", ""))
        == "approve_connector_registration"
    ]
    validation_passed = [
        review
        for review in validation_history
        if _candidate_id(review) not in blocked_ids
    ]
    approval_passed = [
        review for review in approval_history if _candidate_id(review) not in blocked_ids
    ]
    validation_superseded = [
        review for review in validation_history if _candidate_id(review) in blocked_ids
    ]
    approval_superseded = [
        review for review in approval_history if _candidate_id(review) in blocked_ids
    ]

    latest_event = _latest(events)
    detail_event = _latest(_events_for_gate(events, "detail_evidence_gate"))
    validation_event = _latest(
        _events_for_gate(events, "connector_validation_gate")
    )
    approval_event = _latest(_events_for_gate(events, "final_approval_gate"))

    cards = [
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
                f"{len(active)} active · {len(blocked)} blocked · "
                f"{len(candidates)} total candidates"
            ),
            summary=(
                "Builds the current candidate surface and keeps current blockers "
                "separate from historical gate success."
            ),
            evidence=(
                f"gold_candidate_lifecycle_status supplied {len(candidates)} row(s); "
                f"the gate audit trail supplied {len(events)} event(s)."
            ),
            next_action="Prioritize current blockers; use history only as evidence.",
            boundary=(
                "Read-only interpretation. No registration, activation, scheduler "
                "mutation or Bronze write."
            ),
            tone="ok" if candidates else "neutral",
            affected_candidates=_names(candidates, empty="No candidate signal"),
            signal_scope="Current lifecycle plus audit context",
            truth_sources=(
                "gold_candidate_lifecycle_status; "
                "employer_origin_candidate_gate_events"
            ),
            last_signal_at=_format_time(
                _value(latest_event, "created_at") if latest_event else None
            ),
        )
    ]

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
        detail_next = "Review evidence or run only the bounded repair workflow."
    else:
        detail_status = "Healthy"
        detail_tone = "ok"
        detail_quality = "No current detail-evidence blocker"
        detail_decision = "no_active_blocker"
        detail_summary = "No active detail-evidence blocker is visible."
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
                f"{len(_events_for_gate(events, 'detail_evidence_gate'))}."
            ),
            next_action=detail_next,
            boundary="May recommend repair/review only. No activation or Bronze write.",
            tone=detail_tone,
            affected_candidates=_names(
                detail_blocked, empty="No current detail-evidence blocker"
            ),
            signal_scope="Current blocker overrides historical state",
            truth_sources="lifecycle; gate reviews; gate events",
            last_signal_at=_format_time(
                _value(detail_event, "created_at") if detail_event else None
            ),
        )
    )

    cards.append(
        _card(
            name="Connector Artifact Generation Agent",
            group="Connector Agents",
            status="Ready signal" if artifacts else "No build-ready signal",
            output_quality=(
                "Artifact generation allowed"
                if artifacts
                else "No current build permission"
            ),
            latest_decision=(
                f"{len(artifacts)} candidate(s) with artifact_generation_allowed"
            ),
            summary=(
                "Identifies candidates where connector artifacts may be generated "
                "inside the approval-gated boundary."
            ),
            evidence=f"Candidates: {_names(artifacts, empty='none')}.",
            next_action="Generate or review artifacts only through the gated workflow.",
            boundary=(
                "Artifact generation is not registration, activation, scheduler "
                "change or Bronze write."
            ),
            tone="ok" if artifacts else "neutral",
            affected_candidates=_names(artifacts, empty="No build-ready candidate"),
            signal_scope="Current lifecycle build state",
            truth_sources="gold_candidate_lifecycle_status",
            last_signal_at="Current lifecycle snapshot",
        )
    )

    review_relation = _relation_state(
        gate_reviews, "employer_origin_candidate_gate_reviews"
    )
    validation_status, validation_tone, validation_quality = _gate_health(
        current=validation_current,
        passed=validation_passed,
        superseded=validation_superseded,
        relation_available=review_relation,
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
                f"{len(validation_current)} current · "
                f"{len(validation_passed)} latest passed · "
                f"{len(validation_superseded)} superseded"
            ),
            summary=(
                "Checks importability, artifacts, bounded preview behavior and "
                "regression evidence before final approval."
            ),
            evidence=(
                f"Usable: {_names([*validation_current, *validation_passed], empty='none')}. "
                f"Superseded: {_names(validation_superseded, empty='none')}."
            ),
            next_action="Run or review validation before registration approval.",
            boundary="Validation does not register, activate or write Bronze rows.",
            tone=validation_tone,
            affected_candidates=_names(
                [*validation_current, *validation_passed, *validation_superseded],
                empty="No persisted validation signal",
            ),
            signal_scope="Current fields plus latest review per candidate/gate",
            truth_sources="lifecycle; gate reviews; gate events",
            last_signal_at=_format_time(
                _value(validation_event, "created_at")
                if validation_event
                else _value(_latest(validation_history), "created_at")
                if validation_history
                else None
            ),
        )
    )

    approval_status, approval_tone, approval_quality = _gate_health(
        current=approval_current,
        passed=approval_passed,
        superseded=approval_superseded,
        relation_available=review_relation,
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
                f"{len(approval_current)} current · "
                f"{len(approval_passed)} latest passed · "
                f"{len(approval_superseded)} superseded"
            ),
            summary=(
                "Requires an explicit human decision before connector registration "
                "can be prepared."
            ),
            evidence=(
                f"Usable: {_names([*approval_current, *approval_passed], empty='none')}. "
                f"Superseded: {_names(approval_superseded, empty='none')}."
            ),
            next_action="Keep registration and activation as separate gates.",
            boundary=(
                "Final approval still does not allow activation, ingestion or "
                "Bronze writes."
            ),
            tone=approval_tone,
            affected_candidates=_names(
                [*approval_current, *approval_passed, *approval_superseded],
                empty="No persisted final-approval signal",
            ),
            signal_scope="Current fields plus latest review per candidate/gate",
            truth_sources="lifecycle; gate reviews; gate events",
            last_signal_at=_format_time(
                _value(approval_event, "created_at")
                if approval_event
                else _value(_latest(approval_history), "created_at")
                if approval_history
                else None
            ),
        )
    )

    event_relation = _relation_state(
        gate_reviews, "employer_origin_candidate_gate_events"
    )
    if events:
        audit_status = "Healthy"
        audit_tone = "ok"
        audit_quality = "Append-only gate transition evidence available"
        audit_decision = (
            f"{len(events)} event(s) · latest "
            f"{_value(latest_event, 'event_type', 'unknown')} / "
            f"{_event_decision(latest_event)}"
        )
    elif event_relation is False:
        audit_status = "Signal unavailable"
        audit_tone = "neutral"
        audit_quality = "Gate-event relation unavailable"
        audit_decision = "No queryable gate-event relation"
    else:
        audit_status = "No persisted event signal"
        audit_tone = "neutral"
        audit_quality = "No gate transition event supplied"
        audit_decision = "0 gate events"

    cards.append(
        _card(
            name="Gate State Audit Agent",
            group="Approval & Governance",
            status=audit_status,
            output_quality=audit_quality,
            latest_decision=audit_decision,
            summary=(
                "Surfaces append-only gate transitions without treating history "
                "as current approval authority."
            ),
            evidence=(
                f"Latest candidate: "
                f"{_candidate_name(latest_event) if latest_event else 'none'}; "
                f"latest gate: "
                f"{_event_gate_name(latest_event) if latest_event else 'unknown'}."
            ),
            next_action=(
                "Use events for audit; use current lifecycle and latest review "
                "for decisions."
            ),
            boundary="Audit visibility only. No gate write, approval or activation.",
            tone=audit_tone,
            affected_candidates=_names(
                events, empty="No gate-event candidate signal"
            ),
            signal_scope="Historical append-only audit trail",
            truth_sources="employer_origin_candidate_gate_events",
            last_signal_at=_format_time(
                _value(latest_event, "created_at") if latest_event else None
            ),
        )
    )

    latest_run = getattr(orchestrator_steps, "latest_run", None)
    all_steps = list(getattr(orchestrator_steps, "all_steps", ()))
    attention = list(orchestrator_steps)
    if latest_run:
        run_status = str(
            _value(latest_run, "run_status", "")
            or _value(latest_run, "status", "")
        )
        run_id = _value(latest_run, "run_id", _value(latest_run, "id", "-"))
        if run_status in {"failed", "blocked"}:
            orch_status = "Blocked / failed"
            orch_tone = "bad"
            orch_quality = "Latest persisted run did not complete cleanly"
            orch_next = "Resolve the explicit run blocker before another cycle."
        elif attention:
            orch_status = "Needs attention"
            orch_tone = "warn"
            orch_quality = "Latest run has an actionable attention queue"
            orch_next = "Review latest-run attention steps before the next cycle."
        else:
            orch_status = "Healthy"
            orch_tone = "ok"
            orch_quality = "Latest run completed without attention steps"
            orch_next = "Monitor the next audit-only cycle."
        orch_decision = (
            f"run #{run_id} · {run_status or 'unknown'} · "
            f"{len(all_steps)} total · {len(attention)} attention"
        )
        orch_time = _format_time(
            _value(latest_run, "completed_at")
            or _value(latest_run, "created_at")
        )
    else:
        run_relation = _relation_state(
            orchestrator_steps,
            "gold_search_intelligence_orchestrator_latest_run",
        )
        orch_status = (
            "Signal unavailable" if run_relation is False else "No persisted run signal"
        )
        orch_tone = "neutral"
        orch_quality = (
            "Latest-run relation unavailable"
            if run_relation is False
            else "No latest orchestrator run supplied"
        )
        orch_next = "Persist an audit-only run before inferring health."
        orch_decision = f"{len(attention)} attention step(s) without run context"
        orch_time = _format_time(
            _value(_latest(attention), "completed_at") if attention else None
        )

    cards.append(
        _card(
            name="Nightly Intelligence Orchestrator",
            group="Orchestration",
            status=orch_status,
            output_quality=orch_quality,
            latest_decision=orch_decision,
            summary=(
                "Separates latest-run health, all latest-run steps and the "
                "smaller attention subset."
            ),
            evidence=(
                "Uses latest-run, persisted-step and attention-view DB truth."
            ),
            next_action=orch_next,
            boundary=(
                "Audit/control only. No auto-PR, scheduler mutation, activation "
                "or ingestion."
            ),
            tone=orch_tone,
            affected_candidates="System-level",
            signal_scope="Latest run plus all steps plus attention subset",
            truth_sources=(
                "gold_search_intelligence_orchestrator_latest_run; "
                "search_intelligence_orchestrator_steps; "
                "gold_search_intelligence_orchestrator_attention_steps"
            ),
            last_signal_at=orch_time,
        )
    )
    return cards


def build_agent_monitor_summary(agent_cards: list[dict[str, str]]) -> dict[str, int]:
    return {
        "total": len(agent_cards),
        "healthy": sum(card["tone"] == "ok" for card in agent_cards),
        "needs_review": sum(card["tone"] == "warn" for card in agent_cards),
        "blocked": sum(card["tone"] == "bad" for card in agent_cards),
        "no_signal": sum(card["tone"] == "neutral" for card in agent_cards),
    }


def install_agent_health_read_model() -> None:
    """Install v1 builders into the retained legacy ViewModel module."""

    from src.search_intelligence.control_center import view_model

    view_model.build_agent_monitor_cards = build_agent_monitor_cards
    view_model.build_agent_monitor_summary = build_agent_monitor_summary
