"""Bounded relevance-evidence helpers for employer-origin candidates.

The relevance probe is deliberately bounded, but no longer treats a weak
listing/preview page as the final source of truth. It can discover job-detail
links from same-/related-host pages, JSON-LD JobPosting snippets and bounded
search pages. Accepted autonomous evidence can produce DB-backed learning
signals such as Germany-wide location wording or job-detail URL patterns.
"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import json
import re
from typing import Callable, Iterable, Sequence
from urllib.parse import quote_plus, urljoin, urlparse

PROFILE_TERMS = (
    "data engineer",
    "data engineering",
    "databricks",
    "data & analytics",
    "data analytics",
    "analytics engineer",
    "analytics",
    "daten",
    "data",
    "sql",
    "python",
    "business intelligence",
    "bi",
)

# Terms that make a job Germany-/remote-relevant for the user's current search
# scope. "hybrid" alone is intentionally weak; it helps as supporting evidence
# but does not replace a target-location or Germany-wide signal.
REMOTE_OR_GERMANY_TERMS = (
    "deutschlandweit",
    "bundesweit",
    "standort: deutschlandweit",
    "standort deutschlandweit",
    "germany wide",
    "remote deutschland",
    "remote germany",
    "homeoffice",
    "home office",
    "mobiles arbeiten",
    "mobile work",
    "remote",
)

SUPPORTING_FLEXIBILITY_TERMS = (
    "hybrid",
    "flexibilität",
    "flexibility",
    "mobil und flexibel",
)

JOB_OR_SEARCH_PATH_TERMS = (
    "/job/",
    "/jobs/",
    "/stellen/",
    "/stellenangebote/",
    "/search/",
    "jobid=",
    "job/",
)

SEARCH_QUERIES = (
    "Data Engineer",
    "Databricks",
    "Data Analytics",
)


@dataclass(frozen=True)
class RelevanceSignals:
    profile_hits: tuple[str, ...]
    location_hits: tuple[str, ...]
    remote_hits: tuple[str, ...]
    flexibility_hits: tuple[str, ...]

    @property
    def has_profile_evidence(self) -> bool:
        return bool(self.profile_hits)

    @property
    def has_target_or_remote_evidence(self) -> bool:
        return bool(self.location_hits or self.remote_hits)

    @property
    def is_relevant(self) -> bool:
        return self.has_profile_evidence and self.has_target_or_remote_evidence


@dataclass(frozen=True)
class RelevanceProbeResult:
    url: str
    final_url: str | None
    status_code: int | None
    accepted: bool
    reason: str
    signals: RelevanceSignals
    title: str | None = None
    response_bytes: int = 0


@dataclass(frozen=True)
class LearnedSignal:
    signal_type: str
    signal_value: str
    signal_strength: str
    confidence: float
    reason: str


class _LinkAndTitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.title_parts: list[str] = []
        self._inside_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._inside_title = True
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(value.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._inside_title = False

    def handle_data(self, data: str) -> None:
        if self._inside_title and data.strip():
            self.title_parts.append(data.strip())

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def term_hits(text: str, terms: Iterable[str]) -> tuple[str, ...]:
    normalized = normalize_text(text)
    hits: list[str] = []
    for term in terms:
        normalized_term = normalize_text(term)
        if not normalized_term:
            continue
        if normalized_term in {"+ weitere", "+ weitere standorte"}:
            if re.search(r"\+\s*\d+\s+weitere", normalized) and term not in hits:
                hits.append(term)
            continue
        if normalized_term in normalized and term not in hits:
            hits.append(term)
    return tuple(hits)


def relevance_signals(
    text: str,
    *,
    target_location: str,
    source_target: str | None = None,
    promoted_profile_terms: Iterable[str] = (),
    promoted_location_terms: Iterable[str] = (),
    promoted_remote_terms: Iterable[str] = (),
) -> RelevanceSignals:
    location_terms = tuple(
        term
        for term in (
            target_location,
            source_target,
            "hannover" if normalize_text(target_location) == "hannover" else "",
        )
        if str(term or "").strip()
    )
    profile_terms = tuple(dict.fromkeys([*PROFILE_TERMS, *tuple(promoted_profile_terms)]))
    promoted_locations = tuple(term for term in promoted_location_terms if str(term or "").strip())
    promoted_remote = tuple(term for term in promoted_remote_terms if str(term or "").strip())
    return RelevanceSignals(
        profile_hits=term_hits(text, profile_terms),
        location_hits=term_hits(text, tuple(dict.fromkeys([*location_terms, *promoted_locations]))),
        remote_hits=term_hits(text, tuple(dict.fromkeys([*REMOTE_OR_GERMANY_TERMS, *promoted_remote]))),
        flexibility_hits=term_hits(text, SUPPORTING_FLEXIBILITY_TERMS),
    )


def relevance_decision(signals: RelevanceSignals) -> str:
    if signals.is_relevant:
        return "relevant"
    if signals.profile_hits or signals.location_hits or signals.remote_hits:
        return "insufficient_evidence"
    return "not_relevant"


def relevance_confidence(signals: RelevanceSignals) -> float:
    score = 0.0
    if signals.profile_hits:
        score += min(0.45, 0.22 + 0.08 * len(signals.profile_hits))
    if signals.location_hits:
        score += 0.30
    if signals.remote_hits:
        score += min(0.40, 0.22 + 0.06 * len(signals.remote_hits))
    if signals.flexibility_hits:
        score += 0.05
    if signals.is_relevant:
        score = max(score, 0.72)
    return round(min(score, 0.95), 4)


def _host_tokens(hostname: str | None) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9]+", str(hostname or "").lower())
        if len(token) >= 3
    }


def _source_tokens(source_family_candidate: str | None, company_key: str | None = None) -> set[str]:
    generic = {"career", "careers", "source", "origin", "employer", "jobs", "job", "hannover"}
    raw = f"{source_family_candidate or ''} {company_key or ''}"
    return {
        token
        for token in re.split(r"[^a-z0-9]+", raw.lower())
        if len(token) >= 3 and token not in generic
    }


def _is_related_host(hostname: str | None, allowed_hosts: set[str], source_tokens: set[str]) -> bool:
    host = str(hostname or "").lower()
    if not host:
        return False
    if host in allowed_hosts:
        return True
    if host.startswith("www.") and host[4:] in allowed_hosts:
        return True
    return bool(source_tokens & _host_tokens(host))


def extract_candidate_links(
    *,
    base_url: str,
    body: str,
    source_family_candidate: str | None,
    company_key: str | None,
    max_links: int,
) -> tuple[str, ...]:
    parser = _LinkAndTitleParser()
    parser.feed(body or "")
    base_host = urlparse(base_url).netloc.lower()
    allowed_hosts = {base_host, base_host[4:] if base_host.startswith("www.") else base_host}
    tokens = _source_tokens(source_family_candidate, company_key)

    links: list[str] = []
    seen: set[str] = set()
    for href in parser.links:
        absolute = urljoin(base_url, href).split("#", 1)[0]
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if not _is_related_host(parsed.netloc.lower(), allowed_hosts, tokens):
            continue
        lowered = absolute.lower()
        if not any(term in lowered for term in JOB_OR_SEARCH_PATH_TERMS):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)
        if len(links) >= max_links:
            break
    return tuple(links)


def _json_values(value: object) -> Iterable[object]:
    if isinstance(value, dict):
        for child in value.values():
            yield from _json_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _json_values(child)
    else:
        yield value


def extract_json_ld_job_urls(*, base_url: str, body: str, max_links: int = 6) -> tuple[str, ...]:
    """Extract bounded JobPosting URLs from JSON-LD snippets when present."""

    urls: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        body or "",
        flags=re.IGNORECASE | re.DOTALL,
    ):
        payload = match.group(1).strip()
        if not payload:
            continue
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue
        flat_text = normalize_text(json.dumps(parsed, ensure_ascii=False))
        if "jobposting" not in flat_text and "hiringorganization" not in flat_text:
            continue
        for value in _json_values(parsed):
            if not isinstance(value, str):
                continue
            if not (value.startswith("http") or value.startswith("/")):
                continue
            absolute = urljoin(base_url, value).split("#", 1)[0]
            lowered = absolute.lower()
            if not any(term in lowered for term in JOB_OR_SEARCH_PATH_TERMS):
                continue
            if absolute not in seen:
                seen.add(absolute)
                urls.append(absolute)
            if len(urls) >= max_links:
                return tuple(urls)
    return tuple(urls)


def generated_search_urls(
    base_url: str,
    *,
    max_urls: int = 6,
    promoted_url_path_patterns: Iterable[str] = (),
) -> tuple[str, ...]:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ()
    root = f"{parsed.scheme}://{parsed.netloc}"
    urls: list[str] = []
    seen: set[str] = set()
    promoted_patterns = {str(pattern or "").strip().lower() for pattern in promoted_url_path_patterns}
    pattern_templates = [
        "/search/?q={query}",
        "/search/?q={query}&locationsearch=deutschland",
        "/jobs/?q={query}",
    ]
    if "/stellen/..." in promoted_patterns:
        pattern_templates.extend(["/stellen/?q={query}", "/stellenangebote/?q={query}"])
    if "/vacancy/..." in promoted_patterns:
        pattern_templates.extend(["/vacancies/?q={query}", "/vacancy/?q={query}"])
    if "/career/..." in promoted_patterns:
        pattern_templates.extend(["/careers/?q={query}", "/career/?q={query}"])

    for query in SEARCH_QUERIES:
        for template in pattern_templates:
            url = f"{root}{template.format(query=quote_plus(query))}"
            if url not in seen:
                seen.add(url)
                urls.append(url)
            if len(urls) >= max_urls:
                return tuple(urls)
    return tuple(urls)


def build_probe_url_queue(
    *,
    candidate_url: str,
    initial_body: str = "",
    source_family_candidate: str | None = None,
    company_key: str | None = None,
    max_links: int = 8,
    promoted_url_path_patterns: Iterable[str] = (),
) -> tuple[str, ...]:
    queue: list[str] = []
    seen: set[str] = set()

    def add(url: str) -> None:
        clean = str(url or "").strip()
        if not clean or clean in seen:
            return
        seen.add(clean)
        queue.append(clean)

    add(candidate_url)

    detail_candidates = (
        extract_json_ld_job_urls(base_url=candidate_url, body=initial_body, max_links=max_links)
        + extract_candidate_links(
            base_url=candidate_url,
            body=initial_body,
            source_family_candidate=source_family_candidate,
            company_key=company_key,
            max_links=max_links,
        )
    )
    for url in sorted(detail_candidates, key=lambda value: 0 if is_probable_job_detail_url(value) else 1):
        add(url)

    for url in generated_search_urls(candidate_url, promoted_url_path_patterns=promoted_url_path_patterns):
        add(url)
    return tuple(queue[: max_links + 1])


def is_probable_job_detail_url(url: str) -> bool:
    path = urlparse(str(url or "")).path.lower()
    return any(marker in path for marker in ("/job/", "/stellen/", "/vacancy/"))


def job_detail_url_pattern(url: str) -> dict[str, str | None]:
    parsed = urlparse(url)
    path = parsed.path or ""
    path_pattern: str | None = None
    if "/job/" in path:
        path_pattern = "/job/..."
    elif "/jobs/" in path:
        path_pattern = "/jobs/..."
    elif "/stellen/" in path or "/stellenangebote/" in path:
        path_pattern = "/stellen/..."
    elif "/search/" in path:
        path_pattern = "/search/..."
    return {"host": parsed.netloc.lower() or None, "path_pattern": path_pattern}


def _signal_strength(signal_type: str, value: str) -> tuple[str, float, str]:
    normalized = normalize_text(value)
    if signal_type == "remote_or_germany":
        if normalized in {
            "deutschlandweit",
            "bundesweit",
            "standort: deutschlandweit",
            "standort deutschlandweit",
            "remote deutschland",
            "remote germany",
        }:
            return "strong", 0.90, "Germany-wide or explicit Germany-remote signal"
        if normalized in {"remote", "homeoffice", "home office", "mobiles arbeiten", "mobile work"}:
            return "medium", 0.70, "remote/flexible-work signal; useful but may require context"
    if signal_type == "profile":
        if normalized in {"data engineer", "data engineering", "databricks", "data & analytics", "analytics engineer"}:
            return "strong", 0.85, "strong profile-fit signal for the search profile"
        return "medium", 0.60, "supporting profile-fit signal"
    if signal_type == "target_location":
        return "strong", 0.85, "explicit target-location signal"
    if signal_type == "flexibility":
        if normalized == "hybrid":
            return "weak", 0.45, "hybrid alone is not sufficient; useful only with target/Germany-wide evidence"
        return "weak", 0.50, "supporting flexibility signal"
    if signal_type == "job_detail_path_pattern":
        return "medium", 0.65, "accepted job-detail path pattern from autonomous evidence"
    return "weak", 0.40, "unclassified supporting signal"


def learned_signals_from_result(result: RelevanceProbeResult) -> tuple[LearnedSignal, ...]:
    """Return learning candidates from accepted autonomous evidence only."""

    if not result.accepted:
        return ()

    items: list[tuple[str, str]] = []
    items.extend(("profile", hit) for hit in result.signals.profile_hits)
    items.extend(("target_location", hit) for hit in result.signals.location_hits)
    items.extend(("remote_or_germany", hit) for hit in result.signals.remote_hits)
    items.extend(("flexibility", hit) for hit in result.signals.flexibility_hits)

    pattern = job_detail_url_pattern(result.final_url or result.url)
    if pattern.get("path_pattern"):
        items.append(("job_detail_path_pattern", str(pattern["path_pattern"])))

    learned: list[LearnedSignal] = []
    seen: set[tuple[str, str]] = set()
    for signal_type, value in items:
        key = (signal_type, normalize_text(value))
        if not key[1] or key in seen:
            continue
        seen.add(key)
        strength, confidence, reason = _signal_strength(signal_type, value)
        learned.append(
            LearnedSignal(
                signal_type=signal_type,
                signal_value=value,
                signal_strength=strength,
                confidence=confidence,
                reason=reason,
            )
        )
    return tuple(learned)


def probe_result_from_http_response(
    url: str,
    response: object,
    *,
    target_location: str,
    source_target: str | None = None,
    promoted_profile_terms: Iterable[str] = (),
    promoted_location_terms: Iterable[str] = (),
    promoted_remote_terms: Iterable[str] = (),
) -> RelevanceProbeResult:
    status_code = int(getattr(response, "status_code", 0) or 0)
    final_url = str(getattr(response, "url", "") or url)
    text = str(getattr(response, "text", "") or "")
    content = getattr(response, "content", b"") or b""
    parser = _LinkAndTitleParser()
    parser.feed(text)
    signals = relevance_signals(
        text,
        target_location=target_location,
        source_target=source_target,
        promoted_profile_terms=promoted_profile_terms,
        promoted_location_terms=promoted_location_terms,
        promoted_remote_terms=promoted_remote_terms,
    )
    accepted = 200 <= status_code < 400 and signals.is_relevant
    if accepted:
        reason = "profile and target/remote evidence found"
    elif not signals.has_profile_evidence:
        reason = "missing profile evidence"
    elif not signals.has_target_or_remote_evidence:
        reason = "missing target-location or remote/Germany-wide evidence"
    else:
        reason = f"status={status_code}"
    return RelevanceProbeResult(
        url=url,
        final_url=final_url,
        status_code=status_code,
        accepted=accepted,
        reason=reason,
        signals=signals,
        title=parser.title or None,
        response_bytes=len(content),
    )


def select_relevance_evidence(
    urls: Sequence[str],
    *,
    probe: Callable[[str], RelevanceProbeResult],
) -> tuple[RelevanceProbeResult | None, tuple[RelevanceProbeResult, ...]]:
    results: list[RelevanceProbeResult] = []
    for url in urls:
        result = probe(url)
        results.append(result)
        if result.accepted:
            return result, tuple(results)
    return None, tuple(results)
