"""Conservative discovery-only market sensors for commercial aggregators.

LinkedIn and Indeed are intentionally *not* ingestion connectors here. The sensor
builds bounded site-restricted web-search queries and accepts only minimal public
search-result evidence from the expected platform host/path.

No platform page is fetched by this module. No login/browser automation is used.
No result has Employer-Origin, Bronze, Silver, Product, ranking, Fit or application
authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable, Mapping, Sequence
from urllib.parse import urlparse


SENSOR_SCHEMA = "job_application_pipeline.conservative_market_sensor.v2"
SENSOR_PLATFORMS = ("linkedin", "indeed")

_PLATFORM_SPECS: dict[str, dict[str, object]] = {
    "linkedin": {
        "site_query": "site:linkedin.com/jobs/view",
        "host_suffixes": ("linkedin.com",),
        "path_markers": ("/jobs/view/",),
    },
    "indeed": {
        "site_query": "site:de.indeed.com/viewjob",
        "host_suffixes": ("indeed.com",),
        "path_markers": ("/viewjob",),
    },
}

BOUNDARY = {
    "discovery_only": True,
    "direct_platform_http_requests": 0,
    "login_automation": 0,
    "browser_automation": 0,
    "captcha_bypass": 0,
    "raw_job_content_persistence": 0,
    "database_writes": 0,
    "bronze_writes": 0,
    "silver_writes": 0,
    "product_authority": 0,
    "ranking_authority": 0,
    "fit_authority": 0,
    "application_authority": 0,
    "aggregator_url_is_not_origin_url": True,
    "aggregator_job_identity_discarded_before_origin_learning": True,
}

_LEGAL_ENTITY_SUFFIX = (
    r"(?:GmbH(?:\s*&\s*Co\.?\s*KG)?|AG|SE|KGaA|KG|"
    r"UG(?:\s*\(haftungsbeschränkt\))?|e\.?\s*V\.?|Ltd\.?|LLC|Inc\.?|"
    r"Gruppe|Group)"
)


@dataclass(frozen=True)
class SensorQuery:
    sensor: str
    search_term: str
    location_signal: str | None
    query: str


@dataclass(frozen=True)
class SensorObservation:
    schema: str
    sensor: str
    provider: str
    query: str
    url: str
    host: str
    title_signal: str
    snippet_signal: str
    observed_at_utc: str
    search_term: str | None = None
    location_signal: str | None = None
    observed_company_signal: str | None = None
    company_signal_status: str = "unknown"
    company_signal_rule: str | None = None
    authority: str = "discovery_only"

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["boundary"] = BOUNDARY
        return payload


def _normalized_values(values: Iterable[object], *, limit: int) -> tuple[str, ...]:
    if limit <= 0:
        return ()
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = " ".join(str(value or "").split()).strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
        if len(result) >= limit:
            break
    return tuple(result)


def _clean_company_signal(value: object, *, max_words: int = 8) -> str | None:
    rendered = " ".join(str(value or "").split()).strip(" \t\r\n|–—-,:;")
    if not rendered or len(rendered) > 160:
        return None
    if len(rendered.split()) > max_words:
        return None
    return rendered


def _indeed_title_base(title_signal: str) -> str:
    return re.sub(
        r"\s+-\s+(?:\d{5}\b.*|Deutschland\b.*|Indeed\.com\b.*)$",
        "",
        title_signal,
        flags=re.IGNORECASE,
    ).strip()


def extract_observed_company_signal(
    *,
    sensor: str,
    title: object,
    snippet: object,
) -> tuple[str | None, str | None]:
    """Extract only explicit employer text from provider result metadata.

    The extractor intentionally has no fuzzy/company-dictionary fallback. When the
    result metadata does not carry a bounded, structurally explicit company signal,
    the observation remains unattributed for later review.
    """

    title_signal = " ".join(str(title or "").split())[:300]
    snippet_signal = " ".join(str(snippet or "").split())[:500]

    if sensor == "linkedin":
        match = re.match(
            r"^(?P<company>.+?)\s+(?:sucht|hiring)\s+",
            title_signal,
            flags=re.IGNORECASE,
        )
        if match:
            company = _clean_company_signal(match.group("company"))
            if company:
                return company, "linkedin_title_company_prefix"

        match = re.search(
            r"\sbei\s+(?P<company>.+?)(?:\s+[—–|-]\s+|\s+\|\s*LinkedIn$|$)",
            title_signal,
            flags=re.IGNORECASE,
        )
        if match:
            company = _clean_company_signal(match.group("company"))
            if company:
                return company, "linkedin_title_bei"

        match = re.search(
            rf"\bbei\s+(?P<company>[A-Za-zÄÖÜäöüß0-9&.'’+ -]{{1,80}}\b{_LEGAL_ENTITY_SUFFIX})"
            r"\s+in\s+[A-ZÄÖÜ]",
            snippet_signal,
            flags=re.IGNORECASE,
        )
        if match:
            company = _clean_company_signal(match.group("company"))
            if company:
                return company, "linkedin_snippet_bei_legal_in"

        match = re.search(
            r"\bwir\s+bei\s+(?P<company>[A-Z][A-Z0-9&.+-]{1,30})\b",
            snippet_signal,
        )
        if match:
            company = _clean_company_signal(match.group("company"))
            if company:
                return company, "linkedin_snippet_wir_bei_acronym"

        match = re.search(
            rf"\s-\s+(?P<company>[A-Za-zÄÖÜäöüß0-9&.'’+ -]{{1,80}}\b{_LEGAL_ENTITY_SUFFIX})$",
            title_signal,
            flags=re.IGNORECASE,
        )
        if match:
            company = _clean_company_signal(match.group("company"))
            if company:
                return company, "linkedin_title_legal_suffix"

    if sensor == "indeed":
        title_base = _indeed_title_base(title_signal)
        if title_base and snippet_signal.casefold().startswith(title_base.casefold()):
            remainder = snippet_signal[len(title_base) :].strip(" \t\r\n|–—-,:;")
            match = re.match(
                r"^(?P<company>.+?)\s+[·•]\s+\d(?:[.,]\d)?\b",
                remainder,
            )
            if match:
                company = _clean_company_signal(match.group("company"))
                if company:
                    return company, "indeed_title_prefix_rating"

        match = re.search(
            r"\bjoin\s+(?P<company>[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9&.'’+ -]{1,60}?)['’]s\b",
            snippet_signal,
        )
        if match:
            company = _clean_company_signal(match.group("company"))
            if company:
                return company, "indeed_snippet_join_possessive"

        match = re.search(
            rf"\bbei\s+(?P<company>[A-Za-zÄÖÜäöüß0-9&.'’+ -]{{1,80}}\b{_LEGAL_ENTITY_SUFFIX})\b",
            snippet_signal,
            flags=re.IGNORECASE,
        )
        if match:
            company = _clean_company_signal(match.group("company"))
            if company:
                return company, "indeed_snippet_bei_legal"

        match = re.search(
            r"\bwir\s+bei\s+(?P<company>[A-Z][A-Z0-9&.+-]{1,30})\b",
            snippet_signal,
        )
        if match:
            company = _clean_company_signal(match.group("company"))
            if company:
                return company, "indeed_snippet_wir_bei_acronym"

        match = re.search(
            rf"\s-\s+(?P<company>[A-Za-zÄÖÜäöüß0-9&.'’+ -]{{1,80}}\b{_LEGAL_ENTITY_SUFFIX})$",
            title_signal,
            flags=re.IGNORECASE,
        )
        if match:
            company = _clean_company_signal(match.group("company"))
            if company:
                return company, "indeed_title_legal_suffix"

    return None, None


def build_sensor_queries(
    *,
    sensor: str,
    search_terms: Sequence[str],
    location_signals: Sequence[str] = (),
    max_terms: int = 4,
    max_locations: int = 2,
) -> tuple[SensorQuery, ...]:
    if sensor not in _PLATFORM_SPECS:
        raise ValueError(f"Unsupported conservative market sensor: {sensor}")

    terms = _normalized_values(search_terms, limit=max(1, max_terms))
    locations = _normalized_values(location_signals, limit=max(0, max_locations))
    if not terms:
        return ()

    site_query = str(_PLATFORM_SPECS[sensor]["site_query"])
    result: list[SensorQuery] = []
    location_choices: tuple[str | None, ...] = locations or (None,)

    for term in terms:
        for location in location_choices:
            pieces = [site_query, f'"{term}"']
            if location:
                pieces.append(f'"{location}"')
            pieces.append("Germany")
            result.append(
                SensorQuery(
                    sensor=sensor,
                    search_term=term,
                    location_signal=location,
                    query=" ".join(pieces),
                )
            )
    return tuple(result)


def _host_allowed(sensor: str, host: str) -> bool:
    suffixes = tuple(str(v) for v in _PLATFORM_SPECS[sensor]["host_suffixes"])
    normalized = host.casefold().split(":", 1)[0].strip(".")
    return any(
        normalized == suffix or normalized.endswith("." + suffix)
        for suffix in suffixes
    )


def _path_allowed(sensor: str, path: str) -> bool:
    markers = tuple(str(v) for v in _PLATFORM_SPECS[sensor]["path_markers"])
    normalized = path.casefold()
    return any(marker in normalized for marker in markers)


def accept_provider_result(
    *,
    sensor: str,
    provider: str,
    query: str,
    url: object,
    title: object,
    snippet: object,
    observed_at_utc: str,
    search_term: str | None = None,
    location_signal: str | None = None,
    snippet_limit: int = 500,
) -> SensorObservation | None:
    if sensor not in _PLATFORM_SPECS:
        raise ValueError(f"Unsupported conservative market sensor: {sensor}")

    raw_url = str(url or "").strip()
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if not _host_allowed(sensor, parsed.netloc):
        return None
    if not _path_allowed(sensor, parsed.path):
        return None

    title_signal = " ".join(str(title or "").split())[:300]
    snippet_signal = " ".join(str(snippet or "").split())[: max(0, snippet_limit)]
    observed_company_signal, company_signal_rule = extract_observed_company_signal(
        sensor=sensor,
        title=title_signal,
        snippet=snippet_signal,
    )

    return SensorObservation(
        schema=SENSOR_SCHEMA,
        sensor=sensor,
        provider=str(provider or "unknown"),
        query=query,
        url=raw_url,
        host=parsed.netloc.casefold(),
        title_signal=title_signal,
        snippet_signal=snippet_signal,
        observed_at_utc=observed_at_utc,
        search_term=search_term,
        location_signal=location_signal,
        observed_company_signal=observed_company_signal,
        company_signal_status="explicit" if observed_company_signal else "unknown",
        company_signal_rule=company_signal_rule,
    )


def deduplicate_observations(
    observations: Iterable[SensorObservation],
) -> tuple[SensorObservation, ...]:
    by_identity: dict[tuple[str, str], SensorObservation] = {}
    for observation in observations:
        key = (observation.sensor, observation.url)
        by_identity.setdefault(key, observation)
    return tuple(by_identity[key] for key in sorted(by_identity))


def boundary_report() -> Mapping[str, object]:
    return {
        "schema": SENSOR_SCHEMA,
        "platforms": list(SENSOR_PLATFORMS),
        "boundary": dict(BOUNDARY),
    }
