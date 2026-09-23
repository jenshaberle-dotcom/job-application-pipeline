"""Pure payload assembly for the Product V1 Control Center API."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping, Sequence

from src.search_intelligence.f6_template_authority import authority_status
from src.search_intelligence.product_v1_profile_fit_coverage import (
    INSUFFICIENT_EVIDENCE,
    PROFILE_FIT_COMPLETE,
    enrich_profile_fit_coverage,
)
from src.search_intelligence.product_v1_review_fit import enrich_review_fit
from src.search_intelligence.source_connector_overview import (
    empty_source_connector_overview,
)


CURRENT_LIFECYCLE_STATES = {
    "active_confirmed",
    "stale_needs_refresh",
    "inactive_confirmed",
    "unverifiable",
}


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


def _display_job(
    row: Mapping[str, Any],
    *,
    profile_fit_preference_tags: Sequence[str] = (),
) -> dict[str, Any]:
    """Expose Candidate Fit and exact-bound PD-052 Affinity as separate truths."""
    enriched = enrich_profile_fit_coverage(
        row, candidate_preference_tags=profile_fit_preference_tags
    )
    enriched = enrich_review_fit(enriched)

    affinity_score = row.get("affinity_score")
    affinity_status = str(row.get("affinity_authority_status") or "unavailable")
    enriched["affinity_score"] = affinity_score
    enriched["affinity_authority"] = row.get("affinity_authority") or "pd-052"
    enriched["affinity_authority_status"] = affinity_status
    enriched["affinity_components"] = {
        "profile_direction": row.get("affinity_profile_direction_score"),
        "reliability_focus": row.get("affinity_reliability_focus_score"),
        "data_focus": row.get("affinity_data_focus_score"),
        "evidence_quality": row.get("affinity_evidence_quality_score"),
    }
    # Legacy name retained for existing application/ranking compatibility. It is
    # now explicitly the exact-bound Affinity score, never Candidate Fit.
    enriched["product_overall_quality_score"] = affinity_score
    # Compatibility for the current Control Center: the generic Fit field remains
    # the F4A display Fit preview. Affinity is available only through affinity_*.
    enriched["overall_quality_score"] = enriched["display_fit_score"]
    enriched["combined_score"] = None
    return enriched


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
    source_connector_overview: Mapping[str, Any] | None = None,
    observed_opportunities: Sequence[Mapping[str, Any]] = (),
    profile_fit_preference_tags: Sequence[str] = (),
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
        and _value(job, "affinity_authority_status") == "authoritative"
    )
    origin_blocker_count = sum(
        1
        for job in job_readiness
        if _value(job, "product_readiness_status")
        in {"blocked_origin", "origin_validation_required"}
    )
    lifecycle_contract_ready = not job_readiness or all(
        _value(job, "lifecycle_status") in CURRENT_LIFECYCLE_STATES
        for job in job_readiness
    )
    lifecycle_counts = {
        state: sum(
            1
            for job in job_readiness
            if _value(job, "lifecycle_status") == state
        )
        for state in CURRENT_LIFECYCLE_STATES
    }
    observed_opportunity_count = len(observed_opportunities)
    verified_market_opportunity_count = sum(
        1
        for item in observed_opportunities
        if _value(item, "opportunity_stage") == "vacancy_verified_active"
    )
    pending_market_opportunity_count = sum(
        1
        for item in observed_opportunities
        if _value(item, "opportunity_stage")
        in {
            "employer_candidate_missing",
            "origin_source_required",
            "risk_review",
            "vacancy_verification_pending",
        }
    )
    approved_hashes = {
        str(_value(source, "document_type")): str(_value(source, "content_sha256") or "")
        for source in application_sources
        if _value(source, "status") == "approved"
    }
    f6_authority = authority_status(approved_hashes)
    authority_templates = {
        str(item.get("document_type")): bool(item.get("exact_authority_match"))
        for item in f6_authority["templates"]  # type: ignore[index]
    }
    application_sources_ready = {
        "base_cv": authority_templates.get("base_cv") is True,
        "base_application_letter": authority_templates.get("base_application_letter") is True,
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
    if job_readiness and not lifecycle_contract_ready:
        operator_blockers.append(
            {
                "code": "job_lifecycle_health_required",
                "title": "Job lifecycle health contract required",
                "detail": "Historical Silver presence cannot be treated as current vacancy truth. Apply the reviewed lifecycle migration before Top-5 or application readiness is served.",
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
                "code": "f6_base_cv_template_required",
                "title": "Exact F6 CV template required",
                "detail": "The application assistant remains blocked until the canonical CV PDF matches the frozen F6 hash and geometry.",
            }
        )
    if not application_sources_ready["base_application_letter"]:
        operator_blockers.append(
            {
                "code": "f6_base_application_letter_template_required",
                "title": "Exact F6 application-letter template required",
                "detail": "The application assistant remains blocked until the canonical letter PDF matches the frozen F6 hash and geometry.",
            }
        )

    top_jobs_available = (
        lifecycle_contract_ready
        and policy_status == "approved"
        and (hard_filter_policy is None or hard_policy_status == "approved")
    )
    safe_top_jobs = (
        [
            _display_job(job, profile_fit_preference_tags=profile_fit_preference_tags)
            for job in top_jobs
        ]
        if lifecycle_contract_ready
        else []
    )
    safe_application_readiness = (
        list(application_readiness) if lifecycle_contract_ready else []
    )
    display_job_readiness = [
        _display_job(job, profile_fit_preference_tags=profile_fit_preference_tags)
        for job in job_readiness
    ]
    current_profile_fit_rows = [
        job
        for job in display_job_readiness
        if _value(job, "lifecycle_status") == "active_confirmed"
    ]
    profile_fit_complete_count = sum(
        1
        for job in current_profile_fit_rows
        if _value(job, "profile_fit_coverage_status") == PROFILE_FIT_COMPLETE
    )
    profile_fit_insufficient_evidence_count = sum(
        1
        for job in current_profile_fit_rows
        if _value(job, "profile_fit_coverage_status") == INSUFFICIENT_EVIDENCE
    )
    profile_fit_unclassified_count = (
        len(current_profile_fit_rows)
        - profile_fit_complete_count
        - profile_fit_insufficient_evidence_count
    )
    affinity_authoritative_count = sum(
        1
        for job in display_job_readiness
        if _value(job, "affinity_authority_status") == "authoritative"
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
                "status": "available" if wave_states else "waiting_for_runtime_state",
                "summary": "Bounded company-exclusion waves rotate through a logical cooldown pool without pagination.",
            },
            {
                "id": "top_jobs",
                "title": "Origin-validated Top 5",
                "status": "available" if top_jobs_available else "operator_decision_required",
                "summary": "Only lifecycle-confirmed, origin-validated, hard-filter-passing jobs with exact Affinity authority can enter authoritative ranking.",
            },
            {
                "id": "application_assistant",
                "title": "CV & Application Letter Assistant",
                "status": "ready_for_inputs" if all(application_sources_ready.values()) else "operator_inputs_required",
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
            "observed_opportunity_count": observed_opportunity_count,
            "verified_market_opportunity_count": verified_market_opportunity_count,
            "pending_market_opportunity_count": pending_market_opportunity_count,
            "current_active_job_count": lifecycle_counts["active_confirmed"],
            "affinity_authoritative_count": affinity_authoritative_count,
            "combined_score_count": 0,
            "profile_fit_complete_count": profile_fit_complete_count,
            "profile_fit_insufficient_evidence_count": profile_fit_insufficient_evidence_count,
            "profile_fit_unclassified_count": profile_fit_unclassified_count,
            "stale_job_count": lifecycle_counts["stale_needs_refresh"],
            "inactive_confirmed_job_count": lifecycle_counts["inactive_confirmed"],
            "unverifiable_job_count": lifecycle_counts["unverifiable"],
            "rankable_job_count": rankable_count if lifecycle_contract_ready else 0,
            "origin_blocker_count": origin_blocker_count,
            "top_job_count": len(safe_top_jobs),
            "application_ready_count": sum(
                1
                for item in safe_application_readiness
                if _value(item, "application_readiness_status") == "ready_for_generation"
            ),
        },
        "wave_states": list(wave_states),
        "observed_opportunities": list(observed_opportunities),
        "ranking_policy": policy or {"status": "operator_decision_required"},
        "hard_filter_policy": hard_policy or {"status": "operator_decision_required"},
        "job_readiness": display_job_readiness,
        "top_jobs": safe_top_jobs,
        "application_readiness": safe_application_readiness,
        "application_sources": list(application_sources),
        "application_sources_ready": application_sources_ready,
        "f6_template_authority": f6_authority,
        "source_connector_overview": dict(
            source_connector_overview or empty_source_connector_overview()
        ),
        "operator_blockers": operator_blockers,
        "boundaries": {
            "read_only_api": True,
            "no_provider_call": True,
            "no_automatic_application": True,
            "no_source_activation": True,
            "no_scheduler_mutation": True,
            "aggregator_evidence_is_not_top5_truth": True,
            "manual_market_evidence_is_not_job_truth": True,
            "observed_opportunity_is_not_ranking_authority": True,
            "historical_job_presence_is_not_current_activity": True,
            "current_compensation_is_local_runtime_context_only": True,
            "affinity_is_not_candidate_fit": True,
            "affinity_is_not_combined_score": True,
            "combined_score_authority": False,
            "review_fit_preview_is_not_ranking_authority": True,
            "profile_fit_coverage_is_not_ranking_authority": True,
            "profile_fit_missing_evidence_is_not_negative_fit": True,
        },
    }
    return json_safe(payload)
