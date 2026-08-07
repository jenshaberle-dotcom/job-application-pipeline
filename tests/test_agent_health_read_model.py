from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from src.search_intelligence.control_center.agent_health_read_model import (
    GateSignalCollection,
    OrchestratorSignalCollection,
    build_agent_monitor_cards,
    build_agent_monitor_summary,
)
from src.search_intelligence.control_center.renderer import render_template


def _candidate(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "candidate_id": 7,
        "company_key": "example",
        "company_name": "Example AG",
        "status": "connector_candidate",
        "latest_blocking_gate": None,
        "latest_blocking_decision": None,
        "latest_blocking_reason": None,
        "build_status": "artifact_generation_allowed",
        "connector_validation_status": None,
        "final_approval_decision": None,
    }
    value.update(overrides)
    return value


def _review(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "candidate_id": 7,
        "company_key": "example",
        "company_name": "Example AG",
        "gate_name": "connector_validation_gate",
        "gate_status": "passed",
        "decision": "ready_for_final_approval",
        "created_at": "2026-08-06T12:00:00+00:00",
    }
    value.update(overrides)
    return value


def _event(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "candidate_id": 7,
        "company_key": "example",
        "company_name": "Example AG",
        "gate_name": "connector_validation_gate",
        "event_type": "gate_updated",
        "new_state": {
            "gate_name": "connector_validation_gate",
            "decision": "ready_for_final_approval",
        },
        "created_at": "2026-08-06T12:01:00+00:00",
    }
    value.update(overrides)
    return value


def _step(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "run_id": 41,
        "step_order": 1,
        "step_name": "candidate_lifecycle_review",
        "step_status": "ok",
        "action_mode": "observe",
        "recommendation": "Continue monitoring.",
        "reason": None,
        "completed_at": "2026-08-06T12:05:00+00:00",
    }
    value.update(overrides)
    return value


def _card(cards: list[dict[str, str]], name: str) -> dict[str, str]:
    return next(card for card in cards if card["name"] == name)


def test_latest_gate_review_replaces_older_passed_history() -> None:
    reviews = GateSignalCollection(
        [
            _review(created_at="2026-08-06T11:00:00+00:00"),
            _review(
                gate_status="manual_review_required",
                decision="manual_review_required",
                created_at="2026-08-06T13:00:00+00:00",
            ),
        ],
        relations={"employer_origin_candidate_gate_reviews": True},
    )

    cards = build_agent_monitor_cards([_candidate()], [], reviews)
    validation = _card(cards, "Connector Validation Agent")

    assert validation["tone"] == "neutral"
    assert validation["status"] == "No current validation signal"
    assert "0 latest passed" in validation["latest_decision"]


def test_current_lifecycle_blocker_supersedes_older_positive_gate_history() -> None:
    candidates = [
        _candidate(
            status="manual_review_required",
            latest_blocking_gate="detail_evidence_gate",
            latest_blocking_decision="manual_review_required",
            latest_blocking_reason="Current detail evidence is insufficient.",
        )
    ]
    reviews = GateSignalCollection(
        [_review()],
        relations={"employer_origin_candidate_gate_reviews": True},
    )

    cards = build_agent_monitor_cards(candidates, [], reviews)
    validation = _card(cards, "Connector Validation Agent")
    detail = _card(cards, "Detail Evidence Repair Agent")

    assert validation["status"] == "Historical pass superseded"
    assert validation["tone"] == "warn"
    assert "Example AG" in validation["evidence"]
    assert detail["status"] == "Needs review"
    assert detail["latest_decision"] == "manual_review_required"


def test_gate_event_audit_is_visible_without_becoming_decision_authority() -> None:
    reviews = GateSignalCollection(
        [_review()],
        events=[_event()],
        relations={
            "employer_origin_candidate_gate_reviews": True,
            "employer_origin_candidate_gate_events": True,
        },
    )

    cards = build_agent_monitor_cards([_candidate()], [], reviews)
    audit = _card(cards, "Gate State Audit Agent")

    assert audit["status"] == "Healthy"
    assert audit["tone"] == "ok"
    assert "1 event(s)" in audit["latest_decision"]
    assert audit["last_signal_at"] == "2026-08-06T12:01:00Z"
    assert audit["signal_scope"] == "Historical append-only audit trail"
    assert "Audit visibility only" in audit["boundary"]


def test_latest_orchestrator_run_can_be_healthy_without_attention_steps() -> None:
    all_steps = [_step(), _step(step_order=2, step_name="approval_queue_review")]
    signals = OrchestratorSignalCollection(
        [],
        latest_run={
            "run_id": 41,
            "run_status": "completed",
            "completed_at": "2026-08-06T12:06:00+00:00",
        },
        all_steps=all_steps,
        relations={
            "gold_search_intelligence_orchestrator_latest_run": True,
            "search_intelligence_orchestrator_steps": True,
            "gold_search_intelligence_orchestrator_attention_steps": True,
        },
    )

    cards = build_agent_monitor_cards([], signals, GateSignalCollection())
    orchestrator = _card(cards, "Nightly Intelligence Orchestrator")

    assert bool(signals)
    assert orchestrator["status"] == "Healthy"
    assert orchestrator["tone"] == "ok"
    assert "2 total · 0 attention" in orchestrator["latest_decision"]
    assert orchestrator["last_signal_at"] == "2026-08-06T12:06:00Z"


