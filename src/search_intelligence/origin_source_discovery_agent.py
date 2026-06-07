"""Read-only origin-source discovery agent foundation.

This module is deliberately stronger than the legacy URL recovery helper: it does
not treat a reachable career-like URL as sufficient. A candidate URL must also
match the company identity before it can become a selected origin-source
candidate. This prevents false matches such as ``jobs.hannover.de`` for
``Hannover Rück SE``.

The first implementation is provider-ready but does not require an external
search API. It combines deterministic company-domain candidates, existing market
evidence context and bounded HTTP probes. Later providers can add search-result
URLs without changing the scoring/decision model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import html
import re
import unicodedata
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import urlparse

from src.search_intelligence.origin_source_discovery import is_known_aggregator_domain
from src.search_intelligence.origin_url_policy import has_disallowed_source_url_shape


CORPORATE_IDENTITY_ALIASES: dict[str, tuple[str, ...]] = {
    "hannover_ruck": ("hannover re", "hannover-re", "hannover rueck", "hannover rück"),
    "e_on_grid_solutions": ("e.on", "eon", "e.on grid", "eon grid", "eon gridsolutions"),
    "technische_informationsbibliothek_tib": ("tib", "technische informationsbibliothek"),
}


def corporate_identity_aliases(company_key: str, company_name: str) -> tuple[str, ...]:
    aliases = list(CORPORATE_IDENTITY_ALIASES.get(company_key, ()))
    normalized_name = company_name.lower()

    if "hannover rück" in normalized_name or "hannover rueck" in normalized_name:
        aliases.extend(["hannover re", "hannover-re"])

    if "e.on" in normalized_name or "eon" in normalized_name:
        aliases.extend(["e.on", "eon"])

    if "tib" in normalized_name:
        aliases.extend(["tib"])

    return tuple(dict.fromkeys(alias.strip().lower() for alias in aliases if alias.strip()))


def corporate_identity_alias_tokens(company_key: str, company_name: str) -> tuple[str, ...]:
    """Return tokenized corporate aliases for identity scoring only.

    Alias phrases such as ``hannover re`` are useful for search queries, but
    URL scoring works on host/path tokens. Keeping this helper separate avoids
    feeding alias phrases into URL generation while still allowing
    ``jobs.hannover-re.com`` to match Hannover Rück.
    """

    tokens: list[str] = []
    for alias in corporate_identity_aliases(company_key, company_name):
        for token in tokenize(alias):
            if token not in LEGAL_OR_GENERIC_TOKENS and token not in tokens:
                tokens.append(token)
    return tuple(tokens)



CAREER_PATHS = (
    "/karriere",
    "/karriere/jobs",
    "/de/karriere",
    "/de/karriere/jobs",
    "/de/karriere/stellenangebote",
    "/jobs",
    "/jobsuche",
    "/careers",
    "/career",
    "/stellenangebote",
    "/stellen",
)
JOB_HOST_PREFIXES = ("jobs", "careers", "career", "karriere")
TLD_CANDIDATES = ("de", "com", "eu", "group")
SEARCH_PROVIDER_KIND = "search_provider_candidate"
GENERATED_PROVIDER_KIND = "generated_company_domain_candidate"
MARKET_EVIDENCE_PROVIDER_KIND = "market_evidence_context"

LEGAL_OR_GENERIC_TOKENS = {
    "ag",
    "aktiengesellschaft",
    "se",
    "gmbh",
    "kg",
    "co",
    "ev",
    "e",
    "v",
    "mbh",
    "group",
    "gruppe",
    "holding",
    "deutschland",
    "germany",
    "international",
    "systems",
    "solutions",
    "information",
    "communications",
    "consulting",
    "services",
    "service",
    "technology",
    "technologies",
}

LOCALITY_TOKENS = {
    "hannover",
    "berlin",
    "hamburg",
    "muenchen",
    "munich",
    "koeln",
    "cologne",
    "frankfurt",
    "duesseldorf",
    "dusseldorf",
    "bremen",
    "dortmund",
    "stuttgart",
    "leipzig",
}

CAREER_SIGNAL_TERMS = (
    "job",
    "jobs",
    "career",
    "careers",
    "karriere",
    "stellen",
    "stellenangebote",
    "vacancies",
    "bewerbung",
    "recruiting",
)

KNOWN_ATS_PROVIDER_HOST_FRAGMENTS = (
    "myworkdayjobs.com",
    "workdayjobs.com",
    "successfactors.com",
    "successfactors.eu",
    "sapsf.com",
    "sapsf.eu",
    "dvinci-hr.com",
    "softgarden.io",
    "smartrecruiters.com",
    "greenhouse.io",
    "lever.co",
    "personio.de",
    "rexx-systems.com",
    "onlyfy.jobs",
)

HTTP_ACCEPTED_STATUS_CODES = range(200, 400)
AUTO_SELECT_MIN_SCORE = 0.78
MANUAL_REVIEW_MIN_SCORE = 0.55


@dataclass(frozen=True)
class OriginSearchResult:
    url: str
    title: str = ""
    snippet: str = ""
    query: str = ""
    provider: str = "web_search"


@dataclass(frozen=True)
class OriginDiscoveryCandidate:
    url: str
    provider: str
    reason: str
    source_priority: int = 50
    evidence: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class OriginDiscoveryProbeResult:
    url: str
    final_url: str | None
    status_code: int | None
    reachable: bool
    career_like: bool
    response_bytes: int = 0
    title: str | None = None
    reason: str = "not probed"


@dataclass(frozen=True)
class OriginDiscoveryAssessment:
    candidate: OriginDiscoveryCandidate
    probe: OriginDiscoveryProbeResult | None
    normalized_url: str | None
    final_url: str | None
    domain: str | None
    identity_score: float
    career_score: float
    total_score: float
    decision: str
    risk_level: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class OriginDiscoveryResult:
    company_key: str
    company_name: str
    decision: str
    selected_url: str | None
    selected_domain: str | None
    confidence_score: float
    risk_level: str
    reason: str
    candidate_count: int
    assessed_count: int
    alternatives: tuple[OriginDiscoveryAssessment, ...]
    rejected: tuple[OriginDiscoveryAssessment, ...]
    boundary: tuple[str, ...] = (
        "read-only by default",
        "no candidate_url write",
        "no connector registration",
        "no source activation",
        "no Bronze/Silver write",
        "no scheduler change",
    )


def ascii_fold(value: str | None) -> str:
    """Normalize German/company text into predictable ASCII-ish tokens."""

    text = str(value or "").strip().lower()
    text = re.sub(r"\be[.\s_-]+on\b", "eon", text)
    text = (
        text.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
        .replace("&", " and ")
        .replace("+", " plus ")
    )
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def tokenize(value: str | None) -> tuple[str, ...]:
    folded = ascii_fold(value)
    return tuple(token for token in re.split(r"[^a-z0-9]+", folded) if len(token) >= 2)


def company_identity_tokens(*, company_key: str, company_name: str, source_family_candidate: str | None = None) -> tuple[str, ...]:
    """Return stable company identity tokens, keeping distinctive short brands.

    Legal suffixes and generic role words are removed. Locality tokens are kept
    only when paired with at least one non-local distinctive token so
    ``hannover`` alone cannot validate ``jobs.hannover.de`` for Hannover Rück.
    """

    ordered: list[str] = []
    for source in (company_key, source_family_candidate, company_name):
        for token in tokenize(source):
            if token in LEGAL_OR_GENERIC_TOKENS:
                continue
            if token in {"and", "und", "the", "der", "die", "das"}:
                continue
            if token not in ordered:
                ordered.append(token)

    non_local = [token for token in ordered if token not in LOCALITY_TOKENS]
    if non_local:
        return tuple(ordered)
    return tuple(non_local)


def acronym_tokens(company_name: str) -> tuple[str, ...]:
    candidates: list[str] = []
    for match in re.finditer(r"\(([^)]+)\)", company_name or ""):
        token = ascii_fold(match.group(1))
        token = re.sub(r"[^a-z0-9]+", "", token)
        if 2 <= len(token) <= 10:
            candidates.append(token)
    # Capture simple all-caps brand tokens such as TIB or E.ON (as eon).
    for token in re.findall(r"\b[A-ZÄÖÜ][A-ZÄÖÜ0-9.\-]{1,}\b", company_name or ""):
        normalized = re.sub(r"[^a-z0-9]+", "", ascii_fold(token))
        if 2 <= len(normalized) <= 10:
            candidates.append(normalized)
    seen: set[str] = set()
    result: list[str] = []
    for token in candidates:
        if token not in seen and token not in LEGAL_OR_GENERIC_TOKENS:
            seen.add(token)
            result.append(token)
    return tuple(result)


def _join_tokens(tokens: Sequence[str], *, max_parts: int = 4) -> str:
    return "-".join(token for token in tokens[:max_parts] if token)


def _append_url(candidates: list[OriginDiscoveryCandidate], seen: set[str], url: str, *, provider: str, reason: str, priority: int) -> None:
    candidate = url.strip()
    if not candidate or has_disallowed_source_url_shape(candidate) is not None:
        return
    if candidate in seen:
        return
    seen.add(candidate)
    candidates.append(
        OriginDiscoveryCandidate(
            url=candidate,
            provider=provider,
            reason=reason,
            source_priority=priority,
        )
    )


def generate_company_url_candidates(
    *,
    company_key: str,
    company_name: str,
    source_family_candidate: str | None = None,
    max_candidates: int = 30,
) -> tuple[OriginDiscoveryCandidate, ...]:
    """Generate bounded deterministic origin URL candidates.

    The generator deliberately keeps both corporate pages and job-host patterns,
    but scoring later decides whether a reachable result is company-related
    enough. This is why generic hosts such as jobs.hannover.de cannot win merely
    because they are reachable.
    """

    tokens = list(company_identity_tokens(
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=source_family_candidate,
    ))
    acronyms = [token for token in acronym_tokens(company_name) if token not in tokens]
    bases: list[str] = []

    for base in (
        _join_tokens(tokens),
        _join_tokens([token for token in tokens if token not in LOCALITY_TOKENS]),
        _join_tokens(tokens[:2]),
        _join_tokens(acronyms[:1]),
        re.sub(r"[^a-z0-9]+", "", ascii_fold(company_key)),
    ):
        if base and base not in bases and len(base) >= 2:
            bases.append(base)

    candidates: list[OriginDiscoveryCandidate] = []
    seen: set[str] = set()

    for base in bases:
        for tld in TLD_CANDIDATES:
            host = f"{base}.{tld}"
            for path in CAREER_PATHS:
                _append_url(
                    candidates,
                    seen,
                    f"https://www.{host}{path}",
                    provider=GENERATED_PROVIDER_KIND,
                    reason="company-token corporate career path",
                    priority=30,
                )
                _append_url(
                    candidates,
                    seen,
                    f"https://{host}{path}",
                    provider=GENERATED_PROVIDER_KIND,
                    reason="company-token corporate career path",
                    priority=32,
                )
            for prefix in JOB_HOST_PREFIXES:
                _append_url(
                    candidates,
                    seen,
                    f"https://{prefix}.{host}/",
                    provider=GENERATED_PROVIDER_KIND,
                    reason="company-token job host pattern",
                    priority=35,
                )

    return tuple(candidates[:max_candidates])


def generate_search_query_hints(
    *,
    company_name: str,
    target_location: str | None = None,
    company_key: str | None = None,
) -> tuple[str, ...]:
    """Generate bounded search queries in budget-aware priority order.

    The first query always uses the official candidate name. The second query
    should already be the strongest corporate alias when one exists, so a
    low-budget run such as ``--search-query-limit 2`` can test both the known
    name and the most relevant alternate market identity.
    """

    location = f" {target_location}" if target_location else ""
    names: list[str] = [company_name]

    if company_key:
        for alias in corporate_identity_aliases(company_key, company_name):
            cleaned = alias.strip()
            # Keep meaningful phrase/domain aliases, but avoid tiny generic
            # tokens such as ``eon`` becoming the only low-budget query.
            if len(cleaned) >= 5 and cleaned not in names:
                names.append(cleaned)

    query_templates = (
        "{quoted} Karriere Jobs{location}",
        "{quoted} Stellenangebote{location}",
        "{quoted} careers jobs",
        "{quoted} Jobs",
        "{quoted} Bewerbung Karriere",
    )

    queries: list[str] = []
    for template in query_templates:
        for name in names:
            quoted = f'"{name}"'
            query = template.format(quoted=quoted, location=location)
            if query not in queries:
                queries.append(query)

    return tuple(queries)

def search_results_to_origin_candidates(
    results: Sequence[OriginSearchResult | Mapping[str, object]],
    *,
    source_priority: int = 8,
) -> tuple[OriginDiscoveryCandidate, ...]:
    candidates: list[OriginDiscoveryCandidate] = []
    seen: set[str] = set()
    for raw in results:
        if isinstance(raw, OriginSearchResult):
            result = raw
        else:
            result = OriginSearchResult(
                url=str(raw.get("url") or raw.get("link") or ""),
                title=str(raw.get("title") or ""),
                snippet=str(raw.get("snippet") or raw.get("content") or raw.get("description") or ""),
                query=str(raw.get("query") or ""),
                provider=str(raw.get("provider") or "web_search"),
            )
        normalized = normalize_candidate_url(result.url)
        if normalized is None:
            continue
        _append_url(
            candidates,
            seen,
            normalized,
            provider=SEARCH_PROVIDER_KIND,
            reason=f"web search result from {result.provider}",
            priority=source_priority,
        )
        # `_append_url` normalizes only by the exact URL string, so attach context
        # after insertion. This keeps the function's duplicate behavior stable.
        candidates[-1] = OriginDiscoveryCandidate(
            url=candidates[-1].url,
            provider=candidates[-1].provider,
            reason=candidates[-1].reason,
            source_priority=candidates[-1].source_priority,
            evidence={
                "title": result.title,
                "snippet": result.snippet,
                "query": result.query,
                "search_provider": result.provider,
            },
        )
    return tuple(candidates)


def normalize_candidate_url(url: str | None) -> str | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    host = str(parsed.hostname or "").lower().strip(".")
    if not host:
        return None
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return parsed._replace(scheme=parsed.scheme.lower(), netloc=host, path=path, params="", query="", fragment="").geturl()


def _host_and_path_tokens(url: str) -> tuple[str, ...]:
    parsed = urlparse(url)
    return tokenize(f"{parsed.hostname or ''} {parsed.path or ''}")


def company_identity_score(
    *,
    url: str | None,
    company_key: str,
    company_name: str,
    source_family_candidate: str | None = None,
) -> tuple[float, tuple[str, ...]]:
    """Score whether URL identity matches the company.

    A host/path that contains only a locality token is explicitly rejected as a
    weak company match. This protects Hannover Rück from ``jobs.hannover.de``.
    """

    normalized = normalize_candidate_url(url)
    if normalized is None:
        return 0.0, ("invalid URL",)
    parsed = urlparse(normalized)
    host_tokens = set(tokenize(parsed.hostname or ""))
    all_url_tokens = set(_host_and_path_tokens(normalized))
    identity = set(company_identity_tokens(
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=source_family_candidate,
    ))
    identity.update(corporate_identity_alias_tokens(company_key, company_name))
    acronym = set(acronym_tokens(company_name))
    if not identity and not acronym:
        return 0.0, ("no company identity tokens available",)

    non_local_identity = {token for token in identity if token not in LOCALITY_TOKENS}
    matched_host = (identity | acronym) & host_tokens
    matched_anywhere = (identity | acronym) & all_url_tokens
    reasons: list[str] = []

    if is_known_aggregator_domain(parsed.hostname):
        return 0.0, ("known aggregator domain",)

    if matched_host:
        reasons.append("company token found in host")
    if matched_anywhere - matched_host:
        reasons.append("company token found in URL path")

    matched_non_local_host = non_local_identity & host_tokens
    matched_non_local_anywhere = non_local_identity & all_url_tokens
    matched_acronym_host = acronym & host_tokens

    if (identity & host_tokens) and not matched_non_local_host and not matched_acronym_host:
        locality_only = sorted((identity & host_tokens) & LOCALITY_TOKENS)
        if locality_only and non_local_identity:
            return 0.15, (f"only locality token matched host: {', '.join(locality_only)}",)

    score = 0.0
    if matched_non_local_host:
        score += 0.55
    if matched_acronym_host:
        score += 0.55
    if len(matched_non_local_host) >= 2:
        score += 0.20
    if matched_non_local_anywhere - matched_non_local_host:
        score += 0.15
    if not matched_non_local_host and not matched_acronym_host and matched_anywhere:
        score += 0.25
    if parsed.hostname and any(parsed.hostname.startswith(prefix + ".") for prefix in JOB_HOST_PREFIXES):
        score += 0.08
    if any(marker in normalized.lower() for marker in CAREER_SIGNAL_TERMS):
        score += 0.08

    if score == 0.0:
        reasons.append("no distinctive company token matched URL")
    return min(score, 1.0), tuple(reasons)


def _extract_title(text: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", text or "", re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()[:200]


def probe_result_from_http_response(url: str, response: object) -> OriginDiscoveryProbeResult:
    status_code = int(getattr(response, "status_code", 0) or 0)
    final_url = str(getattr(response, "url", "") or url)
    text = str(getattr(response, "text", "") or "")
    content = getattr(response, "content", b"") or b""
    reachable = status_code in HTTP_ACCEPTED_STATUS_CODES
    haystack = f"{final_url} {text[:8000]}".lower()
    career_like = any(term in haystack for term in CAREER_SIGNAL_TERMS)
    reason = "reachable career/job-like URL" if reachable and career_like else f"status={status_code}; career_like={career_like}"
    return OriginDiscoveryProbeResult(
        url=url,
        final_url=final_url,
        status_code=status_code,
        reachable=reachable,
        career_like=career_like,
        response_bytes=len(content),
        title=_extract_title(text),
        reason=reason,
    )



def is_known_ats_provider_domain(hostname: str | None) -> bool:
    host = str(hostname or "").lower().strip(".")
    return any(fragment in host for fragment in KNOWN_ATS_PROVIDER_HOST_FRAGMENTS)


def _candidate_context_text(candidate: OriginDiscoveryCandidate) -> str:
    evidence = candidate.evidence or {}
    return " ".join(
        str(evidence.get(key) or "")
        for key in ("title", "snippet", "query", "search_provider")
    ).strip()


def _context_identity_bonus(
    *,
    candidate: OriginDiscoveryCandidate,
    company_key: str,
    company_name: str,
    source_family_candidate: str | None,
    hostname: str | None,
) -> tuple[float, tuple[str, ...]]:
    if candidate.provider != SEARCH_PROVIDER_KIND:
        return 0.0, ()
    context = _candidate_context_text(candidate)
    if not context:
        return 0.0, ()

    context_tokens = set(tokenize(context))
    identity = set(company_identity_tokens(
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=source_family_candidate,
    ))
    identity.update(corporate_identity_alias_tokens(company_key, company_name))
    acronym = set(acronym_tokens(company_name))
    non_local_identity = {token for token in identity if token not in LOCALITY_TOKENS}
    matched = (non_local_identity | acronym) & context_tokens
    if not matched:
        return 0.0, ()

    bonus = 0.24
    reasons = ["company token found in search result context"]
    if is_known_ats_provider_domain(hostname):
        bonus += 0.18
        reasons.append("known ATS/provider domain with company search-result context")
    if len(matched) >= 2:
        bonus += 0.08
        reasons.append("multiple company tokens found in search result context")
    return min(bonus, 0.45), tuple(reasons)


def _context_career_bonus(candidate: OriginDiscoveryCandidate) -> tuple[float, tuple[str, ...]]:
    if candidate.provider != SEARCH_PROVIDER_KIND:
        return 0.0, ()
    context = ascii_fold(_candidate_context_text(candidate))
    if not context:
        return 0.0, ()
    if any(term in context for term in CAREER_SIGNAL_TERMS):
        return 0.15, ("career/job signal found in search result context",)
    return 0.0, ()

def assess_origin_candidate(
    candidate: OriginDiscoveryCandidate,
    *,
    company_key: str,
    company_name: str,
    source_family_candidate: str | None = None,
    probe: Callable[[str], OriginDiscoveryProbeResult] | None = None,
) -> OriginDiscoveryAssessment:
    normalized = normalize_candidate_url(candidate.url)
    reasons: list[str] = []
    if normalized is None:
        return OriginDiscoveryAssessment(candidate, None, None, None, None, 0.0, 0.0, 0.0, "reject", "blocked", ("invalid URL",))

    parsed = urlparse(normalized)
    if parsed.scheme != "https":
        return OriginDiscoveryAssessment(candidate, None, normalized, normalized, parsed.hostname, 0.0, 0.0, 0.0, "reject", "high", ("HTTPS required",))
    if is_known_aggregator_domain(parsed.hostname):
        return OriginDiscoveryAssessment(candidate, None, normalized, normalized, parsed.hostname, 0.0, 0.0, 0.0, "reject", "medium", ("known aggregator domain",))

    identity, identity_reasons = company_identity_score(
        url=normalized,
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=source_family_candidate,
    )
    reasons.extend(identity_reasons)
    context_bonus, context_reasons = _context_identity_bonus(
        candidate=candidate,
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=source_family_candidate,
        hostname=parsed.hostname,
    )
    if context_bonus:
        identity = min(identity + context_bonus, 1.0)
        reasons.extend(context_reasons)

    probe_result: OriginDiscoveryProbeResult | None = None
    final_url = normalized
    career_score = 0.20 if any(marker in normalized.lower() for marker in CAREER_SIGNAL_TERMS) else 0.0
    context_career_bonus, context_career_reasons = _context_career_bonus(candidate)
    if context_career_bonus:
        career_score += context_career_bonus
        reasons.extend(context_career_reasons)
    if probe is not None:
        probe_result = probe(normalized)
        final_url = probe_result.final_url or normalized
        if final_url != normalized:
            redirected_identity, redirected_reasons = company_identity_score(
                url=final_url,
                company_key=company_key,
                company_name=company_name,
                source_family_candidate=source_family_candidate,
            )
            if redirected_identity < identity:
                reasons.append("redirect weakened company identity match")
            identity = min(identity, redirected_identity) if redirected_identity < 0.45 else max(identity, redirected_identity)
            reasons.extend(redirected_reasons)
        if probe_result.career_like:
            career_score += 0.30
        reasons.append(probe_result.reason)

    total = round(min(identity + career_score, 1.0), 3)
    domain = urlparse(final_url).hostname if final_url else parsed.hostname

    if identity < 0.45:
        return OriginDiscoveryAssessment(candidate, probe_result, normalized, final_url, domain, identity, career_score, total, "reject", "medium", tuple(reasons + ["company identity match too weak"]))
    if probe is not None and probe_result and not probe_result.reachable:
        return OriginDiscoveryAssessment(candidate, probe_result, normalized, final_url, domain, identity, career_score, total, "reject", "medium", tuple(reasons + ["URL not reachable in bounded probe"]))
    if total >= AUTO_SELECT_MIN_SCORE:
        return OriginDiscoveryAssessment(candidate, probe_result, normalized, final_url, domain, identity, career_score, total, "select_candidate", "low", tuple(reasons))
    if total >= MANUAL_REVIEW_MIN_SCORE:
        return OriginDiscoveryAssessment(candidate, probe_result, normalized, final_url, domain, identity, career_score, total, "manual_review_candidate", "medium", tuple(reasons))
    return OriginDiscoveryAssessment(candidate, probe_result, normalized, final_url, domain, identity, career_score, total, "reject", "medium", tuple(reasons + ["score below manual-review threshold"]))


def discover_origin_source(
    *,
    company_key: str,
    company_name: str,
    source_family_candidate: str | None = None,
    market_evidence_urls: Sequence[str] = (),
    search_result_candidates: Sequence[OriginDiscoveryCandidate] = (),
    search_results: Sequence[OriginSearchResult | Mapping[str, object]] = (),
    target_location: str | None = None,
    probe: Callable[[str], OriginDiscoveryProbeResult] | None = None,
    max_generated_candidates: int = 30,
) -> OriginDiscoveryResult:
    candidates: list[OriginDiscoveryCandidate] = []
    seen: set[str] = set()
    for item in tuple(search_result_candidates) + search_results_to_origin_candidates(search_results):
        normalized = normalize_candidate_url(item.url)
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        candidates.append(
            OriginDiscoveryCandidate(
                url=normalized,
                provider=item.provider,
                reason=item.reason,
                source_priority=item.source_priority,
                evidence=dict(item.evidence),
            )
        )
    for url in market_evidence_urls:
        _append_url(
            candidates,
            seen,
            url,
            provider=MARKET_EVIDENCE_PROVIDER_KIND,
            reason="existing market evidence URL; expected to be rejected when aggregator-backed",
            priority=80,
        )
    for item in generate_company_url_candidates(
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=source_family_candidate,
        max_candidates=max_generated_candidates,
    ):
        _append_url(candidates, seen, item.url, provider=item.provider, reason=item.reason, priority=item.source_priority)

    assessments = tuple(
        sorted(
            (
                assess_origin_candidate(
                    item,
                    company_key=company_key,
                    company_name=company_name,
                    source_family_candidate=source_family_candidate,
                    probe=probe,
                )
                for item in candidates
            ),
            key=lambda item: (
                item.decision != "select_candidate",
                1 if is_known_aggregator_domain(item.domain) else 0,
                -item.identity_score,
                -item.total_score,
                item.candidate.source_priority,
            ),
        )
    )
    selected = next((item for item in assessments if item.decision == "select_candidate"), None)
    manual = tuple(item for item in assessments if item.decision == "manual_review_candidate")
    rejected = tuple(item for item in assessments if item.decision == "reject")

    if selected:
        return OriginDiscoveryResult(
            company_key=company_key,
            company_name=company_name,
            decision="origin_url_candidate_selected",
            selected_url=selected.final_url or selected.normalized_url,
            selected_domain=selected.domain,
            confidence_score=selected.total_score,
            risk_level=selected.risk_level,
            reason="selected reachable career-like URL with plausible company identity match",
            candidate_count=len(candidates),
            assessed_count=len(assessments),
            alternatives=assessments[:10],
            rejected=rejected[:10],
        )

    if manual:
        best = manual[0]
        return OriginDiscoveryResult(
            company_key=company_key,
            company_name=company_name,
            decision="manual_review_required",
            selected_url=None,
            selected_domain=None,
            confidence_score=best.total_score,
            risk_level="medium",
            reason="some URL candidates are company-related but not strong enough for automatic selection",
            candidate_count=len(candidates),
            assessed_count=len(assessments),
            alternatives=manual[:10],
            rejected=rejected[:10],
        )

    return OriginDiscoveryResult(
        company_key=company_key,
        company_name=company_name,
        decision="not_found",
        selected_url=None,
        selected_domain=None,
        confidence_score=max((item.total_score for item in assessments), default=0.0),
        risk_level="unknown",
        reason="no reachable career-like URL with plausible company identity match was found",
        candidate_count=len(candidates),
        assessed_count=len(assessments),
        alternatives=(),
        rejected=rejected[:10],
    )


def assessment_to_json(assessment: OriginDiscoveryAssessment) -> dict[str, object]:
    return {
        "url": assessment.candidate.url,
        "provider": assessment.candidate.provider,
        "provider_reason": assessment.candidate.reason,
        "normalized_url": assessment.normalized_url,
        "final_url": assessment.final_url,
        "domain": assessment.domain,
        "identity_score": assessment.identity_score,
        "career_score": assessment.career_score,
        "total_score": assessment.total_score,
        "decision": assessment.decision,
        "risk_level": assessment.risk_level,
        "reasons": list(assessment.reasons),
        "probe": None if assessment.probe is None else {
            "url": assessment.probe.url,
            "final_url": assessment.probe.final_url,
            "status_code": assessment.probe.status_code,
            "reachable": assessment.probe.reachable,
            "career_like": assessment.probe.career_like,
            "response_bytes": assessment.probe.response_bytes,
            "title": assessment.probe.title,
            "reason": assessment.probe.reason,
        },
    }


def result_to_json(result: OriginDiscoveryResult) -> dict[str, object]:
    return {
        "company_key": result.company_key,
        "company_name": result.company_name,
        "decision": result.decision,
        "selected_url": result.selected_url,
        "selected_domain": result.selected_domain,
        "confidence_score": result.confidence_score,
        "risk_level": result.risk_level,
        "reason": result.reason,
        "candidate_count": result.candidate_count,
        "assessed_count": result.assessed_count,
        "alternatives": [assessment_to_json(item) for item in result.alternatives],
        "rejected": [assessment_to_json(item) for item in result.rejected],
        "boundary": list(result.boundary),
        "search_query_hints": list(generate_search_query_hints(company_name=result.company_name, company_key=result.company_key)),
    }
