"""Candidate expansion from market observations.

This module converts unregistered aggregator novelty evidence into a bounded
candidate-expansion review. It deliberately does not create employer-origin
candidates directly. The output is a reviewable decision layer between market
evidence and `employer_origin_source_candidates`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.normalization.company_keys import company_key_matches, normalize_company_key


DATA_SEARCH_TERMS = {
    "analytics engineer",
    "big data",
    "data engineer",
    "data platform",
    "data warehouse",
    "etl",
    "python sql",
}

NOISE_TITLE_TOKENS = {
    "audit",
    "prüfungsassistent",
    "wirtschaftsprüfer",
    "category manager",
    "labor relations",
    "head of quality",
}


@dataclass(frozen=True)
class MarketCompanyObservation:
    company_key: str
    company_name: str
    source_name: str
    observation_count: int
    latest_observed_at: str | None
    search_terms: tuple[str, ...]
    sample_titles: tuple[str, ...]


@dataclass(frozen=True)
class KnownCandidate:
    candidate_id: int
    company_key: str
    company_name: str
    status: str
    source_family_candidate: str | None = None


@dataclass(frozen=True)
class CandidateExpansionItem:
    company_key: str
    company_name: str
    source_name: str
    decision: str
    priority: int
    evidence_count: int
    distinct_search_term_count: int
    sample_title_count: int
    latest_observed_at: str | None
    known_candidate_id: int | None
    known_candidate_status: str | None
    recommended_next_action: str
    reason: str
    evidence: dict[str, object]


@dataclass(frozen=True)
class CandidateExpansionReview:
    source_name: str | None
    observed_since: str | None
    observed_until: str | None
    total_observation_count: int
    company_count: int
    create_recommended_count: int
    manual_review_count: int
    insufficient_evidence_count: int
    already_known_count: int
    suppressed_count: int
    items: tuple[CandidateExpansionItem, ...]
    boundary: dict[str, object]


def _candidate_keys(candidate: KnownCandidate) -> tuple[str, ...]:
    raw_values = [candidate.company_key, candidate.company_name]
    if candidate.source_family_candidate:
        raw_values.append(candidate.source_family_candidate)
    return tuple(key for key in (normalize_company_key(value) for value in raw_values) if key)


def find_known_candidate(
    company_key: str,
    candidates: Iterable[KnownCandidate],
) -> KnownCandidate | None:
    normalized = normalize_company_key(company_key)
    if not normalized:
        return None
    for candidate in candidates:
        for candidate_key in _candidate_keys(candidate):
            if company_key_matches(normalized, candidate_key):
                return candidate
    return None


def _lower_terms(values: Iterable[str]) -> set[str]:
    return {value.strip().lower() for value in values if value and value.strip()}


def _looks_noisy_only(titles: Iterable[str]) -> bool:
    title_list = [title.lower() for title in titles if title]
    if not title_list:
        return False
    return all(any(token in title for token in NOISE_TITLE_TOKENS) for title in title_list)


def _score_priority(
    *,
    evidence_count: int,
    distinct_search_term_count: int,
    data_term_count: int,
    sample_title_count: int,
) -> int:
    return (
        evidence_count * 10
        + distinct_search_term_count * 6
        + data_term_count * 8
        + min(sample_title_count, 5) * 2
    )


def _has_service_provider_source_role_risk(company_key: str, company_name: str) -> bool:
    """Return true for likely consulting/service-provider source-role ambiguity.

    These companies can be valid employers, but direct employer-origin candidate
    creation should pause for source-role review when the signal is broad or
    consulting/service-provider-like.
    """
    haystack = f"{company_key} {company_name}".lower()
    risk_terms = {
        "business_solutions",
        "business solutions",
        "consulting",
        "consultancy",
        "services",
        "service_provider",
        "service provider",
        "solutions",
    }
    return any(term in haystack for term in risk_terms)


def _has_related_company_group_risk(company_key: str, known_candidate_keys: Iterable[str] = ()) -> bool:
    """Return true when a candidate may be covered by a related company/group source.

    This is intentionally conservative. It does not classify the company as noise;
    it only prevents blind creation of multiple connector candidates that may share
    one origin career platform.
    """
    normalized = normalize_company_key(company_key) or company_key
    known = {normalize_company_key(key) or key for key in known_candidate_keys}
    if normalized == "adesso_business_consulting":
        return "adesso" in known or True
    return False


def _has_intermediary_source_role_risk(company_key: str, company_name: str) -> bool:
    """Return true for likely market intermediaries, recruiters or staffing providers.

    These sources may still be useful as market evidence, but they should not be
    promoted directly as employer-origin candidates without explicit review.
    """
    haystack = f"{company_key} {company_name}".lower()
    risk_terms = {
        "computer_futures",
        "amadeus_fire",
        "personalvermittlung",
        "recruiting",
        "recruitment",
        "staffing",
        "workforce",
        "talent",
        "headhunter",
        "vermittlung",
        "zeitarbeit",
    }
    return any(term in haystack for term in risk_terms)


def _has_relevant_title_signal(titles: Iterable[str]) -> bool:
    relevant_terms = {
        "data",
        "daten",
        "engineer",
        "analytics",
        "analyst",
        "cloud",
        "platform",
        "devops",
        "ml",
        "ki",
        "ai",
        "bi",
        "database",
        "etl",
        "software",
        "developer",
        "entwickler",
        "architect",
        "architekt",
        "fullstack",
        "backend",
        "frontend",
    }
    haystack = " ".join(titles).lower()
    return any(term in haystack for term in relevant_terms)


def decide_candidate_expansion_item(
    observation: MarketCompanyObservation,
    known_candidates: Iterable[KnownCandidate],
    *,
    min_create_observations: int = 4,
    min_review_observations: int = 2,
) -> CandidateExpansionItem:
    normalized_key = normalize_company_key(observation.company_key) or observation.company_key
    terms = _lower_terms(observation.search_terms)
    data_terms = terms.intersection(DATA_SEARCH_TERMS)
    titles = tuple(title for title in observation.sample_titles if title)
    known_candidate = find_known_candidate(normalized_key, known_candidates)

    evidence_count = int(observation.observation_count)
    distinct_term_count = len(terms)
    sample_title_count = len(set(titles))
    priority = _score_priority(
        evidence_count=evidence_count,
        distinct_search_term_count=distinct_term_count,
        data_term_count=len(data_terms),
        sample_title_count=sample_title_count,
    )

    if known_candidate and known_candidate.status == "active_controlled":
        decision = "active_candidate_monitoring"
        next_action = "Monitor existing controlled source; do not create duplicate candidate"
        reason = "company is already backed by an active controlled employer-origin candidate"
    elif known_candidate:
        decision = "already_known"
        next_action = "Route evidence to existing candidate lifecycle instead of creating a duplicate"
        reason = "company already exists as employer-origin candidate"
    elif (
        evidence_count >= min_create_observations
        and data_terms
        and not _looks_noisy_only(titles)
        and _has_intermediary_source_role_risk(normalized_key, observation.company_name)
    ):
        decision = "manual_review_required"
        next_action = "Review source role before candidate creation; this may be a recruiter, staffing provider or intermediary source"
        reason = "repeated market observations found, but source-role risk prevents direct employer-origin candidate recommendation"
    elif (
        evidence_count >= min_create_observations
        and data_terms
        and not _looks_noisy_only(titles)
        and _has_service_provider_source_role_risk(normalized_key, observation.company_name)
    ):
        decision = "manual_review_required"
        next_action = "Review source role before candidate creation; this may be a consulting, service-provider or solutions-provider source"
        reason = "repeated market observations found, but service-provider source-role ambiguity prevents direct employer-origin candidate recommendation"
    elif (
        evidence_count >= min_create_observations
        and data_terms
        and not _looks_noisy_only(titles)
        and _has_related_company_group_risk(normalized_key, {candidate.company_key for candidate in known_candidates})
    ):
        decision = "manual_review_required"
        next_action = "Review whether this company is covered by a related group/company career source before creating a separate candidate"
        reason = "possible related company/group candidate; avoid duplicate connector candidates before origin-source review"
    elif evidence_count >= min_create_observations and data_terms and not _looks_noisy_only(titles):
        decision = "create_candidate_recommended"
        next_action = "Review candidate creation, then run Origin Source Discovery Gate"
        reason = "repeated unregistered market observations with data-related search-term evidence"
    elif evidence_count >= min_review_observations and data_terms:
        decision = "manual_review_required"
        next_action = "Review whether evidence is employer-origin relevant before candidate creation"
        reason = "some relevant data/search evidence exists but not enough for direct candidate recommendation"
    elif _looks_noisy_only(titles) or not _has_relevant_title_signal(titles):
        decision = "suppress_as_noise"
        next_action = "Keep as market noise unless future observations add stronger data/job evidence"
        reason = "sample titles look unrelated to the target data/engineering scope"
    else:
        decision = "insufficient_evidence"
        next_action = "Wait for more observations or richer vocabulary before candidate creation"
        reason = "isolated but title-relevant evidence needs more observations before candidate expansion"

    return CandidateExpansionItem(
        company_key=normalized_key,
        company_name=observation.company_name,
        source_name=observation.source_name,
        decision=decision,
        priority=priority,
        evidence_count=evidence_count,
        distinct_search_term_count=distinct_term_count,
        sample_title_count=sample_title_count,
        latest_observed_at=observation.latest_observed_at,
        known_candidate_id=known_candidate.candidate_id if known_candidate else None,
        known_candidate_status=known_candidate.status if known_candidate else None,
        recommended_next_action=next_action,
        reason=reason,
        evidence={
            "search_terms": sorted(terms),
            "data_search_terms": sorted(data_terms),
            "sample_titles": sorted(set(titles))[:10],
            "source_name": observation.source_name,
        },
    )


def build_candidate_expansion_review(
    observations: Iterable[MarketCompanyObservation],
    known_candidates: Iterable[KnownCandidate],
    *,
    source_name: str | None = None,
    observed_since: str | None = None,
    observed_until: str | None = None,
    min_create_observations: int = 4,
    min_review_observations: int = 2,
) -> CandidateExpansionReview:
    observation_list = list(observations)
    candidate_list = list(known_candidates)
    items = tuple(
        sorted(
            (
                decide_candidate_expansion_item(
                    observation,
                    candidate_list,
                    min_create_observations=min_create_observations,
                    min_review_observations=min_review_observations,
                )
                for observation in observation_list
            ),
            key=lambda item: (
                {
                    "create_candidate_recommended": 1,
                    "manual_review_required": 2,
                    "already_known": 3,
                    "active_candidate_monitoring": 4,
                    "insufficient_evidence": 5,
                    "suppress_as_noise": 6,
                }.get(item.decision, 9),
                -item.priority,
                item.company_name.lower(),
            ),
        )
    )

    def count(decision: str) -> int:
        return sum(1 for item in items if item.decision == decision)

    return CandidateExpansionReview(
        source_name=source_name,
        observed_since=observed_since,
        observed_until=observed_until,
        total_observation_count=sum(item.evidence_count for item in items),
        company_count=len(items),
        create_recommended_count=count("create_candidate_recommended"),
        manual_review_count=count("manual_review_required"),
        insufficient_evidence_count=count("insufficient_evidence"),
        already_known_count=count("already_known") + count("active_candidate_monitoring"),
        suppressed_count=count("suppress_as_noise"),
        items=items,
        boundary={
            "external_browsing_allowed": False,
            "candidate_creation_allowed": False,
            "connector_registration_allowed": False,
            "source_activation_allowed": False,
            "bronze_persistence_allowed": False,
            "scheduler_change_allowed": False,
            "csv_or_export_inputs_used": False,
            "min_create_observations": min_create_observations,
            "min_review_observations": min_review_observations,
        },
    )
