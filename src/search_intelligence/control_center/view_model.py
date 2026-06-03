from __future__ import annotations

from typing import Any, Iterable, Mapping


def _value(item: object, name: str, default: object = None) -> object:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def humanize(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "-"
    special = {
        "active_controlled": "Active controlled",
        "manual_review_required": "Needs review",
        "build_approval_required": "Build approval required",
        "artifact_generation_allowed": "Artifact generation allowed",
        "artifacts_present": "Artifacts present",
        "request_explicit_build_approval": "Request explicit build approval",
        "employer_origin_career_site": "Employer-origin career site",
        "employer_origin_ats_backed_career_site": "Employer-origin ATS-backed career site",
        "detail_evidence_gate": "Detail evidence gate",
        "critical": "Critical",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    }
    return special.get(raw, raw.replace("_", " ").replace("-", " ").strip().capitalize())


def tone(value: object) -> str:
    raw = str(value or "").lower()
    if raw in {"active_controlled", "passed", "low", "success", "ok"}:
        return "ok"
    if raw in {"manual_review_required", "medium", "build_approval_required", "open", "review"}:
        return "warn"
    if raw in {"critical", "high", "blocked", "failed"}:
        return "bad"
    return "neutral"


def is_active(candidate: object) -> bool:
    return str(_value(candidate, "status", "")) == "active_controlled"


def needs_build_approval(candidate: object) -> bool:
    return (
        str(_value(candidate, "build_status", "")) == "build_approval_required"
        and str(_value(candidate, "build_recommendation", "")) == "request_explicit_build_approval"
    )


def needs_registration_approval(candidate: object) -> bool:
    return (
        str(_value(candidate, "connector_validation_status", "")) == "passed"
        and str(_value(candidate, "connector_validation_decision", "")) == "ready_for_final_approval"
        and str(_value(candidate, "final_approval_decision", "")) != "approve_connector_registration"
        and not is_active(candidate)
    )


def is_blocked(candidate: object) -> bool:
    return bool(_value(candidate, "latest_blocking_gate"))


def candidate_stage(candidate: object) -> str:
    if is_active(candidate):
        return "Active connector"
    if needs_registration_approval(candidate):
        return "Registration approval"
    if needs_build_approval(candidate):
        return "Build approval"
    blocker = _value(candidate, "latest_blocking_gate")
    if blocker:
        return humanize(blocker)
    return humanize(_value(candidate, "status"))


def path_state(candidate: object) -> str:
    if is_active(candidate):
        return "success"
    if is_blocked(candidate):
        return "blocked"
    if needs_build_approval(candidate) or needs_registration_approval(candidate):
        return "review"
    return "observed"


def candidate_sort_key(candidate: object) -> tuple[int, int, str]:
    state_priority = {"success": 0, "blocked": 1, "review": 2, "observed": 3}.get(path_state(candidate), 4)
    pressure = 0 if str(_value(candidate, "false_negative_risk_level", "")) in {"critical", "high"} else 1
    return (state_priority, pressure, str(_value(candidate, "company_name", "")).lower())


def pipeline_steps(candidate: object) -> list[dict[str, str]]:
    if is_active(candidate):
        states = [
            ("Discover", "done"),
            ("Gate", "done"),
            ("Build", "done"),
            ("Validate", "done"),
            ("Activate", "done"),
            ("Observe", "done"),
        ]
    elif is_blocked(candidate):
        states = [
            ("Discover", "done"),
            ("Evidence", "stop"),
            ("Build", "open"),
            ("Validate", "open"),
            ("Activate", "open"),
            ("Observe", "open"),
        ]
    elif needs_build_approval(candidate) or needs_registration_approval(candidate):
        states = [
            ("Discover", "done"),
            ("Gate", "done"),
            ("Build", "review"),
            ("Validate", "open"),
            ("Activate", "open"),
            ("Observe", "open"),
        ]
    else:
        states = [
            ("Discover", "done"),
            ("Gate", "open"),
            ("Build", "open"),
            ("Validate", "open"),
            ("Activate", "open"),
            ("Observe", "open"),
        ]

    return [{"label": label, "state": state} for label, state in states]


def candidate_card(candidate: object) -> dict[str, Any]:
    blocker_gate = _value(candidate, "latest_blocking_gate")
    blocker_reason = _value(candidate, "latest_blocking_reason")
    status = _value(candidate, "status")

    return {
        "company_name": str(_value(candidate, "company_name", "")),
        "company_key": str(_value(candidate, "company_key", "")),
        "source_name": str(_value(candidate, "source_name_candidate", "")),
        "source_type": humanize(_value(candidate, "source_type_candidate")),
        "status": humanize(status),
        "status_tone": tone(status),
        "path_state": path_state(candidate),
        "stage": candidate_stage(candidate),
        "fn_pressure": humanize(_value(candidate, "false_negative_risk_level")),
        "fn_tone": tone(_value(candidate, "false_negative_risk_level")),
        "gate_score": f"{int(_value(candidate, 'gate_passed_count', 0) or 0)}/{int(_value(candidate, 'gate_total_count', 0) or 0)}",
        "blocker_gate": humanize(blocker_gate) if blocker_gate else None,
        "blocker_reason": str(blocker_reason) if blocker_reason else None,
        "pipeline_steps": pipeline_steps(candidate),
        "next_action": next_action(candidate),
    }


def next_action(candidate: object) -> str:
    if is_active(candidate):
        return "Monitor value"
    if is_blocked(candidate):
        return "Repair evidence"
    if needs_registration_approval(candidate):
        return "Approve registration"
    if needs_build_approval(candidate):
        return "Approve build"
    return "Review candidate"


def source_rows(candidates: Iterable[object]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for candidate in sorted(candidates, key=candidate_sort_key):
        rows.append(
            {
                "company": str(_value(candidate, "company_name", "")),
                "source": str(_value(candidate, "source_name_candidate", "")),
                "type": humanize(_value(candidate, "source_type_candidate")),
                "status": humanize(_value(candidate, "status")),
                "tone": tone(_value(candidate, "latest_blocking_gate") or _value(candidate, "status")),
                "stage": candidate_stage(candidate),
                "layer": "Bronze → Silver → Gold" if is_active(candidate) else "Candidate lifecycle",
            }
        )
    return rows


def _candidate_names(candidates: Iterable[object]) -> str:
    names = [str(_value(candidate, "company_name", "")).strip() for candidate in candidates]
    names = [name for name in names if name]
    return ", ".join(names) if names else "No candidate signal"


def _agent_card(
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
    tone_name: str,
    affected_candidates: str,
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
        "tone": tone_name,
        "affected_candidates": affected_candidates,
    }


def _gate_review_matches(
    gate_reviews: Iterable[object],
    gate_name: str,
    decision: str | None = None,
) -> list[object]:
    matches: list[object] = []
    seen: set[tuple[str, str]] = set()
    for review in gate_reviews:
        if str(_value(review, "gate_name", "")) != gate_name:
            continue
        if str(_value(review, "gate_status", "")) != "passed":
            continue
        if decision is not None and str(_value(review, "decision", "")) != decision:
            continue

        key = (
            str(_value(review, "candidate_id", "")),
            str(_value(review, "gate_name", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        matches.append(review)
    return matches


def _review_names(gate_reviews: Iterable[object]) -> str:
    names = [str(_value(review, "company_name", "")).strip() for review in gate_reviews]
    names = [name for name in names if name]
    unique_names = list(dict.fromkeys(names))
    return ", ".join(unique_names) if unique_names else "No persisted gate-review signal"


def build_agent_monitor_cards(
    candidates: list[object],
    orchestrator_steps: list[object],
    gate_reviews: list[object],
) -> list[dict[str, str]]:
    """Build display-only Agent Monitor cards from real Control Center state.

    This intentionally uses existing lifecycle, gate and orchestrator signals.
    Missing evidence is shown as "No persisted signal yet" instead of being
    invented.
    """

    blocked_candidates = [candidate for candidate in candidates if is_blocked(candidate)]
    active_candidates = [candidate for candidate in candidates if is_active(candidate)]
    detail_blocked = [
        candidate
        for candidate in blocked_candidates
        if str(_value(candidate, "latest_blocking_gate", "")) == "detail_evidence_gate"
    ]
    artifact_candidates = [
        candidate
        for candidate in candidates
        if str(_value(candidate, "build_status", "")) == "artifact_generation_allowed"
    ]
    validation_passed = [
        candidate
        for candidate in candidates
        if str(_value(candidate, "connector_validation_status", "")) == "passed"
    ]
    final_approval_passed = [
        candidate
        for candidate in candidates
        if str(_value(candidate, "final_approval_decision", "")) == "approve_connector_registration"
    ]
    validation_gate_reviews = _gate_review_matches(
        gate_reviews,
        "connector_validation_gate",
        "ready_for_final_approval",
    )
    final_approval_gate_reviews = _gate_review_matches(
        gate_reviews,
        "final_approval_gate",
        "approve_connector_registration",
    )

    if detail_blocked:
        detail_summary = str(_value(detail_blocked[0], "latest_blocking_reason", "Detail evidence requires review."))
        detail_status = "Needs review"
        detail_quality = "Weak evidence"
        detail_decision = "manual_review_required"
        detail_tone = "warn"
        detail_next = "Review detail evidence or rerun bounded repair with adjusted options."
    else:
        detail_summary = "No active detail-evidence blocker is visible in the current lifecycle view."
        detail_status = "Healthy"
        detail_quality = "No blocker"
        detail_decision = "no_active_blocker"
        detail_tone = "ok"
        detail_next = "Monitor future candidate evidence."

    cards = [
        _agent_card(
            name="Candidate Lifecycle Agent",
            group="Lifecycle & Gold Read Models",
            status="Healthy" if candidates else "No signal",
            output_quality="Usable lifecycle state" if candidates else "No persisted signal yet",
            latest_decision=f"{len(active_candidates)} active · {len(blocked_candidates)} blocked · {len(candidates)} total candidates",
            summary="Builds the candidate lifecycle surface used by Dashboard, Source Health and Agent Monitor.",
            evidence=f"Current view includes {_candidate_names(candidates[:5])}.",
            next_action="Use lifecycle state to prioritize blocked and active controlled candidates.",
            boundary="Read-only Gold/ViewModel interpretation. No connector registration, activation or Bronze write.",
            tone_name="ok" if candidates else "neutral",
            affected_candidates=_candidate_names(candidates),
        ),
        _agent_card(
            name="Detail Evidence Repair Agent",
            group="Evidence & Gate Agents",
            status=detail_status,
            output_quality=detail_quality,
            latest_decision=detail_decision,
            summary=detail_summary,
            evidence=f"Affected candidates: {_candidate_names(detail_blocked)}.",
            next_action=detail_next,
            boundary="May recommend repair/review only. No source activation or Bronze persistence.",
            tone_name=detail_tone,
            affected_candidates=_candidate_names(detail_blocked),
        ),
        _agent_card(
            name="Connector Artifact Generation Agent",
            group="Connector Agents",
            status="Ready signal" if artifact_candidates else "No build-ready signal",
            output_quality="Artifact generation allowed" if artifact_candidates else "No persisted build permission yet",
            latest_decision=f"{len(artifact_candidates)} candidate(s) with artifact_generation_allowed",
            summary="Identifies candidates where connector artifacts may be generated under approval-gated boundaries.",
            evidence=f"Candidates: {_candidate_names(artifact_candidates)}.",
            next_action="Generate or review connector artifacts only through the approval-gated workflow.",
            boundary="Artifact generation is not registration, activation, scheduler change or Bronze write.",
            tone_name="ok" if artifact_candidates else "neutral",
            affected_candidates=_candidate_names(artifact_candidates),
        ),
        _agent_card(
            name="Connector Validation Agent",
            group="Connector Agents",
            status="Passed historical signal" if (validation_passed or validation_gate_reviews) else "No current validation signal",
            output_quality="Validated connector artifact" if (validation_passed or validation_gate_reviews) else "No persisted validation result in current view",
            latest_decision=(
                f"{len(validation_passed)} current candidate signal(s) · "
                f"{len(validation_gate_reviews)} persisted gate-review signal(s)"
            ),
            summary="Checks importability, expected files, bounded preview behavior and regression tests before final approval.",
            evidence=(
                f"Current candidates: {_candidate_names(validation_passed)}. "
                f"Gate reviews: {_review_names(validation_gate_reviews)}."
            ),
            next_action="Run or review validation before any registration approval.",
            boundary="Validation does not register connectors, activate sources or write Bronze rows.",
            tone_name="ok" if (validation_passed or validation_gate_reviews) else "neutral",
            affected_candidates=_candidate_names(validation_passed) if validation_passed else _review_names(validation_gate_reviews),
        ),
        _agent_card(
            name="Final Approval Gate Agent",
            group="Approval & Governance",
            status="Passed historical signal" if (final_approval_passed or final_approval_gate_reviews) else "No current final approval signal",
            output_quality="Explicit approval token recorded" if (final_approval_passed or final_approval_gate_reviews) else "No final approval in current view",
            latest_decision=(
                f"{len(final_approval_passed)} current candidate signal(s) · "
                f"{len(final_approval_gate_reviews)} persisted gate-review signal(s)"
            ),
            summary="Requires explicit human approval before connector registration can be prepared.",
            evidence=(
                f"Current candidates: {_candidate_names(final_approval_passed)}. "
                f"Gate reviews: {_review_names(final_approval_gate_reviews)}."
            ),
            next_action="Keep registration and controlled activation as separate gates.",
            boundary="Final approval may allow registration planning; it still does not allow source activation, recurring ingestion or Bronze writes.",
            tone_name="ok" if (final_approval_passed or final_approval_gate_reviews) else "neutral",
            affected_candidates=_candidate_names(final_approval_passed) if final_approval_passed else _review_names(final_approval_gate_reviews),
        ),
    ]

    attention_count = len(orchestrator_steps)
    cards.append(
        _agent_card(
            name="Nightly Intelligence Orchestrator",
            group="Orchestration",
            status="Needs attention" if attention_count else "No attention step in current view",
            output_quality="Actionable attention queue" if attention_count else "No persisted attention signal passed to this render",
            latest_decision=f"{attention_count} attention step(s)",
            summary="Coordinates the next safe review cycle without auto-registering or auto-activating sources.",
            evidence="Uses gold_search_intelligence_orchestrator_attention_steps when available.",
            next_action="Review attention steps before the next cycle.",
            boundary="Audit/control workflow only. No auto-PR, no scheduler mutation and no ingestion side effects.",
            tone_name="warn" if attention_count else "neutral",
            affected_candidates="System-level",
        )
    )

    return cards


def build_agent_monitor_summary(agent_cards: list[dict[str, str]]) -> dict[str, int]:
    return {
        "total": len(agent_cards),
        "healthy": sum(1 for card in agent_cards if card["tone"] == "ok"),
        "needs_review": sum(1 for card in agent_cards if card["tone"] == "warn"),
        "no_signal": sum(1 for card in agent_cards if card["tone"] == "neutral"),
    }


def build_control_center_view_model(
    candidates: list[object],
    *,
    active_tab: str,
    market_summary: object,
    orchestrator_steps: list[object],
    gate_reviews: list[object],
    write_actions_enabled: bool,
    legacy_view_html: str,
    stylesheet: str,
    flash_message: str | None,
) -> dict[str, Any]:
    active_count = int(_value(market_summary, "active_origin_connector_count", 0) or 0)
    if not active_count:
        active_count = sum(1 for item in candidates if is_active(item))

    blocked_count = int(_value(market_summary, "blocked_candidate_count", 0) or 0)
    if not blocked_count:
        blocked_count = sum(1 for item in candidates if is_blocked(item))

    build_approval_count = int(_value(market_summary, "build_approval_required_count", 0) or 0)
    if not build_approval_count:
        build_approval_count = sum(1 for item in candidates if needs_build_approval(item))

    registration_approval_count = sum(1 for item in candidates if needs_registration_approval(item))

    critical_count = int(_value(market_summary, "critical_fn_pressure_candidate_count", 0) or 0)
    if not critical_count:
        critical_count = sum(
            1 for item in candidates if str(_value(item, "false_negative_risk_level", "")) == "critical"
        )

    cards = [candidate_card(item) for item in sorted(candidates, key=candidate_sort_key)]
    success_candidate = next((card for card in cards if card["path_state"] == "success"), None)
    blocked_candidate = next((card for card in cards if card["path_state"] == "blocked"), None)

    nav_items = [
        {"tab": "dashboard", "label": "Dashboard", "count": active_count + critical_count},
        {"tab": "health", "label": "Source Health", "count": critical_count},
        {"tab": "connectors", "label": "Candidates", "count": len(candidates)},
        {"tab": "approvals", "label": "Approvals", "count": build_approval_count + registration_approval_count},
        {"tab": "orchestrator", "label": "Orchestrator", "count": len(orchestrator_steps)},
        {"tab": "agent-monitor", "label": "Agent Monitor", "count": None},
        {"tab": "gaps", "label": "Gap Analysis", "count": None},
        {"tab": "jobs", "label": "Jobs & Applications", "count": None},
        {"tab": "demo-chain", "label": "Demo Chain", "count": None},
    ]

    agent_cards = build_agent_monitor_cards(candidates, orchestrator_steps, gate_reviews)

    return {
        "page_title": "Search Intelligence Control Center",
        "active_tab": active_tab,
        "is_dashboard": active_tab == "dashboard",
        "is_agent_monitor": active_tab == "agent-monitor",
        "stylesheet": stylesheet,
        "flash_message": flash_message,
        "legacy_view_html": legacy_view_html,
        "mode": "write-enabled" if write_actions_enabled else "read-only",
        "nav_items": nav_items,
        "kpis": [
            {"label": "Active connectors", "value": active_count, "helper": "controlled employer-origin source", "tone": "ok"},
            {"label": "Blocked candidates", "value": blocked_count, "helper": "explicit gate stop, no blind activation", "tone": "warn" if blocked_count else "ok"},
            {"label": "Build approvals", "value": build_approval_count, "helper": "no token waiting" if build_approval_count == 0 else "waiting for token", "tone": "warn" if build_approval_count else "neutral"},
            {"label": "Critical FN pressure", "value": critical_count, "helper": "unresolved false-negative pressure", "tone": "bad" if critical_count else "neutral"},
            {"label": "Migration state", "value": "0", "helper": "pending migrations", "tone": "ok"},
            {"label": "Template layer", "value": "J2", "helper": "presentation-only ViewModel path", "tone": "neutral"},
        ],
        "source_rows": source_rows(candidates),
        "candidate_cards": cards,
        "success_candidate": success_candidate,
        "blocked_candidate": blocked_candidate,
        "quality_items": [
            {"title": "Migration tracking", "value": "0 pending", "body": "DB schema state is checksum-backed and reviewable.", "tone": "ok"},
            {"title": "Jinja2 boundary", "value": "presentation", "body": "Templates render prepared display state; product decisions stay outside.", "tone": "ok"},
            {"title": "React path", "value": "open", "body": "ViewModel shape can later become JSON/API state.", "tone": "neutral"},
        ],
        "alerts": [
            {"title": "HDI stopped correctly", "label": "gate", "body": "Existing connector artifact is revalidated, but the lifecycle blocks activation.", "tone": "warn"},
            {"title": "Enercity success path", "label": "live", "body": "Controlled activation produced Bronze/Silver evidence and Gold health visibility.", "tone": "ok"},
            {"title": "No write shortcut", "label": "guardrail", "body": "Dashboard remains presentation-first; approval boundaries stay explicit.", "tone": "neutral"},
        ],
        "guardrails": [
            "No auto-PR",
            "No source activation",
            "No Bronze write",
            "No scheduler change",
            "Explicit approval gates",
            "Responsive SVG-first visuals",
        ],
        "agent_cards": agent_cards,
        "agent_summary": build_agent_monitor_summary(agent_cards),
    }
