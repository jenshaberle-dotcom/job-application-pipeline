from __future__ import annotations

import argparse
import json
import os
import re
from html import unescape
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import psycopg
import requests
from psycopg.rows import dict_row

from src.search_intelligence.multi_origin_evidence import (
    EvidenceDecision,
    EvidenceFailureReason,
    SearchDiscoveryQuery,
    UrlEvidenceCandidate,
    build_search_discovery_queries,
    classify_checked_url,
    decode_search_redirect_url,
    dedupe_url_candidates,
    job_detail_url_shape,
    plausible_sibling_origin_urls,
    registrable_domain_like,
    same_base_domain,
)


DETAIL_EVIDENCE_GATE = "detail_evidence_gate"
CONNECTOR_CANDIDATE_GATE = "connector_candidate_gate"

NON_JOB_DETAIL_URL_FRAGMENTS = (
    "/privacy",
    "/datenschutz",
    "/impressum",
    "/imprint",
    "/cookie",
    "/kontakt",
    "/contact",
    "/faq",
    "/your_career_opportunities",
)

GENERIC_DETAIL_LAST_SEGMENTS = (
    "career",
    "careers",
    "karriere",
    "job",
    "jobs",
    "job_board",
    "stellen",
    "stellenangebote",
    "offene-stellen",
    "stellen-finden",
)

JOB_DETAIL_PATH_MARKERS = (
    "/jobs/",
    "/job/",
    "/stellenangebote/",
    "/offene-stellen/",
    "/stellen-finden/",
    "/karriere/offene-stellen/",
    "/karriere/jobs/",
)

DEFAULT_PROFILE_TERMS = (
    "data",
    "daten",
    "analytics",
    "analyst",
    "business analyst",
    "business intelligence",
    "bi",
    "sql",
    "python",
    "ki",
    "ai",
    "software",
    "entwickler",
    "javascript",
    "ui",
    "product owner",
    "produktverantwort",
)

DEFAULT_LOCATION_TERMS = (
    "hannover",
    "remote",
    "deutschland",
    "bundesweit",
    "hybrid",
)

REQUEST_TIMEOUT_SECONDS = 20
SEARCH_DISCOVERY_URL = "https://html.duckduckgo.com/html/"
DEFAULT_SEARCH_QUERY_LIMIT = 6
DEFAULT_SEARCH_RESULT_LIMIT = 8
DEFAULT_EMBEDDED_DETAIL_URL_LIMIT = 80
DEFAULT_SEARCH_PROVIDER = "duckduckgo_html"
SUPPORTED_SEARCH_PROVIDERS = ("duckduckgo_html", "tavily")



@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: str
    dbname: str
    user: str
    password: str

    @classmethod
    def from_environment(cls) -> "DatabaseConfig":
        return cls(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
        )

    def dsn(self) -> str:
        return (
            f"host={self.host} "
            f"port={self.port} "
            f"dbname={self.dbname} "
            f"user={self.user} "
            f"password={self.password}"
        )


@dataclass(frozen=True)
class SourceCandidate:
    id: int
    company_key: str
    company_name: str
    candidate_url: str
    source_name_candidate: str
    source_family_candidate: str
    source_target_candidate: str | None
    source_type_candidate: str
    status: str
    risk_level: str


@dataclass(frozen=True)
class LinkCandidate:
    url: str
    source_url: str
    text: str
    profile_terms: tuple[str, ...]
    location_terms: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class StructuredSearchResult:
    url: str
    title: str
    snippet: str
    query: str
    provider: str


@dataclass(frozen=True)
class DetailEvidence:
    url: str
    final_url: str
    status_code: int
    title: str
    profile_terms: tuple[str, ...]
    location_terms: tuple[str, ...]
    html_bytes: int
    reason: str


@dataclass(frozen=True)
class RepairOutcome:
    gate_status: str
    decision: str
    stop_reason: str | None
    details: tuple[DetailEvidence, ...]
    rejected_urls: tuple[str, ...]
    requested_urls: tuple[str, ...]
    evidence: dict[str, Any]


class LinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        self._href = urljoin(self.base_url, href)
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            self.links.append((self._href.split("#", 1)[0], normalize_whitespace(" ".join(self._text))))
            self._href = None
            self._text = []


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        self.text_parts.append(data)

    @property
    def title(self) -> str:
        return normalize_whitespace(" ".join(self.title_parts))

    @property
    def text(self) -> str:
        return normalize_whitespace(" ".join(self.text_parts))


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def normalize_text(value: str | None) -> str:
    value = normalize_whitespace(value).casefold()
    return value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def unique_ordered(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return tuple(result)


def _term_pattern(term: str) -> re.Pattern[str]:
    normalized = re.escape(normalize_text(term))
    # Very short profile tokens such as AI, BI, UI and KI are useful but noisy.
    # Match them as standalone tokens so words like maintenance or build do not
    # accidentally count as AI/BI/UI evidence.
    if len(normalize_text(term)) <= 3 and normalize_text(term).isalnum():
        return re.compile(rf"(?<![a-z0-9]){normalized}(?![a-z0-9])")
    return re.compile(normalized)


def find_terms(value: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    haystack = normalize_text(value)
    matches: list[str] = []
    for term in terms:
        if _term_pattern(term).search(haystack) and term not in matches:
            matches.append(term)
    return tuple(matches)


def _canonical_detail_url_key(url: str) -> str:
    parsed = urlparse(url)
    path = re.sub(r"/{2,}", "/", (parsed.path or "/")).rstrip("/") or "/"
    normalized = parsed._replace(
        scheme=parsed.scheme.casefold(),
        netloc=parsed.netloc.casefold(),
        path=path,
        params="",
        fragment="",
    )
    return urlunparse(normalized)


def _url_path_contains_term(url: str, term: str) -> bool:
    path = normalize_text(urlparse(url).path.replace("-", " ").replace("_", " ").replace("/", " "))
    return bool(_term_pattern(term).search(path))


def _labeled_location_signal(term: str, value: str) -> bool:
    normalized_term = re.escape(normalize_text(term))
    haystack = normalize_text(value)
    patterns = (
        rf"\b(standort|arbeitsort|arbeitsplatz|ort|location|locations|city|office|workplace)\b[^.!?\n]{{0,100}}\b{normalized_term}\b",
        rf"\b{normalized_term}\b\s*\((nds|niedersachsen|de|deutschland|germany)\)",
    )
    return any(re.search(pattern, haystack) for pattern in patterns)


def _generic_in_location_signal(term: str, value: str) -> bool:
    normalized_term = re.escape(normalize_text(term))
    haystack = normalize_text(value)
    return bool(re.search(rf"\b(in|at)\s+{normalized_term}\b", haystack))


def _strong_contextual_location_signal(term: str, value: str) -> bool:
    return _labeled_location_signal(term, value) or _generic_in_location_signal(term, value)


def filter_target_location_terms(
    *,
    candidate: SourceCandidate,
    url: str,
    title: str,
    text: str,
    terms: tuple[str, ...],
) -> tuple[str, ...]:
    """Keep target-location terms while suppressing employer-brand noise.

    DETAIL-004 exposed a false-positive pattern for employers whose name itself
    contains the target city.  For example, Hannover Rück pages for London or
    Orlando can contain the word Hannover only because of the employer brand,
    not because the job is located in Hannover.  When the company name already
    contains a location term, the term must also appear in the job URL path or
    in a location-like textual context.
    """

    raw_matches = find_terms(" ".join([url, title, text]), terms)
    company_blob = normalize_text(candidate.company_name)
    filtered: list[str] = []
    for term in raw_matches:
        normalized_term = normalize_text(term)
        if normalized_term not in company_blob:
            filtered.append(term)
            continue
        text_blob = " ".join([title, text])
        if _url_path_contains_term(url, term) or _labeled_location_signal(term, text_blob):
            filtered.append(term)
    return tuple(filtered)


def concrete_job_detail_url(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False

    parsed = urlparse(url)
    path = re.sub(r"/+", "/", parsed.path.casefold()).rstrip("/")
    if not path:
        return False

    if any(fragment in path for fragment in NON_JOB_DETAIL_URL_FRAGMENTS):
        return False

    if job_detail_url_shape(url):
        return True

    last_segment = path.rsplit("/", 1)[-1]
    if last_segment in GENERIC_DETAIL_LAST_SEGMENTS:
        return False

    if not any(marker in f"{path}/" for marker in JOB_DETAIL_PATH_MARKERS):
        return False

    if len(last_segment) < 6:
        return False

    return "-" in last_segment or "_" in last_segment or any(ch.isdigit() for ch in last_segment)


def same_host(url: str, allowed_hosts: tuple[str, ...]) -> bool:
    return urlparse(url).netloc.casefold() in allowed_hosts


def plausible_origin_url(url: str, candidate: SourceCandidate) -> bool:
    candidate_url = candidate.candidate_url
    parsed_host = urlparse(url).netloc.casefold()
    if not parsed_host:
        return False
    if same_base_domain(url, candidate_url):
        return True
    # Company key in host/path is a weaker but useful signal for search-result candidates.
    return candidate.company_key.casefold() in url.casefold()


def extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
    parser = LinkExtractor(base_url)
    parser.feed(html)
    return parser.links


def _decode_embedded_url_text(value: str) -> str:
    """Normalize common HTML/JSON escaping before embedded URL extraction."""

    decoded = unescape(value or "")
    decoded = decoded.replace(r"\/", "/")
    decoded = decoded.replace(r"\u002F", "/").replace(r"\u002f", "/")
    return decoded


def _clean_embedded_url_candidate(raw_url: str, *, base_url: str) -> str | None:
    cleaned = raw_url.strip().strip("\"'`),;")
    cleaned = cleaned.replace("&amp;", "&")
    if cleaned.startswith(("mailto:", "tel:", "javascript:")):
        return None
    if cleaned.startswith(("http://", "https://", "/")):
        return urljoin(base_url, cleaned).split("#", 1)[0]
    return None


def extract_embedded_detail_url_candidates(
    html: str,
    base_url: str,
    *,
    limit: int = DEFAULT_EMBEDDED_DETAIL_URL_LIMIT,
) -> list[tuple[str, str]]:
    """Extract detail-shaped URLs that are present outside ordinary anchors.

    Many employer-origin job portals render visible job cards with JavaScript.
    The static HTML can still contain concrete URLs in JSON blobs, inline
    scripts, or escaped state payloads. DETAIL-002 keeps this bounded and
    deterministic: it only emits URLs that already look like concrete job-detail
    paths, and later validation still fetches and checks the detail page.
    """

    decoded = _decode_embedded_url_text(html)
    patterns = (
        r"https?://[^\s\"'<>]+",
        r"/(?:job|jobs|stellenangebote|offene-stellen|stellen-finden|karriere/jobs|karriere/offene-stellen)/[^\s\"'<>]+",
    )
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, decoded, flags=re.IGNORECASE):
            url = _clean_embedded_url_candidate(match.group(0), base_url=base_url)
            if not url or url in seen:
                continue
            if not concrete_job_detail_url(url):
                continue
            seen.add(url)
            result.append((url, "embedded detail URL candidate"))
            if len(result) >= limit:
                return result
    return result


def candidate_hosts(candidate: SourceCandidate) -> tuple[str, ...]:
    hosts = [urlparse(candidate.candidate_url).netloc.casefold()]
    for item in plausible_sibling_origin_urls(candidate.candidate_url, company_key=candidate.company_key):
        hosts.append(urlparse(item.url).netloc.casefold())
    return unique_ordered(hosts)


def _clean_persisted_evidence_url(raw_value: object) -> str | None:
    """Return only a real URL from persisted gate evidence.

    Gate evidence keeps human-readable rejection strings such as
    ``https://jobs.example.com/ :: not_concrete_job_detail_url``. These are
    audit output, not URLs. DETAIL-002A prevents those strings from re-entering
    bounded probing as malformed URLs like ``%20::%20not_concrete_job_detail_url``.
    DETAIL-003 then keeps rejected URL lists out of the seed budget entirely.
    """

    value = str(raw_value or "").strip()
    if not value:
        return None
    candidate_url = value.split(" :: ", 1)[0].strip()
    normalized = candidate_url.split("#", 1)[0].strip()
    if not normalized.startswith(("http://", "https://")):
        return None
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return normalized


def _concrete_url_from_evidence_item(item: object) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in ("url", "final_url"):
        cleaned = _clean_persisted_evidence_url(item.get(key))
        if cleaned and concrete_job_detail_url(cleaned):
            return cleaned
    return None


def requested_seed_urls(candidate: SourceCandidate, gates: dict[str, dict[str, Any]]) -> tuple[str, ...]:
    urls = [candidate.candidate_url]

    detail_gate = gates.get(DETAIL_EVIDENCE_GATE) or {}
    evidence = detail_gate.get("evidence") or {}

    # DETAIL-003: rejected URLs are audit evidence, not a seed source.  Reusing
    # old rejection lists made noisy DuckDuckGo, CloudFront and overview links
    # consume the bounded max_seed_pages budget before fresh search-discovered
    # job-detail candidates could be probed.  Only previously supported details
    # or explicit concrete candidate links are safe to replay.
    for collection_key in ("details", "supported_details", "candidate_links", "detail_assessments"):
        for item in evidence.get(collection_key) or []:
            concrete_url = _concrete_url_from_evidence_item(item)
            if concrete_url:
                urls.append(concrete_url)

    return unique_ordered([url for url in (_clean_persisted_evidence_url(item) for item in urls) if url])


def fetch_url(url: str) -> tuple[str, str, int]:
    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "job-application-pipeline-employer-origin-detail-repair-agent/0.1 "
                "(bounded; no browser automation; no raw html persistence)"
            ),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text, response.url, response.status_code


def fetch_search_results(query: str) -> tuple[str, str, int]:
    url = SEARCH_DISCOVERY_URL + "?" + urlencode({"q": query})
    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "job-application-pipeline-employer-origin-search-discovery/0.1 "
                "(bounded; no browser automation; no raw html persistence)"
            ),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text, response.url, response.status_code


