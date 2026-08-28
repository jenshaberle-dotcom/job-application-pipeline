"""Query-parameter job-detail completion for the generic S7N runtime.

The existing runtime remains authoritative for URL safety, bounded fetch, dynamic
structure, delegated-board repair and path-based detail evidence. This layer adds
only trusted same-origin query-parameter detail links.
"""

from __future__ import annotations

from dataclasses import replace
from html import unescape
import re
from typing import Iterable
from urllib.parse import parse_qsl, urljoin, urlparse

from src.search_intelligence.connector_feasibility import (
    JOB_DETAIL_MARKERS,
    KNOWN_AGGREGATOR_DOMAINS,
    SOCIAL_OR_EXTERNAL_NOISE_DOMAINS,
    ConnectorFeasibilityItem,
    ConnectorFeasibilityReview,
    EvidenceClassification,
    EvidenceLink,
    OriginCandidate,
    ProbeFetchResult,
    UrlQualityFeedback,
    bounded_fetch,
    is_public_https_origin_url,
    is_technical_or_asset_url,
)
from src.search_intelligence.connector_feasibility_runtime import (
    evaluate_connector_feasibility_runtime as evaluate_base_runtime,
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

QUERY_JOB_IDENTIFIER_KEYS = {
    "id",
    "jobid",
    "vacancyid",
    "vacancieid",
    "postingid",
    "requisitionid",
    "reqid",
    "positionid",
    "openingid",
}

QUERY_SCOPE_KEYS = {
    "companyid",
    "tenantid",
    "organisationid",
    "organizationid",
    "locale",
    "language",
    "lang",
}

QUERY_DETAIL_ACTION_KEYS = {
    "action",
}

QUERY_DETAIL_ACTION_VALUES = {
    "view",
    "detail",
    "show",
    "display",
}

QUERY_ROUTE_CONTEXT_KEYS = {
    "page",
    "mandatortemplateid",
}

QUERY_REDIRECT_KEYS = {
    "url",
    "redirect",
    "redirecturl",
    "returnurl",
    "target",
    "next",
    "continue",
}

GENERIC_DETAIL_LABELS = {
    "mehr",
    "mehr erfahren",
    "details",
    "detail",
    "anzeigen",
    "ansehen",
    "bewerben",
    "jetzt bewerben",
    "apply",
    "apply now",
    "read more",
    "learn more",
    "open",
}

JOB_TITLE_GENDER_MARKERS = (
    "m/w/d",
    "w/m/d",
    "f/m/d",
    "m/f/d",
    "m/w/x",
    "all genders",
)

QUERY_IDENTIFIER_VALUE_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{3,127}$"
)

QUERY_CONTEXT_VALUE_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)


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


