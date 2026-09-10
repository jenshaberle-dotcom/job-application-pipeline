"""Provider-neutral evidence extraction for official careers/job surfaces.

The extractor deliberately reads URL-bearing HTML attributes only. It never scans
arbitrary script/text blobs for provider names, never executes page code, and does
not make any source-validity decision. The result is bounded evidence consumed by
the existing Employer-Origin discovery/proof layers.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit


MAX_SURFACE_URLS = 96
CAREER_URL_MARKERS = (
    "career",
    "careers",
    "job",
    "jobs",
    "karriere",
    "stellen",
    "stellenangebote",
    "vacanc",
    "recruit",
)


@dataclass(frozen=True)
class AtsProviderDefinition:
    family: str
    host_suffixes: tuple[str, ...]
    public_feed_kind: str | None = None


# Data, not branching logic. New families extend this registry without creating an
# employer-specific connector. Endpoint/feed probing is a later bounded step and
# remains independent from source proof.
ATS_PROVIDER_DEFINITIONS = (
    AtsProviderDefinition("workday", ("myworkdayjobs.com", "workdayjobs.com"), "workday_cxs"),
    AtsProviderDefinition("successfactors", ("successfactors.com", "successfactors.eu", "sapsf.com", "sapsf.eu")),
    AtsProviderDefinition("greenhouse", ("greenhouse.io",), "greenhouse_board_api"),
    AtsProviderDefinition("lever", ("lever.co",), "lever_postings_api"),
    AtsProviderDefinition("ashby", ("ashbyhq.com",), "ashby_job_board_api"),
    AtsProviderDefinition("smartrecruiters", ("smartrecruiters.com",), "smartrecruiters_postings_api"),
    AtsProviderDefinition("workable", ("workable.com",), "workable_widget_api"),
    AtsProviderDefinition("recruitee", ("recruitee.com",), "recruitee_offers_api"),
    AtsProviderDefinition("personio", ("personio.de", "personio.com"), "personio_xml"),
    AtsProviderDefinition("bamboohr", ("bamboohr.com",), "bamboohr_careers_api"),
    AtsProviderDefinition("breezy", ("breezy.hr",), "breezy_json"),
    AtsProviderDefinition("teamtailor", ("teamtailor.com",), "teamtailor_jobs_json"),
    AtsProviderDefinition("rippling", ("rippling.com",), "rippling_board_api"),
    AtsProviderDefinition("dvinci", ("dvinci-hr.com",)),
    AtsProviderDefinition("softgarden", ("softgarden.io",)),
    AtsProviderDefinition("rexx", ("rexx-systems.com",)),
    AtsProviderDefinition("onlyfy", ("onlyfy.jobs",)),
)


@dataclass(frozen=True)
class AtsFingerprint:
    family: str
    url: str
    host: str
    public_feed_kind: str | None
    source_attribute: str


@dataclass(frozen=True)
class OriginSurfaceEvidence:
    canonical_url: str | None
    jobspace_urls: tuple[str, ...]
    ats_fingerprints: tuple[AtsFingerprint, ...]


class _SurfaceUrlParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.canonical_url: str | None = None
        self.urls: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.casefold()
        values = {str(key).casefold(): value for key, value in attrs if key}

        if tag_name == "link":
            rel = str(values.get("rel") or "").casefold().split()
            href = values.get("href")
            if "canonical" in rel and href and self.canonical_url is None:
                self.canonical_url = urljoin(self.base_url, href)

        attribute = None
        if tag_name in {"a", "link"}:
            attribute = "href"
        elif tag_name in {"script", "iframe", "frame", "source"}:
            attribute = "src"
        elif tag_name == "form":
            attribute = "action"

        if attribute:
            value = values.get(attribute)
            if value:
                self.urls.append((urljoin(self.base_url, value), f"{tag_name}:{attribute}"))


def _normalize_http_url(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = urlsplit(raw)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.casefold().strip(".")
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.casefold(), host + port, path, parsed.query, ""))


def _host_matches(host: str, suffix: str) -> bool:
    normalized = suffix.casefold().strip(".")
    return host == normalized or host.endswith("." + normalized)


def fingerprint_ats_url(url: str, *, source_attribute: str = "url") -> AtsFingerprint | None:
    normalized = _normalize_http_url(url)
    if normalized is None:
        return None
    host = str(urlsplit(normalized).hostname or "").casefold()
    for definition in ATS_PROVIDER_DEFINITIONS:
        if any(_host_matches(host, suffix) for suffix in definition.host_suffixes):
            return AtsFingerprint(
                family=definition.family,
                url=normalized,
                host=host,
                public_feed_kind=definition.public_feed_kind,
                source_attribute=source_attribute,
            )
    return None


def _career_like_url(url: str) -> bool:
    parsed = urlsplit(url)
    haystack = f"{parsed.hostname or ''} {parsed.path or ''}".casefold()
    return any(marker in haystack for marker in CAREER_URL_MARKERS)


def extract_origin_surface_evidence(
    *,
    html: str,
    base_url: str,
    max_urls: int = MAX_SURFACE_URLS,
) -> OriginSurfaceEvidence:
    """Extract bounded canonical/jobspace/ATS evidence from already-fetched HTML."""

    parser = _SurfaceUrlParser(base_url)
    try:
        parser.feed(html or "")
    except Exception:
        return OriginSurfaceEvidence(None, (), ())

    canonical = _normalize_http_url(parser.canonical_url)
    jobspace_urls: list[str] = []
    ats_matches: list[AtsFingerprint] = []
    seen_urls: set[str] = set()
    seen_ats: set[tuple[str, str]] = set()

    for raw_url, source_attribute in parser.urls[: max(1, max_urls)]:
        normalized = _normalize_http_url(raw_url)
        if normalized is None or normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        ats = fingerprint_ats_url(normalized, source_attribute=source_attribute)
        if ats is not None:
            ats_key = (ats.family, ats.url)
            if ats_key not in seen_ats:
                ats_matches.append(ats)
                seen_ats.add(ats_key)
        if ats is not None or _career_like_url(normalized):
            jobspace_urls.append(normalized)

    return OriginSurfaceEvidence(
        canonical_url=canonical,
        jobspace_urls=tuple(jobspace_urls),
        ats_fingerprints=tuple(ats_matches),
    )


__all__ = [
    "ATS_PROVIDER_DEFINITIONS",
    "AtsFingerprint",
    "AtsProviderDefinition",
    "OriginSurfaceEvidence",
    "extract_origin_surface_evidence",
    "fingerprint_ats_url",
]
