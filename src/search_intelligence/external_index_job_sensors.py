"""Bounded external-index job evidence for the job-first Census.

This module never fetches a job board. It accepts metadata returned by a separately
selected public-search transport, validates the expected board URL shape, derives
only minimal job evidence, hashes the board reference, and discards raw URL/title/
snippet metadata before returning a MarketJobObservation.

A source being present here is not direct-platform automation authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Sequence
from urllib.parse import urlparse

from src.search_intelligence.employer_discovery_census import MarketJobObservation


@dataclass(frozen=True)
class ExternalIndexSourceSpec:
    source: str
    search_site: str
    host_suffix: str
    url_hint: str
    extraction_status: str


@dataclass(frozen=True)
class ExternalIndexQuery:
    source: str
    search_term: str
    location_signal: str | None
    query: str


SOURCE_SPECS: dict[str, ExternalIndexSourceSpec] = {
    "goodjobs": ExternalIndexSourceSpec(
        source="goodjobs",
        search_site="goodjobs.eu",
        host_suffix="goodjobs.eu",
        url_hint="goodjobs.eu/jobs/",
        extraction_status="fixture_qualified",
    ),
    "xing": ExternalIndexSourceSpec(
        source="xing",
        search_site="xing.com",
        host_suffix="xing.com",
        url_hint="xing.com/jobs/",
        extraction_status="fixture_qualified",
    ),
    "get_in_it": ExternalIndexSourceSpec(
        source="get_in_it",
        search_site="get-in-it.de",
        host_suffix="get-in-it.de",
        url_hint="get-in-it.de/jobsuche/p",
        extraction_status="fixture_qualified",
    ),
    "meinestadt": ExternalIndexSourceSpec(
        source="meinestadt",
        search_site="jobs.meinestadt.de",
        host_suffix="jobs.meinestadt.de",
        url_hint="jobs.meinestadt.de/",
        extraction_status="shape_only",
    ),
    "jobvector": ExternalIndexSourceSpec(
        source="jobvector",
        search_site="jobvector.de",
        host_suffix="jobvector.de",
        url_hint="jobvector.de/",
        extraction_status="shape_only",
    ),
}

EXTERNAL_INDEX_SOURCES = tuple(SOURCE_SPECS)
FIXTURE_QUALIFIED_SOURCES = tuple(
    source
    for source, spec in SOURCE_SPECS.items()
    if spec.extraction_status == "fixture_qualified"
)

_LEGAL_ENTITY = (
    r"(?:GmbH(?:\s*&\s*Co\.?\s*KG)?|AG|SE|KGaA|KG|"
    r"UG(?:\s*\(haftungsbeschränkt\))?|e\.?\s*V\.?|Ltd\.?|LLC|Inc\.?)"
)


def _normalized(values: Sequence[str], *, limit: int) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        rendered = " ".join(str(value or "").split()).strip()
        if not rendered:
            continue
        key = rendered.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(rendered)
        if len(result) >= limit:
            break
    return tuple(result)


def build_external_index_queries(
    *,
    source: str,
    search_terms: Sequence[str],
    location_signals: Sequence[str] = (),
    max_terms: int = 4,
    max_locations: int = 2,
) -> tuple[ExternalIndexQuery, ...]:
    if source not in SOURCE_SPECS:
        raise ValueError(f"Unsupported Census external-index source: {source}")
    spec = SOURCE_SPECS[source]
    terms = _normalized(search_terms, limit=max(1, max_terms))
    locations = _normalized(location_signals, limit=max(0, max_locations))
    if not terms:
        return ()

    choices: tuple[str | None, ...] = locations or (None,)
    queries: list[ExternalIndexQuery] = []
    for term in terms:
        for location in choices:
            parts = [f'"{spec.url_hint}"', f'"{term}"']
            if location:
                parts.append(f'"{location}"')
            parts.append("Germany")
            queries.append(
                ExternalIndexQuery(
                    source=source,
                    search_term=term,
                    location_signal=location,
                    query=" ".join(parts),
                )
            )
    return tuple(queries)


def _host_allowed(source: str, host: str) -> bool:
    suffix = SOURCE_SPECS[source].host_suffix
    normalized = host.casefold().split(":", 1)[0].strip(".")
    return normalized == suffix or normalized.endswith("." + suffix)


def classify_external_index_result_shape(*, source: str, url: object) -> str:
    if source not in SOURCE_SPECS:
        raise ValueError(f"Unsupported Census external-index source: {source}")
    raw = str(url or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "invalid_url"
    if not _host_allowed(source, parsed.netloc):
        return "unexpected_host"

    path = parsed.path.casefold()
    if source == "goodjobs":
        return "accepted_shape" if path.startswith("/jobs/") else "unexpected_path"
    if source == "xing":
        return (
            "accepted_shape"
            if re.fullmatch(r"/jobs/.+-\d+", path)
            else "unexpected_path"
        )
    if source == "get_in_it":
        return (
            "accepted_shape"
            if re.match(r"^/jobsuche/p\d+(?:/|$)", path)
            else "unexpected_path"
        )

    # meinestadt/jobvector stay cohort-visible but parser authority is not yet
    # proven. Shape-only sources cannot create MarketJobObservation rows.
    return "shape_only_unqualified"


def _clean(value: object, *, limit: int = 500) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _clean_company(value: str) -> str | None:
    rendered = _clean(value, limit=160).strip(" |–—-,:;")
    if not rendered or len(rendered.split()) > 10:
        return None
    return rendered


def _remote_signal(text: str) -> bool:
    folded = text.casefold()
    return any(
        token in folded
        for token in (
            "remote",
            "home-office",
            "home office",
            "homeoffice",
            "mobiles arbeiten",
        )
    )


def _metadata_location(text: str) -> str | None:
    folded = text.casefold()
    remote = _remote_signal(text)
    if "hannover" in folded:
        return "Hannover remote" if remote else "Hannover"
    if "hanover" in folded:
        return "Hanover remote" if remote else "Hanover"
    if "deutschland" in folded:
        return "Deutschland remote" if remote else "Deutschland"
    if "germany" in folded:
        return "Germany remote" if remote else "Germany"
    if remote:
        return "Remote"
    for city in (
        "berlin",
        "hamburg",
        "munich",
        "münchen",
        "cologne",
        "köln",
        "frankfurt",
        "dublin",
        "london",
    ):
        if city in folded:
            return city
    return None


def _goodjobs_fields(title: str, snippet: str) -> tuple[str, str | None, str | None]:
    cleaned = re.sub(r"\s*\|\s*GoodJobs\s*$", "", title, flags=re.IGNORECASE)
    if " - " not in cleaned:
        return cleaned, None, _metadata_location(snippet)
    job_title, company = cleaned.rsplit(" - ", 1)
    return job_title.strip(), _clean_company(company), _metadata_location(snippet)


def _xing_fields(title: str, snippet: str) -> tuple[str, str | None, str | None]:
    cleaned = re.sub(r"\s*\|\s*XING Jobs\s*$", "", title, flags=re.IGNORECASE)
    location = None
    match = re.match(r"^(?P<title>.+?)\s+in\s+(?P<location>[^|]{2,80})$", cleaned)
    if match:
        job_title = match.group("title").strip()
        location = _clean(match.group("location"), limit=80)
    else:
        job_title = cleaned.strip()

    patterns = (
        rf"^(?P<company>[A-Za-zÄÖÜäöüß0-9&.'’+ -]{{1,100}}\b{_LEGAL_ENTITY})\b",
        rf"\bbei\s+(?P<company>[A-Za-zÄÖÜäöüß0-9&.'’+ -]{{1,100}}\b{_LEGAL_ENTITY})\b",
        rf"(?P<company>[A-Za-zÄÖÜäöüß0-9&.'’+ -]{{1,100}}\b{_LEGAL_ENTITY})\s+sucht\b",
    )
    company = None
    for pattern in patterns:
        found = re.search(pattern, snippet, flags=re.IGNORECASE)
        if found:
            company = _clean_company(found.group("company"))
            if company:
                break
    return job_title, company, location or _metadata_location(snippet)


def _get_in_it_fields(title: str, snippet: str) -> tuple[str, str | None, str | None]:
    parts = [part.strip() for part in title.split("|")]
    if len(parts) >= 3 and "get in it" in parts[-1].casefold():
        return parts[0], _clean_company(parts[1]), _metadata_location(snippet)
    return title, None, _metadata_location(snippet)


def accept_external_index_result(
    *,
    source: str,
    provider: str,
    url: object,
    title: object,
    snippet: object,
    observed_at_utc: str,
) -> MarketJobObservation | None:
    """Derive minimal Census evidence from transient search-index metadata."""
    del provider  # transport identity is run telemetry, not job truth.
    if classify_external_index_result_shape(source=source, url=url) != "accepted_shape":
        return None
    if SOURCE_SPECS[source].extraction_status != "fixture_qualified":
        return None

    raw_url = str(url).strip()
    title_signal = _clean(title, limit=300)
    snippet_signal = _clean(snippet, limit=500)
    if not title_signal:
        return None

    if source == "goodjobs":
        job_title, company, location = _goodjobs_fields(title_signal, snippet_signal)
    elif source == "xing":
        job_title, company, location = _xing_fields(title_signal, snippet_signal)
    elif source == "get_in_it":
        job_title, company, location = _get_in_it_fields(title_signal, snippet_signal)
    else:
        return None

    if not job_title or not company:
        return None

    reference_hash = hashlib.sha256(raw_url.encode("utf-8")).hexdigest()
    return MarketJobObservation(
        source=source,
        title=job_title,
        company_name=company,
        location=location,
        observed_at_utc=observed_at_utc,
        reference=f"external-index:{reference_hash}",
        description="",
        remote_signal=_remote_signal(f"{title_signal} {snippet_signal}"),
    )