def test_orchestrator_attention_and_failed_run_remain_distinct() -> None:
    attention = _step(
        step_status="attention_required",
        action_mode="queue_review",
        recommendation="Review the queue.",
    )
    warning_signals = OrchestratorSignalCollection(
        [attention],
        latest_run={"run_id": 41, "run_status": "completed"},
        all_steps=[attention],
    )
    failed_signals = OrchestratorSignalCollection(
        [attention],
        latest_run={"run_id": 42, "run_status": "failed"},
        all_steps=[attention],
    )

    warning = _card(
        build_agent_monitor_cards([], warning_signals, GateSignalCollection()),
        "Nightly Intelligence Orchestrator",
    )
    failed_cards = build_agent_monitor_cards(
        [], failed_signals, GateSignalCollection()
    )
    failed = _card(failed_cards, "Nightly Intelligence Orchestrator")

    assert warning["status"] == "Needs attention"
    assert warning["tone"] == "warn"
    assert failed["status"] == "Blocked / failed"
    assert failed["tone"] == "bad"
    assert build_agent_monitor_summary(failed_cards)["blocked"] == 1


def test_unavailable_relations_are_explicit_and_never_optimistic() -> None:
    gate_signals = GateSignalCollection(
        relations={
            "employer_origin_candidate_gate_reviews": False,
            "employer_origin_candidate_gate_events": False,
        }
    )
    orchestrator_signals = OrchestratorSignalCollection(
        relations={"gold_search_intelligence_orchestrator_latest_run": False}
    )

    cards = build_agent_monitor_cards([], orchestrator_signals, gate_signals)

    assert bool(gate_signals)
    assert bool(orchestrator_signals)
    assert _card(cards, "Connector Validation Agent")["status"] == "Signal unavailable"
    assert _card(cards, "Gate State Audit Agent")["status"] == "Signal unavailable"
    assert _card(cards, "Nightly Intelligence Orchestrator")["status"] == "Signal unavailable"


def test_mixed_naive_aware_and_missing_timestamps_are_deterministic() -> None:
    reviews = GateSignalCollection(
        [
            _review(created_at=None),
            _review(created_at="2026-08-06T11:00:00"),
            _review(
                gate_status="failed",
                decision="manual_review_required",
                created_at="2026-08-06T12:00:00+00:00",
            ),
        ],
        relations={"employer_origin_candidate_gate_reviews": True},
    )

    validation = _card(
        build_agent_monitor_cards([_candidate()], [], reviews),
        "Connector Validation Agent",
    )

    assert validation["status"] == "No current validation signal"


def test_read_model_does_not_mutate_inputs() -> None:
    candidates = [_candidate()]
    review_values = [_review()]
    event_values = [_event()]
    candidate_snapshot = deepcopy(candidates)
    review_snapshot = deepcopy(review_values)
    event_snapshot = deepcopy(event_values)

    build_agent_monitor_cards(
        candidates,
        OrchestratorSignalCollection(),
        GateSignalCollection(review_values, events=event_values),
    )

    assert candidates == candidate_snapshot
    assert review_values == review_snapshot
    assert event_values == event_snapshot


def test_agent_monitor_template_renders_v1_scope_and_provenance() -> None:
    cards = build_agent_monitor_cards(
        [_candidate()],
        OrchestratorSignalCollection(
            [], latest_run={"run_id": 41, "run_status": "completed"}
        ),
        GateSignalCollection([_review()], events=[_event()]),
    )
    html = render_template(
        "agent_monitor.html",
        {
            "agent_cards": cards,
            "agent_summary": build_agent_monitor_summary(cards),
        },
    )

    assert "Agent Monitor v1" in html
    assert "Gate State Audit Agent" in html
    assert "Signal scope" in html
    assert "Truth provenance" in html
    assert "Last persisted signal" in html
    assert "not faked, explicitly marked" in html


def test_runtime_adapter_contains_only_read_queries_for_new_signals() -> None:
    source = Path("scripts/run_search_intelligence_control_center.py").read_text(
        encoding="utf-8"
    )
    upper = source.upper()

    assert "INSTALL_AGENT_HEALTH_READ_MODEL()" in upper
    assert "EMPLOYER_ORIGIN_CANDIDATE_GATE_EVENTS" in upper
    assert "GOLD_SEARCH_INTELLIGENCE_ORCHESTRATOR_LATEST_RUN" in upper
    assert "SEARCH_INTELLIGENCE_ORCHESTRATOR_STEPS" in upper
    assert "INSERT INTO" not in upper
    assert "UPDATE EMPLOYER_ORIGIN" not in upper
    assert "DELETE FROM" not in upper
