"""Evaluate explicit operator URL hints before accepting fallback discovery.

An operator URL is untrusted evidence, not an allowlist entry. It must pass the
same deterministic origin assessment as every generated or provider candidate.
When it passes, it takes decision precedence over an already known baseline URL;
when it does not pass, the normal staged repair continues without retrying the
same operator URL.

The contract adds no provider call and performs no database or pipeline write.
"""

from __future__ import annotations

from copy import copy
from typing import Any, Callable, Mapping

from src.search_intelligence.adaptive_origin_search import SearchProgressLedger
from src.search_intelligence.origin_url_default_repair import (
    RepairStage,
    compatibility_payload,
    finalize_outcome,
    selected_url,
    skipped_stage,
    stage_from_discovery,
)


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


def _operator_urls(args: object, ledger: SearchProgressLedger) -> tuple[str, ...]:
    raw = getattr(args, "operator_url", []) or []
    values = [raw] if isinstance(raw, str) else list(raw)
    return ledger.novel_urls(str(item) for item in values)


def _operator_assessment(payload: Mapping[str, object]) -> dict[str, object]:
    """Preserve the exact deterministic operator assessment as review evidence."""

    return {
        "artifact_type": "deterministic_operator_url_assessment",
        "schema_version": "1.0",
        "review_output_only_not_pipeline_input": True,
        "provider_requests": 0,
        "pipeline_mutation": False,
        "source_activation_allowed": False,
        "payload": dict(payload),
    }


def _operator_metadata(
    *,
    urls: tuple[str, ...],
    payload: Mapping[str, object],
    fingerprint: str,
    progressed: bool,
) -> dict[str, object]:
    return {
        "attempted": True,
        "urls": list(urls),
        "decision": payload.get("decision"),
        "selected_url": payload.get("selected_url"),
        "provider_requests": 0,
        "state_fingerprint": fingerprint,
        "state_progressed": progressed,
        "untrusted_hint_still_requires_all_origin_gates": True,
        "assessment": _operator_assessment(payload),
    }


def run_with_operator_url_precedence(
    staged_runner: Callable[[Any, str], dict[str, object]],
    *,
    staged_module: Any,
    args: Any,
    company_key: str,
) -> dict[str, object]:
    """Run one deterministic operator-hint assessment before fallback repair."""

    ledger = SearchProgressLedger()
    urls = _operator_urls(args, ledger)
    if not urls:
        return staged_runner(args, company_key)

    rows = staged_module.adaptive._hypothesis_rows(
        company_key=company_key,
        urls=urls,
        provider="operator_supplied_unvalidated",
        rationale="operator hint; still requires deterministic validation",
    )
    operator_payload = staged_module.adaptive._run_atomic_with_rows(
        args,
        company_key=company_key,
        rows=rows,
    )
    fingerprint, progressed = ledger.record_state(operator_payload)
    operator_stage = stage_from_discovery(
        "deterministic_operator_url",
        operator_payload,
    )
    company_name = str(operator_payload.get("company_name") or company_key)
    metadata = _operator_metadata(
        urls=urls,
        payload=operator_payload,
        fingerprint=fingerprint,
        progressed=progressed,
    )

    if selected_url(operator_payload):
        stages = [
            operator_stage,
            skipped_stage(
                "deterministic_baseline",
                "Explicit operator URL passed deterministic validation first.",
            ),
            skipped_stage(
                "deterministic_symbol_brand",
                "Explicit operator URL passed deterministic validation first.",
            ),
            skipped_stage(
                "tavily_repair",
                "Explicit operator URL passed deterministic validation; provider search was unnecessary.",
            ),
            skipped_stage(
                "llm_search_hypothesis_repair",
                "Explicit operator URL passed deterministic validation.",
            ),
            skipped_stage(
                "evidence_and_llm_repair",
                "Explicit operator URL passed deterministic validation.",
            ),
        ]
        outcome = finalize_outcome(
            company_key=company_key,
            company_name=company_name,
            stages=stages,
        )
        result = compatibility_payload(
            outcome,
            last_discovery_payload=operator_payload,
        )
        result["operator_url_precedence"] = metadata
        result["baseline_result"] = dict(operator_payload)
        result["adaptive_search"] = {
            "finite_state_machine": True,
            "identical_retry_forbidden": True,
            "operator_url_precedence": True,
            **ledger.to_json(),
        }
        result["score_semantics"] = {
            "selected_or_review_stage": "confidence_score",
            "not_found_stage": "best_observed_candidate_score_not_decision_confidence",
        }
        return result

    fallback_args = copy(args)
    setattr(fallback_args, "operator_url", [])
    fallback = staged_runner(fallback_args, company_key)
    repair = fallback.get("default_repair")
    if not isinstance(repair, Mapping):
        result = dict(fallback)
        result["operator_url_precedence"] = metadata
        return result
    raw_stages = repair.get("stages")
    if not isinstance(raw_stages, list):
        result = dict(fallback)
        result["operator_url_precedence"] = metadata
        return result

    stages = [operator_stage]
    stages.extend(
        _stage_from_mapping(raw)
        for raw in raw_stages
        if isinstance(raw, Mapping)
    )
    outcome = finalize_outcome(
        company_key=str(repair.get("company_key") or company_key),
        company_name=str(repair.get("company_name") or company_name),
        stages=stages,
    )
    result = compatibility_payload(outcome, last_discovery_payload=fallback)
    result["operator_url_precedence"] = metadata
    return result


__all__ = ["run_with_operator_url_precedence"]