def load_local_env_file(path: str = ".env") -> None:
    """Load local .env entries without overriding already configured secrets."""

    env_path = os.path.abspath(path)
    if not os.path.exists(env_path):
        return

    with open(env_path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and (_is_missing_or_placeholder_secret(os.environ.get(key))):
                os.environ[key] = value


def _is_missing_or_placeholder_secret(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip()
    lowered = normalized.lower()
    return (
        normalized == ""
        or normalized == "..."
        or "your_api_key" in lowered
        or "api_key" in lowered
        or "realer_key" in lowered
        or "hier" in lowered
        or normalized in {"<YOUR_API_KEY>", "YOUR_API_KEY", "changeme"}
    )


def _response_json_or_empty(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def fetch_tavily_search_results(
    query: str,
    *,
    max_results: int,
    timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
    search_depth: str = "basic",
) -> tuple[StructuredSearchResult, ...]:
    """Fetch structured search results from Tavily for detail candidate discovery.

    Tavily is used only as a candidate discovery provider.  Results still have
    to pass plausibility, concrete detail URL shape checks and bounded HTTP
    detail-page validation before any gate can pass.
    """

    api_key = os.getenv("TAVILY_API_KEY")
    if _is_missing_or_placeholder_secret(api_key):
        return ()

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "query": query,
                "search_depth": search_depth,
                "max_results": max(1, min(max_results, 10)),
                "include_answer": False,
                "include_raw_content": False,
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException:
        return ()

    payload = _response_json_or_empty(response)
    results: list[StructuredSearchResult] = []
    for item in payload.get("results", []):
        if not isinstance(item, dict) or not item.get("url"):
            continue
        results.append(
            StructuredSearchResult(
                url=str(item.get("url") or ""),
                title=str(item.get("title") or ""),
                snippet=str(item.get("content") or ""),
                query=query,
                provider="tavily",
            )
        )
    return tuple(results)


def _search_result_candidate(
    *,
    result_url: str,
    title: str,
    snippet: str,
    query: str,
    provider: str,
    candidate: SourceCandidate,
    base_url: str | None = None,
) -> tuple[UrlEvidenceCandidate | None, str | None]:
    decoded = decode_search_redirect_url(result_url, base_url=base_url)
    if not decoded:
        return None, f"{result_url} :: malformed_search_result_url"
    if not plausible_origin_url(decoded, candidate):
        return None, f"{decoded} :: {EvidenceFailureReason.DOMAIN_NOT_PLAUSIBLE.value}"
    if not any(marker in decoded.casefold() for marker in ("job", "career", "karriere", "stellen")):
        return None, f"{decoded} :: no_job_or_career_url_marker"

    text = normalize_whitespace(" ".join([title, snippet]))
    confidence_hint = 0.74 if concrete_job_detail_url(decoded) else 0.60
    return (
        UrlEvidenceCandidate(
            url=decoded,
            discovery_source=f"external_search:{provider}",
            confidence_hint=confidence_hint,
            reason=f"{provider} result for query: {query}; text={text[:160]}",
        ),
        None,
    )


def discover_search_result_candidates(
    *,
    candidate: SourceCandidate,
    profile_terms: tuple[str, ...],
    location_terms: tuple[str, ...],
    max_queries: int,
    max_results: int,
    search_provider: str = DEFAULT_SEARCH_PROVIDER,
    search_fetcher=fetch_search_results,
    tavily_fetcher=fetch_tavily_search_results,
) -> tuple[tuple[UrlEvidenceCandidate, ...], tuple[str, ...], tuple[str, ...], tuple[SearchDiscoveryQuery, ...]]:
    queries = build_search_discovery_queries(
        company_name=candidate.company_name,
        company_key=candidate.company_key,
        profile_terms=profile_terms,
        location_terms=location_terms,
        max_queries=max_queries,
        candidate_url=candidate.candidate_url,
    )
    requested_queries: list[str] = []
    rejected_results: list[str] = []
    discovered: list[UrlEvidenceCandidate] = []
    seen_results: set[str] = set()

    if search_provider not in SUPPORTED_SEARCH_PROVIDERS:
        rejected_results.append(f"search_provider={search_provider} :: unsupported_search_provider")
        return (), unique_ordered(rejected_results), (), queries

    for query in queries:
        requested_queries.append(query.query)

        if search_provider == "tavily":
            results = tavily_fetcher(query.query, max_results=max_results)
            if not results:
                rejected_results.append(f"{query.query} :: tavily_no_results_or_provider_unavailable")
                continue
            for result in results:
                candidate_result, rejection = _search_result_candidate(
                    result_url=result.url,
                    title=result.title,
                    snippet=result.snippet,
                    query=result.query,
                    provider=result.provider,
                    candidate=candidate,
                )
                decoded_url = candidate_result.url if candidate_result else result.url
                if decoded_url in seen_results:
                    continue
                seen_results.add(decoded_url)
                if rejection:
                    rejected_results.append(rejection)
                    continue
                discovered.append(candidate_result)
                if len(discovered) >= max_results:
                    break
            if len(discovered) >= max_results:
                break
            continue

        try:
            html, final_url, status_code = search_fetcher(query.query)
        except Exception as exc:  # noqa: BLE001 - bounded search discovery must continue.
            rejected_results.append(f"{query.query} :: search_fetch_error={type(exc).__name__}")
            continue

        if status_code >= 400:
            rejected_results.append(f"{query.query} :: search_status={status_code}")
            continue

        for raw_url, text in extract_links(html, final_url):
            candidate_result, rejection = _search_result_candidate(
                result_url=raw_url,
                title=text,
                snippet="",
                query=query.query,
                provider="duckduckgo_html",
                candidate=candidate,
                base_url=final_url,
            )
            decoded_url = candidate_result.url if candidate_result else (decode_search_redirect_url(raw_url, base_url=final_url) or raw_url)
            if decoded_url in seen_results:
                continue
            seen_results.add(decoded_url)
            if rejection:
                rejected_results.append(rejection)
                continue
            discovered.append(candidate_result)
            if len(discovered) >= max_results:
                break
        if len(discovered) >= max_results:
            break

    return (
        dedupe_url_candidates(discovered),
        unique_ordered(rejected_results),
        unique_ordered(requested_queries),
        queries,
    )


def build_seed_url_candidates(
    *,
    candidate: SourceCandidate,
    gates: dict[str, dict[str, Any]],
    profile_terms: tuple[str, ...],
    location_terms: tuple[str, ...],
    enable_search_discovery: bool,
    max_search_queries: int,
    max_search_results: int,
    search_provider: str = DEFAULT_SEARCH_PROVIDER,
    search_fetcher=fetch_search_results,
    tavily_fetcher=fetch_tavily_search_results,
) -> tuple[tuple[UrlEvidenceCandidate, ...], tuple[str, ...], tuple[str, ...], tuple[SearchDiscoveryQuery, ...]]:
    persisted_candidates: list[UrlEvidenceCandidate] = []
    for url in requested_seed_urls(candidate, gates):
        persisted_candidates.append(
            UrlEvidenceCandidate(
                url,
                "persisted_gate_evidence",
                0.76,
                "candidate URL or previous gate evidence URL",
            )
        )

    sibling_candidates: list[UrlEvidenceCandidate] = list(
        plausible_sibling_origin_urls(candidate.candidate_url, company_key=candidate.company_key)
    )

    search_rejections: tuple[str, ...] = ()
    requested_search_queries: tuple[str, ...] = ()
    search_candidates: tuple[UrlEvidenceCandidate, ...] = ()
    planned_queries = build_search_discovery_queries(
        company_name=candidate.company_name,
        company_key=candidate.company_key,
        profile_terms=profile_terms,
        location_terms=location_terms,
        max_queries=max_search_queries,
        candidate_url=candidate.candidate_url,
    )
    if enable_search_discovery:
        search_candidates, search_rejections, requested_search_queries, planned_queries = discover_search_result_candidates(
            candidate=candidate,
            profile_terms=profile_terms,
            location_terms=location_terms,
            max_queries=max_search_queries,
            max_results=max_search_results,
            search_provider=search_provider,
            search_fetcher=search_fetcher,
            tavily_fetcher=tavily_fetcher,
        )

    # A1 priority rule:
    # Concrete job-detail URLs discovered by search are more valuable than broad
    # sibling-host guesses. They must not be pushed out by max_seed_pages.
    direct_search_details = [item for item in search_candidates if concrete_job_detail_url(item.url)]
    other_search_candidates = [item for item in search_candidates if not concrete_job_detail_url(item.url)]
    sibling_details = [item for item in sibling_candidates if concrete_job_detail_url(item.url)]
    sibling_non_details = [item for item in sibling_candidates if not concrete_job_detail_url(item.url)]

    seed_candidates = [
        *persisted_candidates,
        *direct_search_details,
        *sibling_details,
        *other_search_candidates,
        *sibling_non_details,
    ]

    return (
        dedupe_url_candidates(seed_candidates),
        search_rejections,
        requested_search_queries,
        planned_queries,
    )


def discover_link_candidates(
    *,
    candidate: SourceCandidate,
    gates: dict[str, dict[str, Any]],
    profile_terms: tuple[str, ...],
    location_terms: tuple[str, ...],
    max_seed_pages: int,
    enable_search_discovery: bool = True,
    max_search_queries: int = DEFAULT_SEARCH_QUERY_LIMIT,
    max_search_results: int = DEFAULT_SEARCH_RESULT_LIMIT,
    search_provider: str = DEFAULT_SEARCH_PROVIDER,
    fetcher=fetch_url,
    search_fetcher=fetch_search_results,
    tavily_fetcher=fetch_tavily_search_results,
) -> tuple[tuple[LinkCandidate, ...], tuple[str, ...], tuple[str, ...], dict[str, Any]]:
    seed_candidates, search_rejections, requested_search_queries, planned_queries = build_seed_url_candidates(
        candidate=candidate,
        gates=gates,
        profile_terms=profile_terms,
        location_terms=location_terms,
        enable_search_discovery=enable_search_discovery,
        max_search_queries=max_search_queries,
        max_search_results=max_search_results,
        search_provider=search_provider,
        search_fetcher=search_fetcher,
        tavily_fetcher=tavily_fetcher,
    )

    requested_urls: list[str] = []
    rejected_urls: list[str] = [*search_rejections]
    link_candidates: list[LinkCandidate] = []
    checked_origin_candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    for seed in seed_candidates[:max_seed_pages]:
        seed_url = seed.url
        origin_record: dict[str, Any] = {
            "url": seed_url,
            "discovery_source": seed.discovery_source,
            "confidence_hint": seed.confidence_hint,
            "reason": seed.reason,
            "host": urlparse(seed_url).netloc.casefold(),
            "base_domain": registrable_domain_like(seed_url),
            "accepted_link_count": 0,
            "status": "pending",
            "rejection_reasons": [],
        }
        if not plausible_origin_url(seed_url, candidate):
            reason = EvidenceFailureReason.DOMAIN_NOT_PLAUSIBLE.value
            origin_record["status"] = "rejected"
            origin_record["rejection_reasons"].append(reason)
            rejected_urls.append(f"{seed_url} :: {reason}")
            checked_origin_candidates.append(origin_record)
            continue

        try:
            html, final_url, status_code = fetcher(seed_url)
        except Exception as exc:  # noqa: BLE001 - bounded repair must continue across individual URL failures.
            reason = f"fetch_error={type(exc).__name__}"
            origin_record["status"] = "fetch_error"
            origin_record["rejection_reasons"].append(reason)
            rejected_urls.append(f"{seed_url} :: {reason}")
            checked_origin_candidates.append(origin_record)
            continue

        requested_urls.append(final_url)
        origin_record["final_url"] = final_url
        origin_record["status_code"] = status_code
        if not plausible_origin_url(final_url, candidate):
            reason = EvidenceFailureReason.DOMAIN_NOT_PLAUSIBLE.value
            origin_record["status"] = "rejected"
            origin_record["rejection_reasons"].append(reason)
            rejected_urls.append(f"{final_url} :: {reason}")
            checked_origin_candidates.append(origin_record)
            continue
        if status_code >= 400:
            reason = EvidenceFailureReason.URL_NOT_REACHABLE.value
            origin_record["status"] = "rejected"
            origin_record["rejection_reasons"].append(reason)
            rejected_urls.append(f"{final_url} :: status={status_code}")
            checked_origin_candidates.append(origin_record)
            continue

        # A search engine can return an actual detail page directly, and a candidate URL can also be a detail page.
        if concrete_job_detail_url(final_url):
            evidence_blob = final_url
            matched_profile = find_terms(evidence_blob, profile_terms)
            matched_location = find_terms(evidence_blob, location_terms)
            link_candidates.append(
                LinkCandidate(
                    url=final_url,
                    source_url=final_url,
                    text="direct detail candidate",
                    profile_terms=matched_profile,
                    location_terms=matched_location,
                    reason="Seed URL itself is a concrete job-detail URL candidate.",
                )
            )
            origin_record["accepted_link_count"] = int(origin_record["accepted_link_count"]) + 1

        extracted_links = extract_links(html, final_url)
        embedded_links = extract_embedded_detail_url_candidates(html, final_url)
        candidate_links_to_check = [*extracted_links, *embedded_links]
        if not candidate_links_to_check:
            origin_record["rejection_reasons"].append(EvidenceFailureReason.NO_JOB_LIST_FOUND.value)

        for url, text in candidate_links_to_check:
            if url in seen:
                continue
            seen.add(url)

            if not plausible_origin_url(url, candidate):
                rejected_urls.append(f"{url} :: {EvidenceFailureReason.DOMAIN_NOT_PLAUSIBLE.value}")
                continue

            if not concrete_job_detail_url(url):
                rejected_urls.append(f"{url} :: not_concrete_job_detail_url")
                continue

            evidence_blob = " ".join([url, text])
            matched_profile = find_terms(evidence_blob, profile_terms)
            matched_location = find_terms(evidence_blob, location_terms)

            # Keep plausible job detail URLs even if signals are not visible in link text;
            # the detail page validation stage gets the final say.
            link_candidates.append(
                LinkCandidate(
                    url=url,
                    source_url=final_url,
                    text=text,
                    profile_terms=matched_profile,
                    location_terms=matched_location,
                    reason="Concrete job-detail URL found during multi-origin bounded repair.",
                )
            )
            origin_record["accepted_link_count"] = int(origin_record["accepted_link_count"]) + 1

        if int(origin_record["accepted_link_count"]) > 0:
            origin_record["status"] = "job_detail_candidates_found"
        elif origin_record["status"] == "pending":
            origin_record["status"] = "checked_no_detail_candidates"
            origin_record["rejection_reasons"].append(EvidenceFailureReason.JOB_LIST_FOUND_BUT_NO_DETAIL_LINKS.value)
        checked_origin_candidates.append(origin_record)

    discovery_evidence = {
        "checked_origin_candidates": checked_origin_candidates,
        "planned_search_queries": [
            {"query": query.query, "reason": query.reason} for query in planned_queries
        ],
        "requested_search_queries": list(requested_search_queries),
        "search_discovery_enabled": enable_search_discovery,
        "detail_link_discovery_version": "DETAIL-004B",
        "embedded_detail_url_extraction_enabled": True,
        "search_provider": search_provider,
    }
    return tuple(link_candidates), unique_ordered(rejected_urls), unique_ordered(requested_urls), discovery_evidence



def parse_detail_page(html: str) -> tuple[str, str]:
    parser = TextExtractor()
    parser.feed(html)
    return parser.title, parser.text


def validate_detail_candidates(
    *,
    candidate: SourceCandidate,
    link_candidates: tuple[LinkCandidate, ...],
    profile_terms: tuple[str, ...],
    location_terms: tuple[str, ...],
    max_detail_pages: int,
    fetcher=fetch_url,
) -> tuple[tuple[DetailEvidence, ...], tuple[str, ...], tuple[str, ...], tuple[dict[str, Any], ...]]:
    requested_urls: list[str] = []
    rejected_urls: list[str] = []
    details: list[DetailEvidence] = []
    assessments: list[dict[str, Any]] = []
    seen_link_keys: set[str] = set()
    accepted_detail_keys: set[str] = set()
    checked_count = 0

    for link in link_candidates:
        link_key = _canonical_detail_url_key(link.url)
        if link_key in seen_link_keys:
            continue
        seen_link_keys.add(link_key)
        if checked_count >= max_detail_pages:
            break
        checked_count += 1

        try:
            html, final_url, status_code = fetcher(link.url)
        except Exception as exc:  # noqa: BLE001
            rejected_urls.append(f"{link.url} :: fetch_error={type(exc).__name__}")
            assessments.append(
                {
                    "url": link.url,
                    "decision": EvidenceDecision.MANUAL_REVIEW_REQUIRED.value,
                    "failure_reason": EvidenceFailureReason.URL_NOT_REACHABLE.value,
                    "confidence_score": 0.40,
                    "confidence_reason": f"detail page fetch failed with {type(exc).__name__}",
                }
            )
            continue

        requested_urls.append(final_url)
        if status_code >= 400:
            rejected_urls.append(f"{final_url} :: status={status_code}")
            assessments.append(
                {
                    "url": final_url,
                    "decision": EvidenceDecision.REJECTED.value,
                    "failure_reason": EvidenceFailureReason.URL_NOT_REACHABLE.value,
                    "confidence_score": 0.80,
                    "confidence_reason": f"detail page returned status {status_code}",
                }
            )
            continue

        title, text = parse_detail_page(html)
        evidence_blob = " ".join([link.url, link.text, title, text])
        matched_profile = find_terms(evidence_blob, profile_terms)
        matched_location = filter_target_location_terms(
            candidate=candidate,
            url=final_url,
            title=title,
            text=text,
            terms=location_terms,
        )
        assessment = classify_checked_url(
            url=final_url,
            reference_url=candidate.candidate_url,
            profile_terms=profile_terms,
            location_terms=location_terms,
            text=evidence_blob,
        )
        final_key = _canonical_detail_url_key(final_url)
        assessment_record = {
            "url": assessment.url,
            "decision": assessment.decision.value,
            "failure_reason": assessment.failure_reason.value if assessment.failure_reason else None,
            "confidence_score": assessment.confidence_score,
            "confidence_reason": assessment.confidence_reason,
            "page_type": assessment.page_type,
            "signals": {
                **assessment.signals,
                "profile_terms": list(matched_profile),
                "location_terms": list(matched_location),
            },
        }
        assessments.append(assessment_record)

        if assessment.decision != EvidenceDecision.ACCEPTED:
            reason = assessment.failure_reason.value if assessment.failure_reason else EvidenceDecision.REJECTED.value
            rejected_urls.append(f"{final_url} :: {reason}")
            continue
        if final_key in accepted_detail_keys:
            rejected_urls.append(f"{final_url} :: duplicate_detail_url")
            continue
        if not matched_profile:
            rejected_urls.append(f"{final_url} :: {EvidenceFailureReason.DETAIL_PAGE_EXTRACTED_BUT_NO_PROFILE_SIGNAL.value}")
            continue
        if not matched_location:
            rejected_urls.append(f"{final_url} :: {EvidenceFailureReason.DETAIL_PAGE_EXTRACTED_BUT_NO_TARGET_SIGNAL.value}")
            continue

        accepted_detail_keys.add(final_key)
        details.append(
            DetailEvidence(
                url=link.url,
                final_url=final_url,
                status_code=status_code,
                title=title,
                profile_terms=matched_profile,
                location_terms=matched_location,
                html_bytes=len(html.encode("utf-8")),
                reason="Detail page contains concrete job URL plus profile and target/remote signals.",
            )
        )

    return tuple(details), unique_ordered(rejected_urls), unique_ordered(requested_urls), tuple(assessments)



def link_candidate_to_report_dict(link: LinkCandidate) -> dict[str, Any]:
    return {
        "url": link.url,
        "source_url": link.source_url,
        "text": link.text,
        "profile_terms": list(link.profile_terms),
        "location_terms": list(link.location_terms),
        "reason": link.reason,
    }


def detail_evidence_to_report_dict(detail: DetailEvidence) -> dict[str, Any]:
    return {
        "url": detail.url,
        "final_url": detail.final_url,
        "status_code": detail.status_code,
        "title": detail.title,
        "profile_terms": list(detail.profile_terms),
        "location_terms": list(detail.location_terms),
        "html_bytes": detail.html_bytes,
        "raw_html_persisted": False,
        "reason": detail.reason,
    }


def detail_evidence_report_contract() -> dict[str, Any]:
    """Describe DETAIL JSON evidence levels for reviewers and downstream UIs.

    The repair agent intentionally exposes multiple evidence stages.  Search and
    listing extraction can find many plausible links, but only fetched and
    assessed detail pages are authoritative for gate decisions.  Keeping the
    contract explicit prevents reports and UI consumers from treating preliminary
    link candidates as supported job evidence.
    """

    return {
        "preliminary_detail_candidates": "Discovered link/search candidates before detail-page fetching; useful for debugging discovery breadth, not gate-pass evidence.",
        "authoritative_detail_assessments": "Post-fetch validation records with decision, failure_reason, confidence and extracted signals.",
        "supported_details": "Accepted detail pages only; this is the evidence set allowed to support detail_evidence_gate pass/apply decisions.",
        "legacy_keys_retained": ["candidate_links", "detail_assessments", "details", "supported_details"],
    }


def build_repair_outcome(
    *,
    candidate: SourceCandidate,
    gates: dict[str, dict[str, Any]],
    profile_terms: tuple[str, ...],
    location_terms: tuple[str, ...],
    max_seed_pages: int,
    max_detail_pages: int,
    enable_search_discovery: bool = True,
    max_search_queries: int = DEFAULT_SEARCH_QUERY_LIMIT,
    max_search_results: int = DEFAULT_SEARCH_RESULT_LIMIT,
    search_provider: str = DEFAULT_SEARCH_PROVIDER,
    fetcher=fetch_url,
    search_fetcher=fetch_search_results,
    tavily_fetcher=fetch_tavily_search_results,
) -> RepairOutcome:
    link_candidates, link_rejections, listing_requests, discovery_evidence = discover_link_candidates(
        candidate=candidate,
        gates=gates,
        profile_terms=profile_terms,
        location_terms=location_terms,
        max_seed_pages=max_seed_pages,
        enable_search_discovery=enable_search_discovery,
        max_search_queries=max_search_queries,
        max_search_results=max_search_results,
        search_provider=search_provider,
        fetcher=fetcher,
        search_fetcher=search_fetcher,
        tavily_fetcher=tavily_fetcher,
    )
    details, detail_rejections, detail_requests, detail_assessments = validate_detail_candidates(
        candidate=candidate,
        link_candidates=link_candidates,
        profile_terms=profile_terms,
        location_terms=location_terms,
        max_detail_pages=max_detail_pages,
        fetcher=fetcher,
    )

    requested_urls = unique_ordered([*listing_requests, *detail_requests])
    rejected_urls = unique_ordered([*link_rejections, *detail_rejections])

    preliminary_detail_candidates = [link_candidate_to_report_dict(link) for link in link_candidates]
    authoritative_detail_assessments = list(detail_assessments)
    supported_detail_evidence = [detail_evidence_to_report_dict(detail) for detail in details]

    evidence: dict[str, Any] = {
        "repair_attempted": True,
        "repair_agent": "s2w_employer_origin_detail_evidence_repair_agent",
        "repair_boundary": {
            "database_writes": True,
            "bronze_persistence": False,
            "connector_activation": False,
            "browser_automation_used": False,
            "raw_html_persisted": False,
            "max_seed_pages": max_seed_pages,
            "max_detail_pages": max_detail_pages,
            "external_search_discovery_used": enable_search_discovery,
            "max_search_queries": max_search_queries,
            "max_search_results": max_search_results,
            "search_provider": search_provider,
        },
        "decision_taxonomy": EvidenceDecision.ACCEPTED.value if details else EvidenceDecision.MANUAL_REVIEW_REQUIRED.value,
        "confidence_score": 0.96 if details else 0.62,
        "confidence_reason": "validated detail page contains profile and target signals" if details else "no validated detail page with profile and target signals after multi-origin discovery",
        **discovery_evidence,
        "search_budget_observability": {
            "search_provider": search_provider,
            "max_search_queries": max_search_queries,
            "max_search_results": max_search_results,
            "requested_search_query_count": len(discovery_evidence.get("requested_search_queries") or []),
            "estimated_provider_credit_count": (
                len(discovery_evidence.get("requested_search_queries") or [])
                if search_provider == "tavily"
                else 0
            ),
        },
        "report_contract": detail_evidence_report_contract(),
        "preliminary_detail_candidates": preliminary_detail_candidates,
        "authoritative_detail_assessments": authoritative_detail_assessments,
        "supported_detail_evidence": supported_detail_evidence,
        "detail_assessments": authoritative_detail_assessments,
        "requested_urls": list(requested_urls),
        "rejected_urls": list(rejected_urls),
        # Legacy keys are retained during the report-contract cleanup so older
        # docs/tests/UI code can migrate without losing compatibility.
        "candidate_links": preliminary_detail_candidates,
        "details": supported_detail_evidence,
        "supported_details": supported_detail_evidence,
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }

    if details:
        return RepairOutcome(
            gate_status="passed",
            decision="passed",
            stop_reason=None,
            details=details,
            rejected_urls=rejected_urls,
            requested_urls=requested_urls,
            evidence=evidence,
        )

    found_detail_candidates = bool(link_candidates)
    if found_detail_candidates:
        evidence["decision_taxonomy"] = EvidenceDecision.IMPLEMENTATION_GAP.value
        evidence["confidence_score"] = 0.82
        evidence["confidence_reason"] = (
            "concrete job-detail candidates were found, but none could be validated with both profile and target signals"
        )
        stop_reason = (
            "multi-origin repair found plausible job-detail candidates but no validated detail page with both profile and target signals"
        )
    else:
        evidence["decision_taxonomy"] = EvidenceDecision.MANUAL_REVIEW_REQUIRED.value
        evidence["confidence_score"] = 0.58
        evidence["confidence_reason"] = (
            "no concrete job-detail candidates found after persisted URLs, plausible origin hosts and search discovery"
        )
        stop_reason = (
            "multi-origin repair found no concrete detail pages with profile and target/remote signals"
        )

    return RepairOutcome(
        gate_status="manual_review_required",
        decision="manual_review_required",
        stop_reason=stop_reason,
        details=details,
        rejected_urls=rejected_urls,
        requested_urls=requested_urls,
        evidence=evidence,
    )


def repair_report_lines(candidate: SourceCandidate, outcome: RepairOutcome) -> list[str]:
    lines = [
        f"candidate_id: {candidate.id}",
        f"candidate: {candidate.company_key} | {candidate.source_name_candidate}",
        f"{DETAIL_EVIDENCE_GATE}: {outcome.gate_status} / {outcome.decision}",
    ]

    decision_taxonomy = outcome.evidence.get("decision_taxonomy") if isinstance(outcome.evidence, dict) else None
    confidence_score = outcome.evidence.get("confidence_score") if isinstance(outcome.evidence, dict) else None
    confidence_reason = outcome.evidence.get("confidence_reason") if isinstance(outcome.evidence, dict) else None
    if decision_taxonomy:
        lines.append(f"decision_taxonomy: {decision_taxonomy}")
    if confidence_score is not None:
        lines.append(f"confidence_score: {confidence_score}")
    if confidence_reason:
        lines.append(f"confidence_reason: {confidence_reason}")

    if outcome.stop_reason:
        lines.append(f"STOP: {outcome.stop_reason}")
    else:
        lines.append(f"repaired_detail_count: {len(outcome.details)}")
        lines.append("NEXT: rerun connector_candidate_agent to recompute connector_candidate_gate from repaired DB evidence.")

    return lines


class GateStateRepository:
    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def load_candidate(self, *, candidate_id: int | None, company_key: str | None) -> SourceCandidate:
        if candidate_id is None and not company_key:
            raise ValueError("Either candidate_id or company_key is required.")

        with self.conn.cursor(row_factory=dict_row) as cur:
            if candidate_id is not None:
                cur.execute(
                    """
                    select *
                    from employer_origin_source_candidates
                    where id = %s
                    """,
                    (candidate_id,),
                )
            else:
                cur.execute(
                    """
                    select *
                    from employer_origin_source_candidates
                    where company_key = %s
                    order by id desc
                    limit 1
                    """,
                    (company_key,),
                )
            row = cur.fetchone()

        if row is None:
            raise ValueError("No employer-origin source candidate found.")

        return SourceCandidate(
            id=int(row["id"]),
            company_key=str(row["company_key"]),
            company_name=str(row["company_name"]),
            candidate_url=str(row["candidate_url"]),
            source_name_candidate=str(row["source_name_candidate"]),
            source_family_candidate=str(row["source_family_candidate"]),
            source_target_candidate=row.get("source_target_candidate"),
            source_type_candidate=str(row["source_type_candidate"]),
            status=str(row["status"]),
            risk_level=str(row["risk_level"]),
        )

    def load_gates(self, candidate_id: int) -> dict[str, dict[str, Any]]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select *
                from employer_origin_candidate_gate_reviews
                where candidate_id = %s
                """,
                (candidate_id,),
            )
            rows = cur.fetchall()

        return {str(row["gate_name"]): dict(row) for row in rows}

    def record_detail_evidence_gate(
        self,
        *,
        candidate_id: int,
        outcome: RepairOutcome,
        reviewed_by: str,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                insert into employer_origin_candidate_gate_reviews (
                    candidate_id,
                    gate_order,
                    gate_name,
                    gate_status,
                    decision,
                    stop_reason,
                    evidence,
                    reviewed_by
                )
                values (%s, 8, %s, %s, %s, %s, %s, %s)
                on conflict (candidate_id, gate_name)
                do update set
                    gate_status = excluded.gate_status,
                    decision = excluded.decision,
                    stop_reason = excluded.stop_reason,
                    evidence = excluded.evidence,
                    reviewed_by = excluded.reviewed_by
                """,
                (
                    candidate_id,
                    DETAIL_EVIDENCE_GATE,
                    outcome.gate_status,
                    outcome.decision,
                    outcome.stop_reason,
                    json.dumps(outcome.evidence),
                    reviewed_by,
                ),
            )


def build_terms(args: argparse.Namespace) -> tuple[tuple[str, ...], tuple[str, ...]]:
    profile_terms = unique_ordered([*DEFAULT_PROFILE_TERMS, *(args.profile_term or [])])
    location_terms = unique_ordered([*DEFAULT_LOCATION_TERMS, *(args.location_term or [])])
    if args.target_location:
        location_terms = unique_ordered([args.target_location, *location_terms])
    return profile_terms, location_terms


def run_agent(args: argparse.Namespace) -> int:
    load_local_env_file()
    profile_terms, location_terms = build_terms(args)

    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        repo = GateStateRepository(conn)
        candidate = repo.load_candidate(candidate_id=args.candidate_id, company_key=args.company_key)
        gates = repo.load_gates(candidate.id)

        outcome = build_repair_outcome(
            candidate=candidate,
            gates=gates,
            profile_terms=profile_terms,
            location_terms=location_terms,
            max_seed_pages=args.max_seed_pages,
            max_detail_pages=args.max_detail_pages,
            enable_search_discovery=not args.disable_search_discovery,
            max_search_queries=args.max_search_queries,
            max_search_results=args.max_search_results,
            search_provider=args.search_provider,
        )

        if not args.dry_run:
            repo.record_detail_evidence_gate(
                candidate_id=candidate.id,
                outcome=outcome,
                reviewed_by=args.reviewed_by,
            )
            conn.commit()

    for line in repair_report_lines(candidate, outcome):
        print(line)

    if args.dry_run:
        print("DRY RUN: no DB gate state was changed.")

    return 0 if outcome.details else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bounded DB-backed repair agent for weak employer-origin detail evidence."
    )

    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-id", type=int)
    candidate.add_argument("--company-key")

    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--profile-term", action="append")
    parser.add_argument("--location-term", action="append")
    parser.add_argument("--max-seed-pages", type=int, default=12)
    parser.add_argument("--max-detail-pages", type=int, default=8)
    parser.add_argument("--max-search-queries", type=int, default=DEFAULT_SEARCH_QUERY_LIMIT)
    parser.add_argument("--max-search-results", type=int, default=DEFAULT_SEARCH_RESULT_LIMIT)
    parser.add_argument("--search-provider", choices=SUPPORTED_SEARCH_PROVIDERS, default=DEFAULT_SEARCH_PROVIDER)
    parser.add_argument("--disable-search-discovery", action="store_true")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
