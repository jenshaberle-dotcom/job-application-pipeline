from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row


REQUIRED_GATE = "connector_candidate_gate"


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
class ConnectorImplementation:
    module_path: Path
    test_path: Path
    docs_path: Path
    module_content: str
    test_content: str
    docs_content: str


def snake_case(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", normalized).strip("_")


def pascal_case(value: str) -> str:
    return "".join(part.capitalize() for part in snake_case(value).split("_") if part)


def module_name_for(candidate: SourceCandidate) -> str:
    return snake_case(candidate.source_family_candidate or candidate.company_key)


def class_name_for(candidate: SourceCandidate) -> str:
    return f"{pascal_case(candidate.source_family_candidate or candidate.company_key)}Connector"


def safe_tuple(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return tuple(result)


def extract_spec_from_gate(gate: dict[str, Any]) -> dict[str, Any]:
    evidence = gate.get("evidence") or {}
    spec = evidence.get("connector_candidate_spec") or {}
    if not isinstance(spec, dict):
        return {}
    return spec


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
    "/jobsuche/",
    "/karriere/jobsuche/",
    "/stellenangebote/",
    "/offene-stellen/",
    "/stellen-finden/",
    "/karriere/offene-stellen/",
    "/karriere/jobs/",
)


def concrete_job_detail_url(url: str) -> bool:
    """Return True only for concrete job-detail URLs, not career roots or legal pages."""
    if not url.startswith(("http://", "https://")):
        return False

    parsed = urlparse(url)
    path = re.sub(r"/+", "/", parsed.path.casefold()).rstrip("/")
    if not path:
        return False

    if any(fragment in path for fragment in NON_JOB_DETAIL_URL_FRAGMENTS):
        return False

    last_segment = path.rsplit("/", 1)[-1]
    if last_segment in GENERIC_DETAIL_LAST_SEGMENTS:
        return False

    if not any(marker in f"{path}/" for marker in JOB_DETAIL_PATH_MARKERS):
        return False

    if len(last_segment) < 6:
        return False

    return "-" in last_segment or "_" in last_segment or any(ch.isdigit() for ch in last_segment)

def extract_detail_urls_from_spec(spec: dict[str, Any]) -> tuple[str, ...]:
    detail = spec.get("detail_evidence") or {}
    urls = detail.get("detail_urls") or []
    return safe_tuple(
        [
            url
            for url in urls
            if str(url).startswith(("http://", "https://")) and concrete_job_detail_url(str(url))
        ]
    )


def rejected_detail_urls_from_spec(spec: dict[str, Any]) -> tuple[str, ...]:
    detail = spec.get("detail_evidence") or {}
    urls = detail.get("detail_urls") or []
    return safe_tuple(
        [
            url
            for url in urls
            if str(url).startswith(("http://", "https://")) and not concrete_job_detail_url(str(url))
        ]
    )


def default_profile_terms() -> tuple[str, ...]:
    return (
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


def default_target_terms(target: str | None) -> tuple[str, ...]:
    terms = [target or "hannover", "remote", "deutschland", "bundesweit", "hybrid"]
    return safe_tuple(terms)


def source_host(url: str) -> str:
    return urlparse(url).netloc.lower()


def source_domain_set(listing_url: str, detail_urls: tuple[str, ...]) -> tuple[str, ...]:
    hosts = [source_host(listing_url), *(source_host(url) for url in detail_urls)]
    return safe_tuple([host for host in hosts if host])


def connector_module_content(
    *,
    candidate: SourceCandidate,
    spec: dict[str, Any],
) -> str:
    module_name = module_name_for(candidate)
    class_name = class_name_for(candidate)
    detail_urls = extract_detail_urls_from_spec(spec)
    domains = source_domain_set(candidate.candidate_url, detail_urls)
    target_terms = default_target_terms(candidate.source_target_candidate)
    profile_terms = default_profile_terms()

    return f"""from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

from src.connectors.base import JobSourceConnector, RawJobRecord, SearchProfile, SearchTerm
from src.connectors.capabilities import SourceCapabilities


SOURCE_NAME = {candidate.source_name_candidate!r}
SOURCE_FAMILY = {candidate.source_family_candidate!r}
SOURCE_TARGET = {candidate.source_target_candidate!r}
SOURCE_TYPE = {candidate.source_type_candidate!r}
COMPANY_NAME = {candidate.company_name!r}
LISTING_URL = {candidate.candidate_url!r}
ALLOWED_HOSTS = {domains!r}
KNOWN_DETAIL_URLS = {detail_urls!r}
REQUEST_TIMEOUT_SECONDS = 20
MAX_DETAIL_PAGES = 3
USER_AGENT = (
    "job-application-pipeline-{module_name}-connector-candidate/0.1 "
    "(bounded; max 3 detail pages; relevance gated)"
)

PROFILE_TERMS = {profile_terms!r}
TARGET_LOCATION_TERMS = {target_terms!r}
EXCLUSION_TERMS = (
    "duales-studium",
    "duales studium",
    "ausbildung",
    "werkstudent",
    "werkstudierende",
    "praktikum",
    "trainee",
)


@dataclass(frozen=True)
class CandidateLink:
    url: str
    path: str
    text: str
    location_terms: tuple[str, ...]
    profile_terms: tuple[str, ...]
    recommendation: str
    reason: str


@dataclass(frozen=True)
class DetailPage:
    url: str
    final_url: str
    status_code: int
    title: str
    text: str
    html_bytes: int


class LinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return

        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")
        if not href:
            return

        self._current_href = urljoin(self.base_url, href)
        self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current_href:
            self.links.append((self._current_href, normalize_whitespace(" ".join(self._text_parts))))
            self._current_href = None
            self._text_parts = []


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


class {class_name}(JobSourceConnector):
    # Bounded employer-origin connector candidate generated from DB-backed approval-gated connector evidence.
    # This module does not activate recurring ingestion or approve Bronze persistence.

    source_name = SOURCE_NAME

    capabilities = SourceCapabilities(
        supports_keyword=False,
        supports_location=False,
        supports_radius=False,
        supports_employment_type=False,
        supports_remote_filter=False,
        supports_pagination=False,
        supports_full_fetch=True,
    )

    def __init__(
        self,
        listing_url: str = LISTING_URL,
        max_detail_pages: int = MAX_DETAIL_PAGES,
        fetcher=None,
    ) -> None:
        self.listing_url = listing_url
        self.max_detail_pages = max_detail_pages
        self.fetcher = fetcher or fetch_url

    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        listing_html, final_url, status_code = self.fetcher(self.listing_url)
        if status_code >= 400:
            raise RuntimeError(f"{{SOURCE_NAME}} listing request failed with status {{status_code}}")

        candidates = select_detail_candidates(
            extract_candidate_links(listing_html, final_url),
            limit=self.max_detail_pages,
        )

        observed_at_utc = datetime.now(UTC).isoformat()
        records: list[RawJobRecord] = []

        for candidate in candidates:
            detail_html, detail_final_url, detail_status = self.fetcher(candidate.url)
            detail = parse_detail_page(
                url=candidate.url,
                final_url=detail_final_url,
                status_code=detail_status,
                html=detail_html,
            )

            if not detail_supports_record(candidate, detail):
                continue

            records.append(
                build_raw_job_record(
                    candidate=candidate,
                    detail=detail,
                    requested_listing_url=final_url,
                    observed_at_utc=observed_at_utc,
                )
            )

        return records, final_url


def fetch_url(url: str) -> tuple[str, str, int]:
    response = requests.get(
        url,
        headers={{"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1"}},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text, response.url, response.status_code


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\\s+", " ", value).strip()


def normalize_text(value: str | None) -> str:
    value = normalize_whitespace(value).casefold()
    value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return value


def find_terms(value: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    lowered = normalize_text(value)
    matches: list[str] = []

    for term in terms:
        if normalize_text(term) in lowered and term not in matches:
            matches.append(term)

    return tuple(matches)


def allowed_host(url: str) -> bool:
    return urlparse(url).netloc.lower() in ALLOWED_HOSTS


def has_known_detail_url(url: str) -> bool:
    return url.split("#", 1)[0] in KNOWN_DETAIL_URLS


def extract_candidate_links(html: str, base_url: str) -> list[CandidateLink]:
    parser = LinkExtractor(base_url)
    parser.feed(html)

    candidates: list[CandidateLink] = []
    seen: set[str] = set()

    for url, text in parser.links:
        clean_url = url.split("#", 1)[0]
        if clean_url in seen:
            continue
        seen.add(clean_url)

        if not allowed_host(clean_url):
            continue

        parsed = urlparse(clean_url)
        path = parsed.path
        blob = " ".join([clean_url, path, text])

        if find_terms(blob, EXCLUSION_TERMS):
            continue

        profile_terms = find_terms(blob, PROFILE_TERMS)
        location_terms = find_terms(blob, TARGET_LOCATION_TERMS)

        if has_known_detail_url(clean_url):
            recommendation = "known_detail_candidate_from_gate_evidence"
            reason = "URL was approved by DB-backed detail evidence gate."
        elif profile_terms and location_terms:
            recommendation = "strong_listing_candidate_for_review"
            reason = "Listing has profile and target/remote signals."
        elif profile_terms or location_terms:
            recommendation = "weak_listing_candidate_for_review"
            reason = "Listing has partial relevance evidence."
        else:
            continue

        candidates.append(
            CandidateLink(
                url=clean_url,
                path=path,
                text=text,
                location_terms=location_terms,
                profile_terms=profile_terms,
                recommendation=recommendation,
                reason=reason,
            )
        )

    return candidates


def select_detail_candidates(candidates: list[CandidateLink], limit: int) -> list[CandidateLink]:
    known = [candidate for candidate in candidates if candidate.recommendation == "known_detail_candidate_from_gate_evidence"]
    strong = [candidate for candidate in candidates if candidate.recommendation == "strong_listing_candidate_for_review"]
    weak = [candidate for candidate in candidates if candidate.recommendation == "weak_listing_candidate_for_review"]

    selected: list[CandidateLink] = []
    seen: set[str] = set()

    for candidate in [*known, *strong, *weak]:
        if candidate.url in seen:
            continue
        seen.add(candidate.url)
        selected.append(candidate)
        if len(selected) >= limit:
            break

    return selected


def parse_detail_page(url: str, final_url: str, status_code: int, html: str) -> DetailPage:
    parser = TextExtractor()
    parser.feed(html)

    return DetailPage(
        url=url,
        final_url=final_url,
        status_code=status_code,
        title=parser.title,
        text=parser.text,
        html_bytes=len(html.encode("utf-8")),
    )


def detail_supports_record(candidate: CandidateLink, detail: DetailPage) -> bool:
    if detail.status_code >= 400:
        return False

    evidence_text = " ".join([candidate.url, candidate.path, candidate.text, detail.title, detail.text])
    exclusion_scope_text = " ".join([candidate.url, candidate.path, detail.title])

    if find_terms(exclusion_scope_text, EXCLUSION_TERMS):
        return False

    return bool(find_terms(evidence_text, PROFILE_TERMS) and find_terms(evidence_text, TARGET_LOCATION_TERMS))


def stable_external_job_id(url: str) -> str:
    parsed = urlparse(url)
    slug = parsed.path.rstrip("/").split("/")[-1] or SOURCE_FAMILY
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return f"{{slug}}:{{digest}}"


def derive_title(candidate: CandidateLink, detail: DetailPage) -> str:
    title = detail.title

    for suffix in (f" - {{COMPANY_NAME}}", f" | {{COMPANY_NAME}}", f" - {{SOURCE_FAMILY}}"):
        if title.endswith(suffix):
            title = title[: -len(suffix)]

    return normalize_whitespace(title) or candidate.text or candidate.path.rsplit("/", 1)[-1].replace("-", " ")


def build_raw_job_record(
    candidate: CandidateLink,
    detail: DetailPage,
    requested_listing_url: str,
    observed_at_utc: str,
) -> RawJobRecord:
    title = derive_title(candidate, detail)
    evidence_text = " ".join([candidate.url, candidate.text, detail.title, detail.text])
    profile_terms = find_terms(evidence_text, PROFILE_TERMS)
    location_terms = find_terms(evidence_text, TARGET_LOCATION_TERMS)
    location = "; ".join(location_terms) or SOURCE_TARGET or ""

    detail_url = detail.final_url or candidate.url

    return RawJobRecord(
        source_name=SOURCE_NAME,
        source_url=detail_url,
        external_job_id=stable_external_job_id(candidate.url),
        raw_data={{
            "source_family": SOURCE_FAMILY,
            "source_target": SOURCE_TARGET,
            "source_type": SOURCE_TYPE,
            "acquisition_boundary": {{
                "listing_url": requested_listing_url,
                "max_detail_pages": MAX_DETAIL_PAGES,
                "detail_pages_fetched": True,
                "browser_automation_used": False,
                "raw_html_persisted": False,
                "relevance_gated": True,
                "generated_from_gate_evidence": True,
            }},
            "result_card": {{
                "title": title,
                "company_name": COMPANY_NAME,
                "location": location,
                "detail_url": detail_url,
            }},
            "job": {{
                "title": title,
                "company_name": COMPANY_NAME,
                "location": location,
                "source_url": detail_url,
                "profile_terms": list(profile_terms),
            }},
            "listing_evidence": {{
                "candidate_path": candidate.path,
                "listing_text": candidate.text,
                "listing_recommendation": candidate.recommendation,
                "listing_reason": candidate.reason,
            }},
            "detail_evidence": {{
                "page_title": detail.title,
                "html_bytes": detail.html_bytes,
                "status_code": detail.status_code,
                "raw_html_persisted": False,
            }},
            "observed_at_utc": observed_at_utc,
        }},
    )
"""


def connector_test_content(candidate: SourceCandidate) -> str:
    module_name = module_name_for(candidate)
    class_name = class_name_for(candidate)
    candidate_host = source_host(candidate.candidate_url) or "example.test"
    detail_url = f"https://{candidate_host}/jobs/product-owner-data-platform"

    return f"""from __future__ import annotations

from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.{module_name} import (
    COMPANY_NAME,
    SOURCE_NAME,
    SOURCE_TYPE,
    {class_name},
    extract_candidate_links,
    select_detail_candidates,
)


LISTING_URL = {candidate.candidate_url!r}
DETAIL_URL = {detail_url!r}


def fake_fetcher(url: str) -> tuple[str, str, int]:
    if url == LISTING_URL:
        html = (
            "<html><body>"
            f"<a href='{{DETAIL_URL}}'>Product Owner Data Platform Hannover</a>"
            "<a href='/jobs/duales-studium-data'>Duales Studium Data Hannover</a>"
            "</body></html>"
        )
        return html, LISTING_URL, 200

    if url == DETAIL_URL:
        html = (
            "<html>"
            "<title>Product Owner Data Platform</title>"
            "<body>Product Owner Data Platform in Hannover. Data, Analytics and stakeholder work.</body>"
            "</html>"
        )
        return html, DETAIL_URL, 200

    raise AssertionError(f"Unexpected URL: {{url}}")


def make_profile() -> SearchProfile:
    return SearchProfile(
        id=1,
        profile_name="unit_test",
        source_name=SOURCE_NAME,
        search_location="Hannover",
        search_radius_km=50,
        offer_type=None,
        page_size=10,
    )


def test_extract_candidate_links_is_bounded_to_relevant_same_domain_links() -> None:
    html, final_url, _ = fake_fetcher(LISTING_URL)

    candidates = extract_candidate_links(html, final_url)
    selected = select_detail_candidates(candidates, limit=3)

    assert [candidate.url for candidate in selected] == [DETAIL_URL]


def test_connector_fetches_bounded_relevant_jobs() -> None:
    connector = {class_name}(listing_url=LISTING_URL, fetcher=fake_fetcher)

    records, final_url = connector.fetch_jobs(
        profile=make_profile(),
        search_term=SearchTerm("Product Owner", id=1),
    )

    assert final_url == LISTING_URL
    assert len(records) == 1

    record = records[0]
    assert record.source_name == SOURCE_NAME
    assert record.source_url == DETAIL_URL
    assert record.external_job_id
    assert record.raw_data["source_type"] == SOURCE_TYPE
    assert record.raw_data["source_family"]
    assert record.raw_data["result_card"]["company_name"] == COMPANY_NAME
    assert "Product Owner" in record.raw_data["result_card"]["title"]
    assert record.raw_data["acquisition_boundary"]["browser_automation_used"] is False
    assert record.raw_data["acquisition_boundary"]["raw_html_persisted"] is False
"""


def connector_docs_content(candidate: SourceCandidate, spec: dict[str, Any]) -> str:
    module_name = module_name_for(candidate)
    class_name = class_name_for(candidate)
    detail_urls = extract_detail_urls_from_spec(spec)
    rejected_urls = rejected_detail_urls_from_spec(spec)

    detail_lines: list[str] = []
    if detail_urls:
        detail_lines.append("Concrete job-detail evidence carried into the connector candidate:")
        detail_lines.extend(f"- {url}" for url in detail_urls)
    else:
        detail_lines.append("- no concrete job-detail URLs were available in connector-candidate evidence")

    if rejected_urls:
        detail_lines.append("")
        detail_lines.append(
            "Broader career-context URLs were present in the evidence, but are not treated as job-detail evidence:"
        )
        detail_lines.extend(f"- {url}" for url in rejected_urls)

    detail_section = "\n".join(detail_lines)

    return f"""# {candidate.company_name} Connector Candidate Implementation

## Status

Generated from DB-backed approval-gated connector evidence. For S7Q artifact reviews this may include S7O build-queue sample evidence.

## Boundary

This is a connector candidate implementation, not a controlled activation.

It does not approve:

- recurring ingestion
- Bronze persistence by itself
- broad crawling
- browser automation
- CSV/Excel/export artifacts as inputs
- raw HTML persistence

## Source Identity

- company key: `{candidate.company_key}`
- source name: `{candidate.source_name_candidate}`
- source family: `{candidate.source_family_candidate}`
- source target: `{candidate.source_target_candidate}`
- source type: `{candidate.source_type_candidate}`
- listing URL: `{candidate.candidate_url}`

## Generated Files

- module: `src/connectors/{module_name}.py`
- tests: `tests/test_{module_name}_connector.py`
- class: `{class_name}`

## Detail Evidence Carried Forward

{detail_section}

## Next Gate

A separate controlled activation gate must decide whether this connector candidate may be registered in the ingestion runner and activated through a search profile migration.
"""


def build_implementation(candidate: SourceCandidate, gate: dict[str, Any]) -> ConnectorImplementation:
    spec = extract_spec_from_gate(gate)
    module_name = module_name_for(candidate)

    return ConnectorImplementation(
        module_path=Path("src/connectors") / f"{module_name}.py",
        test_path=Path("tests") / f"test_{module_name}_connector.py",
        docs_path=Path("docs/planning/active/source-candidates") / f"{module_name}_connector_candidate.md",
        module_content=connector_module_content(candidate=candidate, spec=spec),
        test_content=connector_test_content(candidate),
        docs_content=connector_docs_content(candidate, spec),
    )


def validate_gate(candidate: SourceCandidate, gate: dict[str, Any] | None) -> None:
    if gate is None:
        raise ValueError(f"Missing {REQUIRED_GATE} for candidate {candidate.company_key}.")

    if gate.get("gate_status") != "passed" or gate.get("decision") != "build_connector_candidate":
        raise ValueError(
            f"{REQUIRED_GATE} is not passed/build_connector_candidate for {candidate.company_key}: "
            f"{gate.get('gate_status')} / {gate.get('decision')}"
        )

    spec = extract_spec_from_gate(gate)
    if not spec:
        raise ValueError(f"{REQUIRED_GATE} does not contain connector_candidate_spec evidence.")

    if not extract_detail_urls_from_spec(spec):
        rejected = rejected_detail_urls_from_spec(spec)
        raise ValueError(
            f"{REQUIRED_GATE} connector_candidate_spec does not contain concrete job-detail URLs. "
            f"Rejected URLs: {list(rejected)}"
        )


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

    def load_gate(self, candidate_id: int, gate_name: str) -> dict[str, Any] | None:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select *
                from employer_origin_candidate_gate_reviews
                where candidate_id = %s
                  and gate_name = %s
                """,
                (candidate_id, gate_name),
            )
            row = cur.fetchone()

        return dict(row) if row else None


def gate_stop_lines(candidate: SourceCandidate, reason: str) -> list[str]:
    return [
        f"candidate_id: {candidate.id}",
        f"candidate: {candidate.company_key} | {candidate.source_name_candidate}",
        f"STOP: {reason}",
        "No connector artifact files were written.",
    ]


def print_gate_stop(candidate: SourceCandidate, reason: str) -> None:
    for line in gate_stop_lines(candidate, reason):
        print(line)

def write_files(implementation: ConnectorImplementation, *, overwrite: bool) -> None:
    for path, content in [
        (implementation.module_path, implementation.module_content),
        (implementation.test_path, implementation.test_content),
        (implementation.docs_path, implementation.docs_content),
    ]:
        if path.exists() and not overwrite:
            raise FileExistsError(f"{path} already exists. Use --overwrite to replace it.")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def run_agent(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        repo = GateStateRepository(conn)
        candidate = repo.load_candidate(candidate_id=args.candidate_id, company_key=args.company_key)
        gate = repo.load_gate(candidate.id, REQUIRED_GATE)

    try:
        validate_gate(candidate, gate)
    except ValueError as exc:
        print_gate_stop(candidate, str(exc))
        return 2

    implementation = build_implementation(candidate, gate or {})

    print(f"candidate_id: {candidate.id}")
    print(f"candidate: {candidate.company_key} | {candidate.source_name_candidate}")
    print(f"{REQUIRED_GATE}: passed / build_connector_candidate")
    print("Planned files:")
    print(f"- {implementation.module_path}")
    print(f"- {implementation.test_path}")
    print(f"- {implementation.docs_path}")

    if args.dry_run:
        print("DRY RUN: no files written.")
        return 0

    write_files(implementation, overwrite=args.overwrite)

    print("Connector artifact files written.")
    print("NEXT: run compile/tests. This still does not activate ingestion or Bronze persistence.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a bounded employer-origin connector artifact candidate from DB-backed gate evidence."
    )
    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-id", type=int)
    candidate.add_argument("--company-key")

    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
