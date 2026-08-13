"""Greenhouse-only delegated fallback for employer-origin Detail Evidence repair.

The ordinary employer-origin repair remains authoritative and runs first without
modification.  Only when it produces no supported detail does this wrapper:

1. refetch the persisted employer page and require a concrete first-party
   Greenhouse board reference;
2. prove board identity through the reviewed Greenhouse authority contract;
3. select at most two board jobs with listing-level profile + target/location
   signals; and
4. feed those concrete job URLs through the existing
   ``validate_detail_candidates`` implementation.

No generic cross-domain or ATS-host trust is introduced.  This module does not
write database state; callers receive a normal ``RepairOutcome`` and existing
controlled writers remain the only persistence boundary.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import scripts.run_employer_origin_detail_evidence_repair_agent as base
from src.search_intelligence.greenhouse_delegated_detail_contract import (
    GREENHOUSE_AUTHORITY_CONTRACT_VERSION,
    JsonFetcher,
    extract_greenhouse_reference_hosts,
    fetch_greenhouse_json,
    resolve_greenhouse_delegation,
)


MAX_GREENHOUSE_DELEGATED_DETAIL_PAGES = 2


def _outcome_with_evidence(
    outcome: base.RepairOutcome,
    *,
    evidence: dict[str, Any],
    requested_urls: tuple[str, ...] | None = None,
    rejected_urls: tuple[str, ...] | None = None,
    gate_status: str | None = None,
    decision: str | None = None,
    stop_reason: str | None | object = ...,
    details: tuple[base.DetailEvidence, ...] | None = None,
) -> base.RepairOutcome:
    resolved_stop_reason = outcome.stop_reason if stop_reason is ... else stop_reason
    return base.RepairOutcome(
        gate_status=gate_status or outcome.gate_status,
        decision=decision or outcome.decision,
        stop_reason=resolved_stop_reason,
        details=outcome.details if details is None else details,
        rejected_urls=outcome.rejected_urls if rejected_urls is None else rejected_urls,
        requested_urls=outcome.requested_urls if requested_urls is None else requested_urls,
        evidence=evidence,
    )


def _fresh_employer_greenhouse_hosts(
    *,
    candidate: base.SourceCandidate,
    fetcher,
) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, Any]]:
    requested: list[str] = []
    evidence: dict[str, Any] = {
        "fresh_employer_page_requested": True,
        "fresh_employer_page_raw_html_persisted": False,
    }
    try:
        html, final_url, status_code = fetcher(candidate.candidate_url)
    except Exception as exc:  # noqa: BLE001 - delegated fallback must fail closed.
        evidence.update(
            {
                "fresh_employer_page_status": "fetch_failed",
                "fresh_employer_page_error": type(exc).__name__,
            }
        )
        return (), (), evidence

    requested.append(final_url)
    evidence.update(
        {
            "fresh_employer_page_status_code": status_code,
            "fresh_employer_page_final_host": base.urlparse(final_url).netloc.casefold(),
        }
    )
    if status_code >= 400:
        evidence["fresh_employer_page_status"] = "not_reachable"
        return (), tuple(requested), evidence
    if not base.same_base_domain(final_url, candidate.candidate_url):
        evidence["fresh_employer_page_status"] = "cross_domain_redirect_refused"
        return (), tuple(requested), evidence

    hosts = extract_greenhouse_reference_hosts(html, final_url)
    evidence.update(
        {
            "fresh_employer_page_status": "ok",
            "fresh_greenhouse_reference_hosts": list(hosts),
        }
    )
    return hosts, tuple(requested), evidence


def _eligible_greenhouse_links(
    *,
    candidate: base.SourceCandidate,
    jobs,
    board_jobs_url: str,
    profile_terms: tuple[str, ...],
    location_terms: tuple[str, ...],
    limit: int,
) -> tuple[base.LinkCandidate, ...]:
    links: list[base.LinkCandidate] = []
    for job in jobs:
        listing_blob = " ".join((job.absolute_url, job.title, job.location))
        matched_profile = base.find_terms(listing_blob, profile_terms)
        matched_location = base.filter_target_location_terms(
            candidate=candidate,
            url=job.absolute_url,
            title=job.title,
            text=job.location,
            terms=location_terms,
        )
        if not matched_profile or not matched_location:
            continue
        links.append(
            base.LinkCandidate(
                url=job.absolute_url,
                source_url=board_jobs_url,
                text=base.normalize_whitespace(" ".join((job.title, job.location))),
                profile_terms=matched_profile,
                location_terms=matched_location,
                reason=(
                    "Concrete Greenhouse job returned by an employer-page-backed, "
                    "first-party board whose organization identity matches the "
                    "canonical employer token."
                ),
            )
        )
        if len(links) >= limit:
            break
    return tuple(links)


def build_greenhouse_delegated_repair_outcome(
    *,
    candidate: base.SourceCandidate,
    gates: dict[str, dict[str, Any]],
    profile_terms: tuple[str, ...],
    location_terms: tuple[str, ...],
    max_seed_pages: int,
    max_detail_pages: int,
    enable_search_discovery: bool = True,
    max_search_queries: int = base.DEFAULT_SEARCH_QUERY_LIMIT,
    max_search_results: int = base.DEFAULT_SEARCH_RESULT_LIMIT,
    search_provider: str = base.DEFAULT_SEARCH_PROVIDER,
    fetcher=base.fetch_url,
    search_fetcher=base.fetch_search_results,
    tavily_fetcher=base.fetch_tavily_search_results,
    greenhouse_json_fetcher: JsonFetcher = fetch_greenhouse_json,
    max_greenhouse_detail_pages: int = MAX_GREENHOUSE_DELEGATED_DETAIL_PAGES,
) -> base.RepairOutcome:
    """Run ordinary repair, then a bounded Greenhouse-only delegated fallback."""

    ordinary = base.build_repair_outcome(
        candidate=candidate,
        gates=gates,
        profile_terms=profile_terms,
        location_terms=location_terms,
        max_seed_pages=max_seed_pages,
        max_detail_pages=max_detail_pages,
        enable_search_discovery=enable_search_discovery,
        max_search_queries=max_search_queries,
        max_search_results=max_search_results,
        search_provider=search_provider,
        fetcher=fetcher,
        search_fetcher=search_fetcher,
        tavily_fetcher=tavily_fetcher,
    )
    if ordinary.details:
        return ordinary

    evidence = dict(ordinary.evidence)
    delegated_evidence: dict[str, Any] = {
        "contract_version": GREENHOUSE_AUTHORITY_CONTRACT_VERSION,
        "fallback_attempted_after_ordinary_supported_detail": False,
        "ordinary_supported_detail_count": 0,
        "max_delegated_detail_pages": max(0, min(max_greenhouse_detail_pages, MAX_GREENHOUSE_DELEGATED_DETAIL_PAGES)),
        "database_writes": False,
        "connector_activation": False,
        "generic_ats_delegation_enabled": False,
    }
    evidence["greenhouse_delegation"] = delegated_evidence

    detail_limit = max(0, min(max_greenhouse_detail_pages, MAX_GREENHOUSE_DELEGATED_DETAIL_PAGES))
    if detail_limit == 0:
        delegated_evidence["status"] = "delegated_detail_budget_zero"
        return _outcome_with_evidence(ordinary, evidence=evidence)

    reference_hosts, fresh_requests, fresh_evidence = _fresh_employer_greenhouse_hosts(
        candidate=candidate,
        fetcher=fetcher,
    )
    delegated_evidence.update(fresh_evidence)
    requested_urls = base.unique_ordered([*ordinary.requested_urls, *fresh_requests])
    if not reference_hosts:
        delegated_evidence["status"] = "missing_fresh_employer_greenhouse_reference"
        return _outcome_with_evidence(
            ordinary,
            evidence=evidence,
            requested_urls=requested_urls,
        )

    resolution = resolve_greenhouse_delegation(
        company_key=candidate.company_key,
        company_name=candidate.company_name,
        fresh_reference_hosts=reference_hosts,
        json_fetcher=greenhouse_json_fetcher,
    )
    delegated_evidence.update(resolution.evidence)
    delegated_evidence.update(
        {
            "status": resolution.status,
            "attempted": resolution.attempted,
            "authorized": resolution.authorized,
            "board_name": resolution.board_name,
        }
    )
    if not resolution.authorized or not resolution.board_jobs_url:
        return _outcome_with_evidence(
            ordinary,
            evidence=evidence,
            requested_urls=requested_urls,
        )

    links = _eligible_greenhouse_links(
        candidate=candidate,
        jobs=resolution.jobs,
        board_jobs_url=resolution.board_jobs_url,
        profile_terms=profile_terms,
        location_terms=location_terms,
        limit=detail_limit,
    )
    delegated_evidence["profile_location_candidate_count"] = len(links)
    delegated_evidence["selected_candidates"] = [
        base.link_candidate_to_report_dict(link) for link in links
    ]
    if not links:
        delegated_evidence["status"] = "board_authorized_no_current_profile_location_match"
        return _outcome_with_evidence(
            ordinary,
            evidence=evidence,
            requested_urls=requested_urls,
            stop_reason=(
                "Greenhouse board delegation is authorized, but no current board job "
                "matches both profile and target/location signals."
            ),
        )

    # The existing validator deliberately rejects cross-domain details relative
    # to the employer page.  Once Greenhouse board identity has been proven, use
    # that exact first-party board as the validation reference.  The same
    # classify_checked_url + profile/location contract remains unchanged.
    delegated_candidate = replace(candidate, candidate_url=resolution.board_jobs_url)
    delegated_details, delegated_rejections, delegated_requests, delegated_assessments = base.validate_detail_candidates(
        candidate=delegated_candidate,
        link_candidates=links,
        profile_terms=profile_terms,
        location_terms=location_terms,
        max_detail_pages=detail_limit,
        fetcher=fetcher,
    )
    requested_urls = base.unique_ordered([*requested_urls, *delegated_requests])
    rejected_urls = base.unique_ordered([*ordinary.rejected_urls, *delegated_rejections])
    delegated_evidence["detail_assessments"] = list(delegated_assessments)
    delegated_evidence["supported_detail_count"] = len(delegated_details)

    preliminary = [
        *(ordinary.evidence.get("preliminary_detail_candidates") or []),
        *[base.link_candidate_to_report_dict(link) for link in links],
    ]
    assessments = [
        *(ordinary.evidence.get("authoritative_detail_assessments") or []),
        *list(delegated_assessments),
    ]
    supported = [base.detail_evidence_to_report_dict(detail) for detail in delegated_details]
    evidence.update(
        {
            "preliminary_detail_candidates": preliminary,
            "authoritative_detail_assessments": assessments,
            "supported_detail_evidence": supported,
            "candidate_links": preliminary,
            "detail_assessments": assessments,
            "details": supported,
            "supported_details": supported,
            "requested_urls": list(requested_urls),
            "rejected_urls": list(rejected_urls),
        }
    )

    if delegated_details:
        delegated_evidence["status"] = "delegation_proven_detail_supported"
        evidence.update(
            {
                "decision_taxonomy": base.EvidenceDecision.ACCEPTED.value,
                "confidence_score": 0.96,
                "confidence_reason": (
                    "first-party Greenhouse board identity is proven and the delegated "
                    "concrete detail passed the existing profile/target validation contract"
                ),
            }
        )
        return _outcome_with_evidence(
            ordinary,
            evidence=evidence,
            requested_urls=requested_urls,
            rejected_urls=rejected_urls,
            gate_status="passed",
            decision="passed",
            stop_reason=None,
            details=delegated_details,
        )

    delegated_evidence["status"] = "delegated_concrete_detail_not_supported"
    evidence.update(
        {
            "decision_taxonomy": base.EvidenceDecision.IMPLEMENTATION_GAP.value,
            "confidence_score": 0.82,
            "confidence_reason": (
                "Greenhouse delegation and concrete board jobs were authorized, but the "
                "existing detail validator did not support any selected detail"
            ),
        }
    )
    return _outcome_with_evidence(
        ordinary,
        evidence=evidence,
        requested_urls=requested_urls,
        rejected_urls=rejected_urls,
        stop_reason=(
            "Greenhouse delegation is authorized and concrete detail candidates exist, "
            "but none passed the existing Detail Evidence profile/target contract."
        ),
    )
