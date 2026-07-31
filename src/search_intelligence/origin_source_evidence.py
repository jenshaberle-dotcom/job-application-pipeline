"""Deterministic evidence grading for employer origin-source candidates.

The provider benchmark discovers plausible URLs. This module combines independently
measured entity fidelity, source grade, job inventory, locale and target signals.
LLM output is never treated as source truth.
"""

from __future__ import annotations

from typing import Sequence

from src.search_intelligence.origin_source_discovery_agent import (
    company_identity_score,
    normalize_candidate_url,
)
from src.search_intelligence.origin_source_evidence_classify import (
    _entity_fidelity,
    _job_inventory_state,
    _source_grade,
    _target_signal_count,
)
from src.search_intelligence.origin_source_evidence_extract import (
    _ats_family,
    detect_locale,
    extract_job_links,
    failed_page_evidence,
    page_evidence_from_html,
    resolves_to_public_addresses,
    validate_public_https_url,
)
from src.search_intelligence.origin_source_evidence_models import (
    DEFAULT_TARGET_TERMS,
    ENTITY_FIDELITY_SCORES,
    JOB_INVENTORY_SCORES,
    SOURCE_GRADE_SCORES,
    ArtifactCandidate,
    LinkEvidence,
    OriginEvidenceAssessment,
    OriginEvidenceDecision,
    PageEvidence,
)

__all__ = [
    "ArtifactCandidate",
    "LinkEvidence",
    "OriginEvidenceAssessment",
    "OriginEvidenceDecision",
    "PageEvidence",
    "assess_origin_evidence_candidate",
    "decide_origin_evidence",
    "failed_page_evidence",
    "page_evidence_from_html",
    "resolves_to_public_addresses",
    "should_request_llm_adjudication",
    "validate_public_https_url",
]

def assess_origin_evidence_candidate(
    *,
    candidate_id: str,
    candidate: ArtifactCandidate,
    company_key: str,
    company_name: str,
    page: PageEvidence,
    target_location: str,
    target_locale: str = "de",
    target_terms: Sequence[str] = DEFAULT_TARGET_TERMS,
) -> OriginEvidenceAssessment:
    final_url = normalize_candidate_url(page.final_url or candidate.url) or candidate.url
    identity_score, identity_reasons = company_identity_score(
        url=final_url,
        company_key=company_key,
        company_name=company_name,
    )
    identity_score = max(identity_score, candidate.prior_identity_score)
    job_links = extract_job_links(page)
    ats_family = _ats_family(final_url, page)
    source_grade, source_reason = _source_grade(
        url=final_url,
        page=page,
        job_links=job_links,
        ats_family=ats_family,
    )
    fidelity, fidelity_reasons = _entity_fidelity(
        candidate=candidate,
        company_key=company_key,
        company_name=company_name,
        page=page,
        identity_score=identity_score,
    )
    inventory, inventory_reason = _job_inventory_state(
        page=page,
        source_grade=source_grade,
        job_links=job_links,
    )
    locale = detect_locale(page, final_url)
    locale_score = 1.0 if locale == target_locale else 0.50 if locale == "neutral" else 0.25
    target_count = _target_signal_count(
        job_links,
        target_location=target_location,
        target_terms=target_terms,
    )
    target_score = min(target_count / 3.0, 1.0)
    completeness_checks = (
        page.reachable,
        source_grade not in {"unknown", "corporate_page"},
        fidelity != "unknown",
        inventory not in {"job_bearing_unknown", "fetch_failed"},
        bool(page.title or candidate.title),
    )
    completeness = round(sum(bool(item) for item in completeness_checks) / len(completeness_checks), 3)
    source_score = SOURCE_GRADE_SCORES[source_grade]
    entity_score = ENTITY_FIDELITY_SCORES[fidelity]
    job_score = JOB_INVENTORY_SCORES[inventory]
    ranking = round(
        0.32 * entity_score
        + 0.28 * source_score
        + 0.25 * job_score
        + 0.07 * locale_score
        + 0.08 * target_score,
        4,
    )
    reasons = tuple(
        dict.fromkeys(
            [
                *identity_reasons,
                *fidelity_reasons,
                source_reason,
                inventory_reason,
                f"locale={locale}",
                f"target_signal_job_count={target_count}",
            ]
        )
    )
    observed_job_count = len(job_links) + page.json_ld_jobposting_count
    page_type = {
        "ats_job_listing": "job_listing",
        "company_job_listing": "job_listing",
        "career_landing": "career_landing",
        "job_detail": "job_detail",
        "corporate_page": "corporate_page",
    }.get(source_grade, "unknown")
    return OriginEvidenceAssessment(
        candidate_id=candidate_id,
        url=candidate.url,
        final_url=final_url,
        provider=candidate.provider,
        source_grade=source_grade,
        entity_fidelity=fidelity,
        job_inventory_state=inventory,
        page_type=page_type,
        ats_family=ats_family,
        http_status=page.status_code,
        reachable=page.reachable,
        locale=locale,
        observed_job_count=observed_job_count,
        target_signal_job_count=target_count,
        sample_job_urls=tuple(item.url for item in job_links[:5]),
        identity_score=round(identity_score, 3),
        source_grade_score=source_score,
        entity_fidelity_score=entity_score,
        job_bearing_score=job_score,
        locale_preference_score=locale_score,
        target_relevance_score=round(target_score, 3),
        evidence_completeness=completeness,
        ranking_score=ranking,
        reasons=reasons,
        failure_class=page.failure_class,
    )