def _normalized_path(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path or "/"


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


def _normalized_query_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _bounded_query_job_identifier(url: str) -> str | None:
    pairs = parse_qsl(urlparse(url).query, keep_blank_values=True)
    if not pairs or len(pairs) > 4:
        return None

    normalized_pairs = [
        (_normalized_query_key(key), value.strip())
        for key, value in pairs
    ]
    if any(key in QUERY_REDIRECT_KEYS for key, _ in normalized_pairs):
        return None

    identifiers = [
        value
        for key, value in normalized_pairs
        if key in QUERY_JOB_IDENTIFIER_KEYS
        and QUERY_IDENTIFIER_VALUE_PATTERN.fullmatch(value)
    ]
    if len(identifiers) != 1:
        return None

    for key, value in normalized_pairs:
        if key in QUERY_JOB_IDENTIFIER_KEYS:
            if not QUERY_IDENTIFIER_VALUE_PATTERN.fullmatch(value):
                return None
            continue
        if key in QUERY_DETAIL_ACTION_KEYS:
            if value.casefold() not in QUERY_DETAIL_ACTION_VALUES:
                return None
            continue
        if key in QUERY_ROUTE_CONTEXT_KEYS:
            if not QUERY_CONTEXT_VALUE_PATTERN.fullmatch(value):
                return None
            continue
        if key not in QUERY_SCOPE_KEYS:
            return None
        if not QUERY_IDENTIFIER_VALUE_PATTERN.fullmatch(value):
            return None

    return identifiers[0]


def _role_like_job_label(label: str) -> bool:
    normalized = _normalized_label(label)
    if not normalized or len(normalized) > 220:
        return False
    if normalized in GENERIC_DETAIL_LABELS:
        return False
    if any(marker in normalized for marker in JOB_TITLE_GENDER_MARKERS):
        return True

    tokens = set(re.findall(r"[a-z0-9äöüß]+", normalized))
    for marker in JOB_DETAIL_MARKERS:
        marker_tokens = (
            marker.lower().replace("-", " ").replace("_", " ").split()
        )
        if len(marker_tokens) == 1:
            token = marker_tokens[0]
            if len(token) <= 3:
                if token in tokens:
                    return True
            elif re.search(rf"\b{re.escape(token)}\b", normalized):
                return True
        elif all(token in tokens for token in marker_tokens):
            return True
    return False


def _safe_query_job_detail_link(
    origin_url: str,
    absolute_url: str,
    label: str,
) -> bool:
    parsed = urlparse(absolute_url)
    host = (parsed.hostname or "").lower()
    if not is_public_https_origin_url(absolute_url):
        return False
    if (
        host in KNOWN_AGGREGATOR_DOMAINS
        or host in SOCIAL_OR_EXTERNAL_NOISE_DOMAINS
    ):
        return False
    if is_technical_or_asset_url(absolute_url):
        return False
    if not _same_registered_domain(origin_url, absolute_url):
        return False
    if not (
        _job_or_career_host(origin_url)
        or _job_or_career_host(absolute_url)
    ):
        return False
    if not (
        _normalized_path(origin_url) == _normalized_path(absolute_url)
        or _job_board_path(absolute_url)
        or _shallow_locale_path(absolute_url)
    ):
        return False
    if _bounded_query_job_identifier(absolute_url) is None:
        return False
    return _role_like_job_label(label)


def extract_trusted_query_job_detail_links(
    origin_url: str,
    html: str,
    *,
    limit: int = 20,
) -> tuple[EvidenceLink, ...]:
    """Return concrete query-detail links from a trusted job-board surface."""

    candidates: list[EvidenceLink] = []
    seen: set[str] = set()
    for raw_href, label in _anchor_candidates(html):
        absolute_url = urljoin(origin_url, raw_href)
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        if not _safe_query_job_detail_link(
            origin_url,
            absolute_url,
            label,
        ):
            continue
        candidates.append(
            EvidenceLink(
                url=absolute_url,
                label=label,
                evidence_type="job_detail_candidate_evidence",
                reason=(
                    "trusted same-origin query-parameter job detail "
                    "with bounded identifier and role-like label"
                ),
            )
        )
        if len(candidates) >= limit:
            break
    return tuple(candidates)


def _classification_with_query_details(
    item: ConnectorFeasibilityItem,
    query_details: tuple[EvidenceLink, ...],
) -> EvidenceClassification:
    promoted_urls = {detail.url for detail in query_details}
    accepted = [
        link
        for link in item.evidence_classification.accepted
        if link.url not in promoted_urls
    ]
    accepted.extend(query_details)
    rejected = [
        link
        for link in item.evidence_classification.rejected
        if link.url not in promoted_urls
    ]
    return EvidenceClassification(
        accepted=tuple(accepted),
        rejected=tuple(rejected),
    )


def _with_query_detail_evidence(
    item: ConnectorFeasibilityItem,
    query_details: tuple[EvidenceLink, ...],
) -> ConnectorFeasibilityItem:
    classification = _classification_with_query_details(
        item,
        query_details,
    )
    structural_count = classification.structural_count
    sample_urls = classification.job_detail_candidate_urls[:5]
    feedback = UrlQualityFeedback(
        status="valid_probe_ready",
        code="sample_job_evidence_found",
        repair_candidate_url=None,
        message=(
            "Selected origin URL is reachable and exposes concrete "
            "query-parameter job-detail evidence."
        ),
    )
    evidence = dict(item.evidence)
    evidence.update(
        {
            "query_parameter_job_detail_candidates": [
                detail.url for detail in query_details
            ],
            "structural_job_evidence_count": structural_count,
            "evidence_classification": classification.as_dict(),
            "url_quality_feedback": feedback.__dict__,
        }
    )
    return replace(
        item,
        sample_job_urls=sample_urls,
        structural_job_evidence_count=structural_count,
        feasibility_status="likely_feasible",
        decision="continue_to_connector_build_planning",
        blocker_code=None,
        reason=(
            "Bounded probe reached a career-like page with job-list and "
            "concrete query-parameter job-detail evidence."
        ),
        recommended_next_action=(
            "Create connector build plan and capture one reviewed sample job "
            "before registration."
        ),
        url_quality=feedback,
        evidence_classification=classification,
        evidence=evidence,
    )


def evaluate_connector_feasibility_runtime(
    candidate: OriginCandidate,
    *,
    fetch_enabled: bool = True,
    fetch_result: ProbeFetchResult | None = None,
) -> ConnectorFeasibilityItem:
    """Complete S7N with bounded query-parameter detail evidence."""

    if not fetch_enabled or not candidate.origin_url:
        return evaluate_base_runtime(
            candidate,
            fetch_enabled=fetch_enabled,
            fetch_result=fetch_result,
        )

    result = (
        fetch_result
        if fetch_result is not None
        else bounded_fetch(candidate.origin_url)
    )
    item = evaluate_base_runtime(
        candidate,
        fetch_enabled=True,
        fetch_result=result,
    )
    if item.feasibility_status in {
        "likely_feasible",
        "blocked",
        "missing_origin_url",
    }:
        return item
    if not item.reachable:
        return item

    query_details = extract_trusted_query_job_detail_links(
        candidate.origin_url,
        result.body,
    )
    if not query_details:
        return item
    return _with_query_detail_evidence(item, query_details)


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
