"""Entity, source-grade, inventory and target-signal classification."""

from __future__ import annotations

from typing import Sequence
from urllib.parse import urlparse

from src.search_intelligence.origin_source_discovery import is_known_aggregator_domain
from src.search_intelligence.origin_source_discovery_agent import (
    ascii_fold,
    is_known_ats_provider_domain,
)
from src.search_intelligence.origin_source_evidence_extract import (
    _is_job_detail_url,
    _normalized_host,
    normalize_org_name,
    is_social_host,
)
from src.search_intelligence.origin_source_evidence_models import (
    CAREER_TERMS,
    EMPTY_INVENTORY_PHRASES,
    LISTING_PATH_MARKERS,
    ArtifactCandidate,
    LinkEvidence,
    PageEvidence,
)

def _entity_fidelity(
    *,
    candidate: ArtifactCandidate,
    company_key: str,
    company_name: str,
    page: PageEvidence,
    identity_score: float,
) -> tuple[str, tuple[str, ...]]:
    context = " ".join(
        value
        for value in (candidate.title, candidate.snippet, page.title, page.text[:25_000])
        if value
    )
    target = normalize_org_name(company_name)
    context_normalized = normalize_org_name(context)
    target_tokens = set(target.split())
    context_tokens = set(context_normalized.split())
    overlap = target_tokens & context_tokens
    reasons: list[str] = []

    if target and target in context_normalized:
        return "exact_legal_entity", ("normalized company name appears in page/search evidence",)

    distinctive_target = {
        token for token in target_tokens if token not in {"group", "holding", "international"}
    }
    distinctive_overlap = distinctive_target & context_tokens
    short_brand_only = (
        len(distinctive_target) >= 2
        and len(distinctive_overlap) == 1
        and len(next(iter(distinctive_overlap), "")) <= 4
    )
    conflicting_descriptors = {
        token
        for token in context_tokens - target_tokens
        if token in {"consulting", "digital", "services", "solutions", "systems", "technology"}
    }
    if short_brand_only and conflicting_descriptors:
        return (
            "ambiguous",
            (
                "only a short brand token matches while entity descriptors differ",
                "conflicting descriptors: " + ", ".join(sorted(conflicting_descriptors)),
            ),
        )

    if identity_score >= 0.75 and len(distinctive_overlap) >= 2:
        return "brand_match", ("multiple distinctive company tokens match",)
    if identity_score >= 0.60 and (
        "group" in context_tokens or "holding" in context_tokens
    ):
        return "parent_group_match", ("company brand matches a group/holding context",)
    if identity_score >= 0.45 and overlap:
        reasons.append("partial company identity match")
        return "related_entity", tuple(reasons)
    if identity_score >= 0.45:
        return "ambiguous", ("URL identity is plausible but page entity evidence is weak",)
    return "unknown", ("no reliable entity relationship was observed",)


def _source_grade(
    *,
    url: str,
    page: PageEvidence,
    job_links: Sequence[LinkEvidence],
    ats_family: str | None,
) -> tuple[str, str]:
    host = _normalized_host(urlparse(url).hostname)
    path = urlparse(url).path.lower()
    folded = ascii_fold(f"{page.title} {page.text[:40_000]}")
    if is_known_aggregator_domain(host):
        return "aggregator", "known aggregator domain"
    if is_social_host(host):
        return "social_profile", "social-network domain"
    if page.json_ld_jobposting_count and _is_job_detail_url(url):
        return "job_detail", "JobPosting schema on a detail-shaped URL"
    if _is_job_detail_url(url) and not job_links:
        return "job_detail", "detail-shaped URL"
    if ats_family and (
        job_links
        or any(marker in path for marker in LISTING_PATH_MARKERS)
        or "search jobs" in folded
        or "stellen suchen" in folded
        or any(ascii_fold(phrase) in folded for phrase in EMPTY_INVENTORY_PHRASES)
        or is_known_ats_provider_domain(host)
    ):
        return "ats_job_listing", "ATS markers and listing/job evidence"
    if job_links or page.json_ld_jobposting_count >= 1:
        return "company_job_listing", "multiple concrete job records or links observed"
    if any(term in folded for term in CAREER_TERMS) or any(
        marker in path for marker in LISTING_PATH_MARKERS
    ):
        return "career_landing", "career terms observed without concrete job inventory"
    if page.reachable:
        return "corporate_page", "reachable page without job-board structure"
    return "unknown", "page evidence unavailable"


def _job_inventory_state(
    *,
    page: PageEvidence,
    source_grade: str,
    job_links: Sequence[LinkEvidence],
) -> tuple[str, str]:
    if page.failure_class or not page.reachable:
        return "fetch_failed", page.failure_class or "page_not_reachable"
    observed = len(job_links) + page.json_ld_jobposting_count
    if observed:
        return "job_bearing_proven", "concrete job URLs or JobPosting records observed"
    folded = ascii_fold(page.text[:80_000])
    if any(ascii_fold(phrase) in folded for phrase in EMPTY_INVENTORY_PHRASES):
        return "job_bearing_currently_empty", "page explicitly reports no current openings"
    if source_grade in {"ats_job_listing", "company_job_listing"}:
        return "job_bearing_unknown", "listing structure observed but no concrete job record extracted"
    if source_grade == "career_landing":
        return "job_bearing_unknown", "career landing page without concrete inventory proof"
    return "not_job_bearing", "no job-board or job-detail evidence observed"


def _target_signal_count(
    links: Sequence[LinkEvidence],
    *,
    target_location: str,
    target_terms: Sequence[str],
) -> int:
    normalized_terms = tuple(ascii_fold(item) for item in target_terms if item)
    location = ascii_fold(target_location)
    count = 0
    for item in links:
        haystack = ascii_fold(f"{item.text} {item.url}")
        profile_hit = any(term in haystack for term in normalized_terms)
        location_hit = bool(location and location in haystack)
        remote_hit = any(term in haystack for term in ("remote", "homeoffice", "hybrid"))
        if profile_hit and (location_hit or remote_hit or not location):
            count += 1
    return count
