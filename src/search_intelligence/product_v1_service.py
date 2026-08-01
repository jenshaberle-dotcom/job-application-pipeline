"""Pure payload assembly for the Product V1 Control Center API."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping, Sequence


def _value(item: Mapping[str, Any], key: str, default: Any = None) -> Any:
    return item.get(key, default)


def json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def build_product_v1_payload(
    *,
    wave_states: Sequence[Mapping[str, Any]],
    job_readiness: Sequence[Mapping[str, Any]],
    top_jobs: Sequence[Mapping[str, Any]],
    ranking_policy: Mapping[str, Any] | None,
    application_readiness: Sequence[Mapping[str, Any]],
    application_sources: Sequence[Mapping[str, Any]],
    migration_ready: bool,
    hard_filter_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    policy = dict(ranking_policy or {})
    policy_status = str(policy.get("status") or "operator_decision_required")
    hard_policy = dict(hard_filter_policy or {})
    hard_policy_status = str(
        hard_policy.get("status") or "operator_decision_required"
    )
    rankable_count = sum(
        1
        for job in job_readiness
        if _value(job, "product_readiness_status") == "rankable"
    )
    origin_blocker_count = sum(
        1
        for job in job_readiness
        if _value(job, "product_readiness_status")
        in {"blocked_origin", "origin_validation_required"}
    )
    approved_source_types = {
        str(_value(source, "document_type"))
        for source in application_sources
        if _value(source, "status") == "approved"
    }
    application_sources_ready = {
        "base_cv": "base_cv" in approved_source_types,
        "base_application_letter": "base_application_letter"
        in approved_source_types,
    }

    operator_blockers: list[dict[str, str]] = []
    if not migration_ready:
        operator_blockers.append(
            {
                "code": "migration_required",
                "title": "Product V1 migration not applied",
                "detail": "Apply the reviewed migrations before DB-backed Product V1 state can be served.",
            }
        )
    if policy_status != "approved":
        operator_blockers.append(
            {
                "code": "ranking_policy_required",
                "title": "Top-5 product decisions required",
                "detail": "Count semantics, threshold, factor weights, comparable-job tolerance and explanation mode remain operator-owned.",
            }
        )
    if hard_filter_policy is not None and hard_policy_status != "approved":
        operator_blockers.append(
            {
                "code": "hard_filter_policy_required",
                "title": "Hard-filter product decisions required",
                "detail": "Employment, language, working-time, seniority and salary treatment must be operator-approved.",
            }
        )
    if not application_sources_ready["base_cv"]:
        operator_blockers.append(
            {
                "code": "base_cv_required",
                "title": "Approved base CV required",
                "detail": "The application assistant remains blocked until an operator-approved base CV is registered.",
            }
        )
    if not application_sources_ready["base_application_letter"]:
        operator_blockers.append(
            {
                "code": "base_application_letter_required",
                "title": "Approved base application letter required",
                "detail": "The application assistant remains blocked until an operator-approved base letter is registered.",
            }
        )

    top_jobs_available = (
        policy_status == "approved"
        and (hard_filter_policy is None or hard_policy_status == "approved")
    )
    payload = {
        "schema_version": "pipeline.product_v1.control_center.v1",
        "product": {
            "name": "Deep Ocean Intelligence Job Pipeline",
            "character": "intent_locked",
            "target_profile": "Machine Learning Engineer with strong Data Engineering and Reliability focus",
        },
        "pillars": [
            {
                "id": "stepstone_waves",
                "title": "StepStone Waves",
                "status": "available"
                if wave_states
                else "waiting_for_runtime_state",
                "summary": "Bounded company-exclusion waves rotate through a logical cooldown pool without pagination.",
            },
            {
                "id": "top_jobs",
                "title": "Origin-validated Top 5",
                "status": "available"
                if top_jobs_available
                else "operator_decision_required",
                "summary": "Only current, origin-validated, hard-filter-passing jobs can enter authoritative ranking.",
            },
            {
                "id": "application_assistant",
                "title": "CV & Application Letter Assistant",
                "status": "ready_for_inputs"
                if all(application_sources_ready.values())
                else "operator_inputs_required",
                "summary": "Source-grounded draft preparation with no invented facts and no automatic submission.",
            },
            {
                "id": "react_control_center",
                "title": "React Control Center",
                "status": "source_ready",
                "summary": "Deep Ocean Intelligence frontend consuming this read-only Product V1 API.",
            },
        ],
        "summary": {
            "wave_term_count": len(wave_states),
            "observed_job_count": len(job_readiness),
            "rankable_job_count": rankable_count,
            "origin_blocker_count": origin_blocker_count,
            "top_job_count": len(top_jobs),
            "application_ready_count": sum(
                1
                for item in application_readiness
                if _value(item, "application_readiness_status")
                == "ready_for_generation"
            ),
        },
        "wave_states": list(wave_states),
        "ranking_policy": policy or {"status": "operator_decision_required"},
        "hard_filter_policy": hard_policy
        or {"status": "operator_decision_required"},
        "job_readiness": list(job_readiness),
        "top_jobs": list(top_jobs),
        "application_readiness": list(application_readiness),
        "application_sources": list(application_sources),
        "application_sources_ready": application_sources_ready,
        "operator_blockers": operator_blockers,
        "boundaries": {
            "read_only_api": True,
            "no_provider_call": True,
            "no_automatic_application": True,
            "no_source_activation": True,
            "no_scheduler_mutation": True,
            "aggregator_evidence_is_not_top5_truth": True,
            "current_compensation_is_local_runtime_context_only": True,
        },
    }
    return json_safe(payload)
