"""Pure contracts for adaptive, non-repeating origin-source search.

The module models the small set of actions a human uses when literal search
fails: preserve the displayed brand, derive domain-safe brand surfaces, search
without an over-specific location first, inspect likely career hosts, and only
then ask an LLM for novel hypotheses. Every transition must add a novel query,
URL, or observed domain. Repeating the same state is explicitly rejected.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import re
import unicodedata
from typing import Iterable, Mapping
from urllib.parse import urlparse

from src.search_intelligence.origin_source_discovery import is_known_aggregator_domain
from src.search_intelligence.origin_url_policy import has_disallowed_source_url_shape

LEGAL_SUFFIXES = {
    "ag",
    "se",
    "gmbh",
    "kg",
    "mbh",
    "co",
    "ohg",
    "ug",
    "inc",
    "ltd",
    "limited",
    "corp",
    "corporation",
}
CAREER_HOST_PREFIXES = ("career", "careers", "jobs", "karriere")
BRAND_TLDS = ("org", "de", "com", "eu", "group")


def _ascii(value: str) -> str:
    text = str(value or "").strip().lower()
    text = (
        text.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _strip_legal_suffixes(value: str) -> str:
    tokens = [
        token
        for token in re.split(r"[^a-z0-9&+@]+", _ascii(value))
        if token and token not in LEGAL_SUFFIXES
    ]
    return " ".join(tokens).strip()


def _domain_surface(value: str, *, joiner: str = "") -> str:
    text = _strip_legal_suffixes(value)
    text = text.replace("&", f"{joiner}and{joiner}")
    text = text.replace("+", f"{joiner}plus{joiner}")
    text = text.replace("@", f"{joiner}at{joiner}")
    parts = [part for part in re.split(r"[^a-z0-9]+", text) if part]
    return joiner.join(parts)


def brand_surface_variants(
    *,
    company_name: str,
    company_key: str | None = None,
) -> tuple[str, ...]:
    """Return bounded human-readable and domain-safe brand variants."""

    original = _strip_legal_suffixes(company_name) or str(company_name or "").strip()
    candidates = [
        original,
        _domain_surface(company_name),
        _domain_surface(company_name, joiner="-"),
    ]
    if company_key:
        key = _ascii(company_key)
        candidates.extend(
            [
                re.sub(r"[^a-z0-9]+", "", key),
                re.sub(r"[^a-z0-9]+", "-", key).strip("-"),
            ]
        )

    result: list[str] = []
    for candidate in candidates:
        cleaned = re.sub(r"\s+", " ", str(candidate or "").strip())
        if len(cleaned) < 2 or cleaned in result:
            continue
        result.append(cleaned)
    return tuple(result[:6])


def deterministic_brand_url_hypotheses(
    *,
    company_name: str,
    company_key: str | None = None,
    maximum: int = 24,
) -> tuple[str, ...]:
    """Generate high-value career-host hypotheses before path combinatorics."""

    bases = [
        item
        for item in brand_surface_variants(
            company_name=company_name,
            company_key=company_key,
        )
        if re.fullmatch(r"[a-z0-9-]+", item) and not item.isdigit()
    ]
    urls: list[str] = []
    for base in bases:
        for tld in BRAND_TLDS:
            for prefix in CAREER_HOST_PREFIXES:
                url = f"https://{prefix}.{base}.{tld}/"
                if url not in urls:
                    urls.append(url)
                    if len(urls) >= maximum:
                        return tuple(urls)
    return tuple(urls)


def initial_adaptive_queries(
    *,
    company_name: str,
    company_key: str | None = None,
    target_location: str | None = None,
    maximum: int = 6,
) -> tuple[str, ...]:
    """Build a bounded query sequence in human-search order."""

    variants = brand_surface_variants(
        company_name=company_name,
        company_key=company_key,
    )
    original = variants[0] if variants else company_name
    domain_variants = [item for item in variants[1:] if item != original]
    queries: list[str] = [
        f'"{original}" Karriere',
        f'"{original}" careers',
        f'"{original}" offizielle Karriereseite',
    ]
    for variant in domain_variants:
        queries.extend(
            [
                f'"{variant}" Karriere',
                f'"{variant}" careers',
            ]
        )
    if target_location:
        queries.append(f'"{original}" Jobs {target_location}')

    unique: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = normalize_query(query)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(query)
        if len(unique) >= maximum:
            break
    return tuple(unique)


def domain_followup_queries(
    domains: Iterable[str],
    *,
    maximum: int = 4,
) -> tuple[str, ...]:
    queries: list[str] = []
    for raw in domains:
        host = str(raw or "").lower().strip(".")
        if host.startswith("www."):
            host = host[4:]
        if not host or is_known_aggregator_domain(host):
            continue
        for term in ("career", "jobs"):
            query = f"site:{host} {term}"
            if query not in queries:
                queries.append(query)
            if len(queries) >= maximum:
                return tuple(queries)
    return tuple(queries)


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", str(query or "").strip().lower())


def normalize_url(url: str) -> str | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    if is_known_aggregator_domain(parsed.hostname):
        return None
    if has_disallowed_source_url_shape(raw) is not None:
        return None
    host = str(parsed.hostname).lower().strip(".")
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=host,
        path=path,
        params="",
        query="",
        fragment="",
    ).geturl()


@dataclass
class SearchProgressLedger:
    attempted_queries: set[str] = field(default_factory=set)
    attempted_urls: set[str] = field(default_factory=set)
    observed_domains: set[str] = field(default_factory=set)
    fingerprints: list[str] = field(default_factory=list)

    def novel_queries(self, queries: Iterable[str]) -> tuple[str, ...]:
        result: list[str] = []
        for raw in queries:
            normalized = normalize_query(raw)
            if not normalized or normalized in self.attempted_queries:
                continue
            self.attempted_queries.add(normalized)
            result.append(str(raw).strip())
        return tuple(result)

    def novel_urls(self, urls: Iterable[str]) -> tuple[str, ...]:
        result: list[str] = []
        for raw in urls:
            normalized = normalize_url(raw)
            if normalized is None or normalized in self.attempted_urls:
                continue
            self.attempted_urls.add(normalized)
            parsed = urlparse(normalized)
            if parsed.hostname:
                self.observed_domains.add(parsed.hostname.lower())
            result.append(normalized)
        return tuple(result)

    def record_state(self, payload: Mapping[str, object]) -> tuple[str, bool]:
        urls: set[str] = set()
        for key in ("selected_url", "recommended_url"):
            value = payload.get(key)
            if isinstance(value, str):
                normalized = normalize_url(value)
                if normalized:
                    urls.add(normalized)
        for key in ("search_results", "alternatives", "rejected"):
            rows = payload.get(key)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, Mapping):
                    continue
                value = row.get("final_url") or row.get("url")
                if isinstance(value, str):
                    normalized = normalize_url(value)
                    if normalized:
                        urls.add(normalized)
        state = {
            "decision": payload.get("decision"),
            "confidence_score": payload.get("confidence_score"),
            "urls": sorted(urls),
        }
        digest = hashlib.sha256(
            json.dumps(state, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        progressed = not self.fingerprints or self.fingerprints[-1] != digest
        self.fingerprints.append(digest)
        return digest, progressed

    def to_json(self) -> dict[str, object]:
        return {
            "attempted_queries": sorted(self.attempted_queries),
            "attempted_urls": sorted(self.attempted_urls),
            "observed_domains": sorted(self.observed_domains),
            "state_fingerprints": list(self.fingerprints),
            "repeated_state_detected": len(self.fingerprints)
            != len(set(self.fingerprints)),
        }


@dataclass(frozen=True)
class SearchHypothesisSet:
    queries: tuple[str, ...]
    urls: tuple[str, ...]
    rationale: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


def validate_search_hypotheses(
    payload: Mapping[str, object],
    *,
    ledger: SearchProgressLedger,
    max_queries: int = 3,
    max_urls: int = 3,
) -> SearchHypothesisSet:
    raw_queries = payload.get("queries")
    raw_urls = payload.get("urls")
    if not isinstance(raw_queries, list) or not isinstance(raw_urls, list):
        raise ValueError("search hypothesis payload requires query and URL arrays")
    queries = ledger.novel_queries(str(item) for item in raw_queries[:max_queries])
    urls = ledger.novel_urls(str(item) for item in raw_urls[:max_urls])
    return SearchHypothesisSet(
        queries=queries,
        urls=urls,
        rationale=str(payload.get("rationale") or "").strip()[:600],
    )
