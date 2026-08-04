"""Normalize explicit Tavily-disable semantics without hiding real blockers.

An operator may intentionally run deterministic-only acceptance checks. In that
mode ``tavily_disabled_diagnostic_override`` is a deliberate skip, not a broken
configuration. Missing credentials, provider failures, and budget errors remain
configuration blockers.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from src.search_intelligence.origin_url_default_repair import (
    RepairStage,
    compatibility_payload,
    finalize_outcome,
)

EXPLICIT_TAVILY_DISABLE_BLOCKER = "tavily_disabled_diagnostic_override"


def _stage_from_mapping(raw: Mapping[str, object]) -> RepairStage:
    return RepairStage(
        name=str(raw.get("name") or ""),
        attempted=bool(raw.get("attempted")),
        status=str(raw.get("status") or ""),
        decision=(str(raw.get("decision")) if raw.get("decision") is not None else None),
        selected_url=(
            str(raw.get("selected_url"))
            if raw.get("selected_url") is not None
            else None
        ),
        recommended_url=(
            str(raw.get("recommended_url"))
            if raw.get("recommended_url") is not None
            else None
        ),
        confidence_score=float(raw.get("confidence_score") or 0.0),
        candidate_count=int(raw.get("candidate_count") or 0),
        provider_request_count=int(raw.get("provider_request_count") or 0),
        reason=str(raw.get("reason") or ""),
        blocker=(str(raw.get("blocker")) if raw.get("blocker") is not None else None),
    )


def normalize_explicit_tavily_disable_outcome(
    payload: Mapping[str, object],
    *,
    tavily_disabled: bool,
) -> dict[str, object]:
    """Return a payload where an intentional Tavily skip is not a config error."""

    result = dict(payload)
    if not tavily_disabled:
        return result

    repair = payload.get("default_repair")
    if not isinstance(repair, Mapping):
        return result
    raw_stages = repair.get("stages")
    if not isinstance(raw_stages, list):
        return result

    transformed: list[RepairStage] = []
    changed = False
    for raw in raw_stages:
        if not isinstance(raw, Mapping):
            continue
        stage = _stage_from_mapping(raw)
        if stage.blocker != EXPLICIT_TAVILY_DISABLE_BLOCKER:
            transformed.append(stage)
            continue
        changed = True
        transformed.append(
            replace(
                stage,
                attempted=False,
                status="skipped",
                blocker=None,
                reason="Tavily stage disabled by explicit deterministic-only runtime policy.",
            )
        )

    if not changed:
        return result

    outcome = finalize_outcome(
        company_key=str(repair.get("company_key") or payload.get("company_key") or ""),
        company_name=str(
            repair.get("company_name") or payload.get("company_name") or ""
        ),
        stages=transformed,
    )
    normalized = compatibility_payload(outcome, last_discovery_payload=result)
    normalized["tavily_disabled_by_explicit_policy"] = True
    normalized["tavily_disable_semantics_normalized"] = True
    return normalized


__all__ = [
    "EXPLICIT_TAVILY_DISABLE_BLOCKER",
    "normalize_explicit_tavily_disable_outcome",
]
