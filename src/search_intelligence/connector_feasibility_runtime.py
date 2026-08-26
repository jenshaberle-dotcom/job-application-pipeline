"""Runtime completion for generic S7N connector-feasibility evidence.

The historical S7N contract remains the authority for URL safety, bounded fetch,
link classification and all terminal decisions. This module adds two evidence
signals that the active runner previously did not project into those decisions:
HTML-level structure on dynamic job boards and trusted delegated job-board links.
"""

from __future__ import annotations

from dataclasses import replace
from html import unescape
import re
from typing import Iterable
from urllib.parse import urljoin, urlparse

from src.search_intelligence.career_origin_drift import career_origin_drift_candidates
from src.search_intelligence.connector_feasibility import (
    KNOWN_AGGREGATOR_DOMAINS,
    SOCIAL_OR_EXTERNAL_NOISE_DOMAINS,
    ConnectorFeasibilityItem,
    ConnectorFeasibilityReview,
    OriginCandidate,
    ProbeFetchResult,
    UrlQualityFeedback,
    bounded_fetch,
    classify_evidence_links,
    evaluate_connector_feasibility,
    html_has_structural_job_evidence,
    is_job_list_url,
    is_public_https_origin_url,
    is_technical_or_asset_url,
    structural_job_evidence_count,
)

STRONG_JOB_BOARD_LABELS = (
    "offene stellen",
    "stellenangebote",
    "alle jobs",
    "jobs ansehen",
    "jobs anzeigen",
    "jobs durchsuchen",
    "search jobs",
    "search vacancies",
    "view jobs",
    "all jobs",
    "find jobs",
    "job search",
    "vacancies",
    "open positions",
    "job openings",
    "see job openings",
    "current openings",
    "open roles",
    "view roles",
    "view all opportunities",
)

JOB_BOARD_HOST_LABELS = {
    "job",
    "jobs",
    "career",
    "careers",
    "karriere",
    "recruiting",
    "recruitment",
}

JOB_BOARD_PATH_PARTS = {
    "job",
    "jobs",
    "search",
    "job-search",
    "jobsearch",
    "stellen",
    "stellenangebote",
    "jobsuche",
    "vacancies",
    "positions",
    "open-positions",
}

LOCALE_PATH_PARTS = {
    "de",
    "de-de",
    "en",
    "en-gb",
    "en-us",
    "at",
    "ch",
}


def _normalized_label(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value).strip().lower())


def _registered_domain(url_or_host: str | None) -> str:
    if not url_or_host:
        return ""
    host = urlparse(url_or_host).hostname or url_or_host
    host = host.lower().removeprefix("www.")
    parts = host.split(".")
    if len(parts) < 2:
        return host
    return ".".join(parts[-2:])


def _same_registered_domain(left: str | None, right: str | None) -> bool:
    left_domain = _registered_domain(left)
    return bool(left_domain and left_domain == _registered_domain(right))


def _job_or_career_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    labels = {part for part in host.split(".") if part}
    return bool(labels.intersection(JOB_BOARD_HOST_LABELS))


def _strong_job_board_label(label: str) -> bool:
    normalized = _normalized_label(label)
    return any(marker in normalized for marker in STRONG_JOB_BOARD_LABELS)


def _job_board_path(url: str) -> bool:
    parts = {
        part.replace("_", "-").lower()
        for part in urlparse(url).path.strip("/").split("/")
        if part
    }
    return bool(parts.intersection(JOB_BOARD_PATH_PARTS))


def _shallow_locale_path(url: str) -> bool:
    parts = [
        part.replace("_", "-").lower()
        for part in urlparse(url).path.strip("/").split("/")
        if part
    ]
    return len(parts) <= 1 and (not parts or parts[0] in LOCALE_PATH_PARTS)


def _route_identity(url: str) -> str:
    """Collapse only an optional trailing slash for candidate deduplication."""

    return str(url or "").rstrip("/")


