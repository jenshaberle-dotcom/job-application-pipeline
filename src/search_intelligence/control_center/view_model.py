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


def build_control_center_view_model(
    candidates: list[object],
    *,
    active_tab: str,
    market_summary: object,
    orchestrator_steps: list[object],
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
        {"tab": "gaps", "label": "Gap Analysis", "count": None},
        {"tab": "jobs", "label": "Jobs & Applications", "count": None},
        {"tab": "demo-chain", "label": "Demo Chain", "count": None},
    ]

    return {
        "page_title": "Search Intelligence Control Center",
        "active_tab": active_tab,
        "is_dashboard": active_tab == "dashboard",
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
    }