def decide_origin_evidence(
    *,
    company_key: str,
    company_name: str,
    assessments: Sequence[OriginEvidenceAssessment],
) -> OriginEvidenceDecision:
    ordered = tuple(
        sorted(
            assessments,
            key=lambda item: (
                -item.ranking_score,
                -item.evidence_completeness,
                item.final_url,
            ),
        )
    )
    if not ordered:
        return OriginEvidenceDecision(
            company_key=company_key,
            company_name=company_name,
            deterministic_decision="not_found",
            selected_candidate_id=None,
            selected_url=None,
            confidence_score=0.0,
            confidence_band="unknown",
            selection_margin=0.0,
            manual_review_required=True,
            adjudication_reasons=("no evidence candidates available",),
            assessments=(),
        )

    winner = ordered[0]
    runner_score = ordered[1].ranking_score if len(ordered) > 1 else 0.0
    margin = round(max(0.0, winner.ranking_score - runner_score), 4)
    normalized_margin = min(margin / 0.20, 1.0)
    confidence = round(
        min(
            0.95,
            0.25
            + 0.45 * winner.ranking_score
            + 0.20 * normalized_margin
            + 0.10 * winner.evidence_completeness,
        ),
        3,
    )

    reasons: list[str] = []
    select_grade = winner.source_grade in {"ats_job_listing", "company_job_listing"}
    select_entity = winner.entity_fidelity in {
        "exact_legal_entity",
        "brand_match",
        "parent_group_match",
    }
    select_inventory = winner.job_inventory_state in {
        "job_bearing_proven",
        "job_bearing_currently_empty",
    }
    auto_select = (
        winner.ranking_score >= 0.65
        and margin >= 0.05
        and select_grade
        and select_entity
        and select_inventory
    )

    if winner.entity_fidelity == "ambiguous":
        reasons.append("entity_ambiguity")
    if margin < 0.05 and len(ordered) > 1:
        reasons.append("low_winner_margin")
    if winner.job_inventory_state == "job_bearing_unknown":
        reasons.append("job_inventory_unknown")
    if winner.job_inventory_state == "fetch_failed":
        reasons.append("winner_fetch_failed")
    if winner.source_grade == "career_landing":
        reasons.append("career_landing_without_job_listing_proof")
    if not select_entity:
        reasons.append("entity_fidelity_below_auto_select")
    if not select_grade:
        reasons.append("source_grade_below_auto_select")
    if not select_inventory:
        reasons.append("job_inventory_below_auto_select")

    if auto_select:
        decision = "origin_url_candidate_selected"
        manual = False
        if confidence >= 0.82 and winner.job_inventory_state == "job_bearing_proven":
            band = "high"
        else:
            band = "medium"
    elif winner.ranking_score >= 0.45:
        decision = "manual_review_required"
        manual = True
        band = "low" if confidence < 0.70 else "medium"
    else:
        decision = "not_found"
        manual = True
        band = "unknown"
        reasons.append("no_candidate_meets_minimum_evidence_grade")

    return OriginEvidenceDecision(
        company_key=company_key,
        company_name=company_name,
        deterministic_decision=decision,
        selected_candidate_id=winner.candidate_id if auto_select else None,
        selected_url=winner.final_url if auto_select else None,
        confidence_score=confidence,
        confidence_band=band,
        selection_margin=margin,
        manual_review_required=manual,
        adjudication_reasons=tuple(dict.fromkeys(reasons)),
        assessments=ordered,
    )


def should_request_llm_adjudication(decision: OriginEvidenceDecision) -> bool:
    if not decision.assessments:
        return False
    if decision.deterministic_decision == "origin_url_candidate_selected":
        return False
    supported_reasons = {
        "career_landing_without_job_listing_proof",
        "entity_ambiguity",
        "entity_fidelity_below_auto_select",
        "job_inventory_unknown",
        "low_winner_margin",
        "source_grade_below_auto_select",
        "winner_fetch_failed",
    }
    return bool(supported_reasons & set(decision.adjudication_reasons))