def _anchor_candidates(html: str) -> Iterable[tuple[str, str]]:
    pattern = re.compile(
        r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(html):
        href = unescape(match.group(1)).strip()
        text = re.sub(r"<[^>]+>", " ", match.group(2))
        text = re.sub(r"\s+", " ", unescape(text)).strip()
        yield href, text


def _safe_trusted_job_board_link(origin_url: str, absolute_url: str, label: str) -> bool:
    parsed = urlparse(absolute_url)
    host = (parsed.hostname or "").lower()
    if not is_public_https_origin_url(absolute_url):
        return False
    if host in KNOWN_AGGREGATOR_DOMAINS or host in SOCIAL_OR_EXTERNAL_NOISE_DOMAINS:
        return False
    if is_technical_or_asset_url(absolute_url):
        return False
    if not _strong_job_board_label(label):
        return False

    related_destination = _same_registered_domain(origin_url, absolute_url)
    delegated_job_host = _job_or_career_host(absolute_url)
    if not (related_destination or delegated_job_host):
        return False

    return _job_board_path(absolute_url) or _shallow_locale_path(absolute_url)


def extract_trusted_delegated_job_board_urls(
    origin_url: str,
    html: str,
    *,
    limit: int = 5,
) -> tuple[str, ...]:
    """Return strong, safe job-board links without selecting one automatically.

    The historical same-employer/job-host contract remains first. The newer
    career-origin drift contract contributes only explicit recognized ATS or
    recruiting-sibling transitions from this exact employer page. Those additions
    remain repair candidates, not host or Product authority.
    """

    if limit < 1:
        return ()

    candidates: list[str] = []
    seen: set[str] = set()
    normalized_origin = origin_url.rstrip("/")
    for raw_href, label in _anchor_candidates(html):
        absolute_url = urljoin(origin_url, raw_href)
        if absolute_url.rstrip("/") == normalized_origin:
            continue
        if not _safe_trusted_job_board_link(origin_url, absolute_url, label):
            continue
        identity = _route_identity(absolute_url)
        if identity not in seen:
            candidates.append(absolute_url)
            seen.add(identity)
        if len(candidates) >= limit:
            return tuple(candidates)

    origin_host = (urlparse(origin_url).hostname or "").casefold().strip(".")
    if not origin_host:
        return tuple(candidates)
    for drift_candidate in career_origin_drift_candidates(
        page_url=origin_url,
        html=html,
        allowed_hosts={origin_host},
        limit=limit,
    ):
        candidate_url = drift_candidate.candidate_url
        identity = _route_identity(candidate_url)
        if identity in seen:
            continue
        candidates.append(candidate_url)
        seen.add(identity)
        if len(candidates) >= limit:
            break
    return tuple(candidates)


def _dynamic_structural_count(
    candidate: OriginCandidate,
    result: ProbeFetchResult,
    item: ConnectorFeasibilityItem,
) -> int:
    if not candidate.origin_url:
        return item.structural_job_evidence_count

    classification = classify_evidence_links(candidate.origin_url, result.body)
    count = structural_job_evidence_count(
        candidate.origin_url,
        result.body,
        classification,
    )
    if count > classification.structural_count:
        return max(item.structural_job_evidence_count, count)

    final_url = result.final_url or candidate.origin_url
    trusted_dynamic_context = (
        is_job_list_url(final_url)
        or _job_or_career_host(final_url)
        or item.page_type == "ats_board_or_embed"
    )
    if trusted_dynamic_context and html_has_structural_job_evidence(result.body):
        count += 1
    return max(item.structural_job_evidence_count, count)


def _with_evidence(
    item: ConnectorFeasibilityItem,
    **updates: object,
) -> dict:
    evidence = dict(item.evidence)
    evidence.update(updates)
    return evidence


def evaluate_connector_feasibility_runtime(
    candidate: OriginCandidate,
    *,
    fetch_enabled: bool = True,
    fetch_result: ProbeFetchResult | None = None,
) -> ConnectorFeasibilityItem:
    """Complete generic S7N evidence without widening downstream authority."""

    if not fetch_enabled or not candidate.origin_url:
        return evaluate_connector_feasibility(
            candidate,
            fetch_enabled=fetch_enabled,
            fetch_result=fetch_result,
        )

    result = fetch_result if fetch_result is not None else bounded_fetch(candidate.origin_url)
    item = evaluate_connector_feasibility(
        candidate,
        fetch_enabled=True,
        fetch_result=result,
    )

    if item.feasibility_status in {"likely_feasible", "blocked", "missing_origin_url"}:
        return item
    if item.job_detail_candidate_evidence_count > 0:
        return item

    repair_candidates = extract_trusted_delegated_job_board_urls(
        candidate.origin_url,
        result.body,
    )
    if repair_candidates and item.structural_job_evidence_count == 0:
        repair_url = repair_candidates[0]
        feedback = UrlQualityFeedback(
            status="repair_candidate_detected",
            code="trusted_delegated_job_board_detected",
            repair_candidate_url=repair_url,
            message=(
                "The reviewed origin page exposes a strong, safe delegated job-board "
                "link. Candidate URL repair remains a separate CAND-001 decision."
            ),
        )
        return replace(
            item,
            blocker_code="origin_url_repair_candidate_detected",
            reason=(
                "Bounded probe reached the origin page and found a trusted delegated "
                "job board, but did not select or persist it automatically."
            ),
            recommended_next_action=(
                "Review the delegated job-board URL through CAND-001, then rerun "
                "connector feasibility."
            ),
            url_quality=feedback,
            evidence=_with_evidence(
                item,
                delegated_job_board_candidates=list(repair_candidates),
                url_quality_feedback=feedback.__dict__,
            ),
        )

    structural_count = _dynamic_structural_count(candidate, result, item)
    if item.reachable and structural_count > item.structural_job_evidence_count:
        feedback = UrlQualityFeedback(
            status="structural_without_detail",
            code="dynamic_job_structure_without_detail",
            repair_candidate_url=item.url_quality.repair_candidate_url,
            message=(
                "The reachable job/career page exposes generic HTML job-search "
                "structure, but no concrete job-detail sample was detected."
            ),
        )
        return replace(
            item,
            structural_job_evidence_count=structural_count,
            blocker_code="structural_evidence_without_job_detail",
            reason=(
                "Bounded probe found dynamic job-search structure but no concrete "
                "job-detail sample evidence."
            ),
            recommended_next_action=(
                "Review the source manually or improve bounded detail extraction "
                "before connector build planning."
            ),
            url_quality=feedback,
            evidence=_with_evidence(
                item,
                html_structural_job_evidence=True,
                structural_job_evidence_count=structural_count,
                url_quality_feedback=feedback.__dict__,
            ),
        )

    return item


def build_connector_feasibility_review(
    candidates: Iterable[OriginCandidate],
    *,
    reviewed_by: str,
    fetch_enabled: bool = True,
) -> ConnectorFeasibilityReview:
    items = tuple(
        evaluate_connector_feasibility_runtime(
            candidate,
            fetch_enabled=fetch_enabled,
        )
        for candidate in candidates
    )
    return ConnectorFeasibilityReview(
        items=items,
        fetch_enabled=fetch_enabled,
        reviewed_by=reviewed_by,
    )
