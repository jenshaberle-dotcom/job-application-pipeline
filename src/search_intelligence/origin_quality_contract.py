"""Install hard quality gates for employer-origin URL discovery.

The finder must identify a reusable employer career or job-list source. A page is
not an origin source merely because search-result text mentions the employer and
careers. This contract therefore closes the false-positive classes observed in
the second database-wide audit:

- malformed generated hostnames must fail closed before HTTP;
- third-party company profiles may provide evidence but cannot become origins;
- generic company homepages are not automatically promoted from body text;
- single job-detail pages are evidence and may yield a portal-root hypothesis;
- short acronyms require stronger identity evidence than an acronym collision.

The contract is installed before the staged runtime imports the discovery agent.
It preserves all existing scores and thresholds, then narrows automatic selection.
"""

from __future__ import annotations

from dataclasses import replace
import re
from typing import Mapping, Sequence
from urllib.parse import urlparse

import src.search_intelligence.origin_source_discovery_agent as origin_agent

_INSTALL_MARKER = "_origin_quality_contract_installed"
_ORIGINAL_NORMALIZE = "_origin_quality_original_normalize_candidate_url"
_ORIGINAL_ASSESS = "_origin_quality_original_assess_origin_candidate"
_ORIGINAL_SEARCH_CONVERSION = "_origin_quality_original_search_results_to_candidates"

ORIGIN_HOST_LABELS = {"career", "careers", "jobs", "karriere", "recruiting"}
ORIGIN_PATH_SEGMENTS = {
    "career",
    "careers",
    "jobs",
    "karriere",
    "stellen",
    "stellenangebote",
    "jobboerse",
    "jobbörse",
    "recruiting",
    "vacancies",
    "join-us",
    "work-with-us",
}
JOB_DETAIL_SEGMENTS = {
    "job",
    "jobs",
    "posting",
    "position",
    "positions",
    "vacancy",
    "vacancies",
    "requisition",
}


def _valid_dns_hostname(hostname: str | None) -> bool:
    host = str(hostname or "").lower().strip(".")
    if not host:
        return False
    try:
        encoded = host.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    if len(encoded) > 253:
        return False
    labels = encoded.split(".")
    return all(
        1 <= len(label) <= 63
        and not label.startswith("-")
        and not label.endswith("-")
        and re.fullmatch(r"[a-z0-9-]+", label) is not None
        for label in labels
    )


def _path_segments(url: str) -> tuple[str, ...]:
    return tuple(
        segment.lower()
        for segment in urlparse(url).path.split("/")
        if segment.strip()
    )


def is_job_detail_url(url: str | None) -> bool:
    raw = str(url or "").strip()
    if not raw:
        return False
    segments = _path_segments(raw)
    if not segments:
        return False
    for index, segment in enumerate(segments):
        if segment not in JOB_DETAIL_SEGMENTS:
            continue
        # A tenant/list root such as /zscaler is not a detail page. A detail
        # marker must have at least one following path component.
        if index + 1 < len(segments):
            return True
    return False


def canonical_origin_from_job_detail(url: str | None) -> str | None:
    """Return a conservative reusable portal hypothesis for known detail shapes."""

    raw = str(url or "").strip()
    if not raw or not is_job_detail_url(raw):
        return None
    parsed = urlparse(raw)
    host = str(parsed.hostname or "").lower()
    segments = list(_path_segments(raw))
    if not host or not segments:
        return None

    if host == "job-boards.greenhouse.io" or host.endswith(".job-boards.greenhouse.io"):
        if len(segments) >= 3 and segments[1] == "jobs":
            return f"https://{host}/{segments[0]}"

    if host == "boards.greenhouse.io" or host.endswith(".boards.greenhouse.io"):
        if len(segments) >= 3 and segments[1] == "jobs":
            return f"https://{host}/{segments[0]}"

    if host == "careers.smartrecruiters.com" and len(segments) >= 2:
        return f"https://{host}/{segments[0]}"

    first_label = host.split(".", 1)[0]
    if first_label in ORIGIN_HOST_LABELS:
        return f"https://{host}/"
    return None


def _has_origin_locator(url: str | None) -> bool:
    raw = str(url or "").strip()
    if not raw:
        return False
    parsed = urlparse(raw)
    host = str(parsed.hostname or "").lower()
    if not host:
        return False
    first_label = host.split(".", 1)[0]
    if first_label in ORIGIN_HOST_LABELS:
        return True
    if origin_agent.is_known_ats_provider_domain(host):
        return True
    return any(segment in ORIGIN_PATH_SEGMENTS for segment in _path_segments(raw))


def _candidate_context_without_query(candidate: object, probe_title: str | None) -> str:
    evidence = getattr(candidate, "evidence", {})
    values: list[str] = []
    if isinstance(evidence, Mapping):
        values.extend(
            str(evidence.get(key) or "")
            for key in ("title", "snippet")
        )
    if probe_title:
        values.append(probe_title)
    return origin_agent.ascii_fold(" ".join(values))


def _distinctive_long_identity_tokens(company_name: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in origin_agent.tokenize(company_name)
        if len(token) >= 5
        and token not in origin_agent.LEGAL_OR_GENERIC_TOKENS
        and token not in origin_agent.LOCALITY_TOKENS
        and token not in {"and", "und", "the", "der", "die", "das"}
    )


