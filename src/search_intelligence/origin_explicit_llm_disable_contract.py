"""Normalize explicit LLM-disable semantics without hiding real blockers.

An operator may intentionally run a bounded Tavily-only audit. In that mode an
LLM stage is not misconfigured; it is deliberately skipped. Earlier runtime
versions represented ``llm_disabled_diagnostic_override`` as a configuration
blocker, causing otherwise complete Tavily/evidence runs to end as
``repair_configuration_blocked``.

This contract rewrites only that explicit blocker. Missing credentials, missing
models, provider failures, and budget-reservation errors remain configuration
blockers. The transformed stages are passed back through the normal deterministic
outcome reducer.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from src.search_intelligence.origin_url_default_repair import (
    RepairStage,
    compatibility_payload,
    finalize_outcome,
)

EXPLICIT_LLM_DISABLE_BLOCKER = "llm_disabled_diagnostic_override"


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


def normalize_explicit_llm_disable_outcome(
    payload: Mapping[str, object],
    *,
    llm_disabled: bool,
) -> dict[str, object]:
    """Return a payload where an intentional LLM skip is not a config error."""

    result = dict(payload)
    if not llm_disabled:
        return result

    repair = payload.get("default_repair")
    if not isinstance(repair, Mapping):
        return result
    raw_stages = repair.get("stages")
    if not isinstance(raw_stages, list):
        return result

    evidence = payload.get("evidence_review")
    evidence_map = evidence if isinstance(evidence, Mapping) else {}
    transformed: list[RepairStage] = []
    changed = False

    for raw in raw_stages:
        if not isinstance(raw, Mapping):
            continue
        stage = _stage_from_mapping(raw)
        if stage.blocker != EXPLICIT_LLM_DISABLE_BLOCKER:
            transformed.append(stage)
            continue

        changed = True
        if stage.name == "evidence_and_llm_repair":
            manual_required = bool(
                evidence_map.get("manual_review_required")
                or evidence_map.get("llm_eligible")
            )
            transformed.append(
                replace(
                    stage,
                    status="manual_review" if manual_required else "not_found",
                    blocker=None,
                    reason=(
                        "Deterministic evidence review completed; optional LLM "
                        "adjudication was disabled by explicit runtime policy."
                    ),
                )
            )
        else:
            transformed.append(
                replace(
                    stage,
                    attempted=False,
                    status="skipped",
                    blocker=None,
                    reason="Optional LLM stage disabled by explicit runtime policy.",
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
    normalized["llm_disabled_by_explicit_policy"] = True
    normalized["llm_disable_semantics_normalized"] = True
    return normalized


__all__ = [
    "EXPLICIT_LLM_DISABLE_BLOCKER",
    "normalize_explicit_llm_disable_outcome",
]