def _short_identity_only(
    *,
    company_key: str,
    company_name: str,
    source_family_candidate: str | None,
) -> bool:
    tokens = origin_agent.company_identity_tokens(
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=source_family_candidate,
    )
    tokens = tuple(token for token in tokens if token not in origin_agent.LOCALITY_TOKENS)
    return bool(tokens) and all(len(token) <= 3 for token in tokens)


def _downgrade(
    assessment: origin_agent.OriginDiscoveryAssessment,
    *,
    decision: str,
    risk_level: str,
    reason: str,
) -> origin_agent.OriginDiscoveryAssessment:
    return replace(
        assessment,
        decision=decision,
        risk_level=risk_level,
        reasons=tuple((*assessment.reasons, reason)),
    )


def install_origin_quality_contract() -> None:
    """Install the quality contract exactly once per Python process."""

    if bool(getattr(origin_agent, _INSTALL_MARKER, False)):
        return

    original_normalize = origin_agent.normalize_candidate_url
    original_assess = origin_agent.assess_origin_candidate
    original_conversion = origin_agent.search_results_to_origin_candidates
    setattr(origin_agent, _ORIGINAL_NORMALIZE, original_normalize)
    setattr(origin_agent, _ORIGINAL_ASSESS, original_assess)
    setattr(origin_agent, _ORIGINAL_SEARCH_CONVERSION, original_conversion)

    def normalize_candidate_url_with_dns_guard(url: str | None) -> str | None:
        normalized = original_normalize(url)
        if normalized is None:
            return None
        if not _valid_dns_hostname(urlparse(normalized).hostname):
            return None
        return normalized

    def search_results_with_portal_hypotheses(
        results: Sequence[origin_agent.OriginSearchResult | Mapping[str, object]],
        *,
        source_priority: int = 8,
    ) -> tuple[origin_agent.OriginDiscoveryCandidate, ...]:
        converted = list(original_conversion(results, source_priority=source_priority))
        expanded: list[origin_agent.OriginDiscoveryCandidate] = []
        seen: set[str] = set()
        for item in converted:
            portal = canonical_origin_from_job_detail(item.url)
            if portal and portal not in seen:
                evidence = dict(item.evidence)
                evidence["derived_from_job_detail"] = item.url
                expanded.append(
                    origin_agent.OriginDiscoveryCandidate(
                        url=portal,
                        provider=item.provider,
                        reason="portal-root hypothesis derived from job-detail evidence",
                        source_priority=max(1, item.source_priority - 1),
                        evidence=evidence,
                    )
                )
                seen.add(portal)
            if item.url not in seen:
                expanded.append(item)
                seen.add(item.url)
        return tuple(expanded)

    def assess_origin_candidate_with_quality_gate(
        candidate: origin_agent.OriginDiscoveryCandidate,
        *,
        company_key: str,
        company_name: str,
        source_family_candidate: str | None = None,
        probe=None,
    ) -> origin_agent.OriginDiscoveryAssessment:
        assessment = original_assess(
            candidate,
            company_key=company_key,
            company_name=company_name,
            source_family_candidate=source_family_candidate,
            probe=probe,
        )
        if assessment.decision != "select_candidate":
            return assessment

        final_url = assessment.final_url or assessment.normalized_url or candidate.url
        host = urlparse(final_url).hostname
        intrinsic_identity, _ = origin_agent.company_identity_score(
            url=final_url,
            company_key=company_key,
            company_name=company_name,
            source_family_candidate=source_family_candidate,
        )

        if is_job_detail_url(final_url):
            return _downgrade(
                assessment,
                decision="manual_review_candidate",
                risk_level="medium",
                reason="job-detail evidence is not a reusable origin source",
            )

        if not _has_origin_locator(final_url):
            return _downgrade(
                assessment,
                decision="manual_review_candidate",
                risk_level="medium",
                reason="generic company page lacks a career/job origin locator",
            )

        if not origin_agent.is_known_ats_provider_domain(host) and intrinsic_identity < 0.45:
            return _downgrade(
                assessment,
                decision="reject",
                risk_level="medium",
                reason="search context cannot promote a third-party profile to origin source",
            )

        long_tokens = _distinctive_long_identity_tokens(company_name)
        context = _candidate_context_without_query(
            candidate,
            None if assessment.probe is None else assessment.probe.title,
        )
        if long_tokens and not any(token in context for token in long_tokens):
            host_tokens = set(origin_agent.tokenize(host or ""))
            matched_host = set(
                origin_agent.company_identity_tokens(
                    company_key=company_key,
                    company_name=company_name,
                    source_family_candidate=source_family_candidate,
                )
            ) & host_tokens
            if matched_host and all(len(token) <= 4 for token in matched_host):
                return _downgrade(
                    assessment,
                    decision="manual_review_candidate",
                    risk_level="medium",
                    reason="short brand/acronym host lacks full employer identity evidence",
                )

        if _short_identity_only(
            company_key=company_key,
            company_name=company_name,
            source_family_candidate=source_family_candidate,
        ):
            return _downgrade(
                assessment,
                decision="manual_review_candidate",
                risk_level="medium",
                reason="short-only employer identity is collision-prone and requires review",
            )

        return assessment

    origin_agent.normalize_candidate_url = normalize_candidate_url_with_dns_guard
    origin_agent.search_results_to_origin_candidates = search_results_with_portal_hypotheses
    origin_agent.assess_origin_candidate = assess_origin_candidate_with_quality_gate
    setattr(origin_agent, _INSTALL_MARKER, True)


__all__ = [
    "canonical_origin_from_job_detail",
    "install_origin_quality_contract",
    "is_job_detail_url",
]
