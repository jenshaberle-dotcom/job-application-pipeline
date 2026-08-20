"""Acquisition-first adapter for the approval-gated connector artifact generator.

The legacy generator owns repository/DB gate identity and artifact write
boundaries. V2 intentionally changes only generated connector semantics:
connector health means reaching a genuine employer-origin job detail, while
profile/role/skill/location qualification is deferred downstream.
"""

from __future__ import annotations

from urllib.parse import urlparse

from scripts import run_employer_origin_connector_artifact_generator as legacy


GENERATOR_SEMANTICS = "employer_origin_acquisition_first.v2"


def validate_gate_v2(candidate: legacy.SourceCandidate, gate: dict | None) -> None:
    if gate is None:
        raise ValueError(f"Missing {legacy.REQUIRED_GATE} for candidate {candidate.company_key}.")
    if gate.get("gate_status") != "passed" or gate.get("decision") != "build_connector_candidate":
        raise ValueError(
            f"{legacy.REQUIRED_GATE} is not passed/build_connector_candidate for {candidate.company_key}: "
            f"{gate.get('gate_status')} / {gate.get('decision')}"
        )
    spec = legacy.extract_spec_from_gate(gate)
    if not spec:
        raise ValueError(f"{legacy.REQUIRED_GATE} does not contain connector_candidate_spec evidence.")

    parsed = urlparse(candidate.candidate_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("candidate origin URL is not an absolute HTTP(S) URL")


def connector_module_content_v2(
    *,
    candidate: legacy.SourceCandidate,
    spec: dict,
) -> str:
    module_name = legacy.module_name_for(candidate)
    class_name = legacy.class_name_for(candidate)
    detail_urls = legacy.extract_detail_urls_from_spec(spec)
    domains = legacy.source_domain_set(candidate.candidate_url, detail_urls)

    return f'''from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import requests

from src.connectors.base import JobSourceConnector, RawJobRecord, SearchProfile, SearchTerm
from src.connectors.capabilities import SourceCapabilities
from src.connectors.employer_origin_acquisition import acquire_genuine_job_pages, normalize_whitespace


SOURCE_NAME = {candidate.source_name_candidate!r}
SOURCE_FAMILY = {candidate.source_family_candidate!r}
SOURCE_TARGET = {candidate.source_target_candidate!r}
SOURCE_TYPE = {candidate.source_type_candidate!r}
COMPANY_NAME = {candidate.company_name!r}
LISTING_URL = {candidate.candidate_url!r}
ALLOWED_HOSTS = {domains!r}
KNOWN_DETAIL_URLS = {detail_urls!r}
REQUEST_TIMEOUT_SECONDS = 20
MAX_DETAIL_PAGES = 2
USER_AGENT = (
    "job-application-pipeline-{module_name}-connector-candidate/0.2 "
    "(bounded acquisition proof; qualification deferred)"
)


class {class_name}(JobSourceConnector):
    # Generated from DB-backed approval-gated employer-origin evidence.
    # Acquisition proves genuine jobs only; relevance is a downstream concern.

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
        # profile/search_term are intentionally not acquisition gates. They are
        # accepted for the common connector interface and evaluated downstream.
        del profile, search_term
        jobs, final_url = acquire_genuine_job_pages(
            listing_url=self.listing_url,
            allowed_hosts=ALLOWED_HOSTS,
            known_detail_urls=KNOWN_DETAIL_URLS,
            fetcher=self.fetcher,
            max_followup_requests=self.max_detail_pages,
            max_results=max(1, self.max_detail_pages),
        )
        observed_at_utc = datetime.now(UTC).isoformat()
        records = [
            build_raw_job_record(
                job=job,
                requested_listing_url=final_url,
                observed_at_utc=observed_at_utc,
                max_followup_requests=self.max_detail_pages,
            )
            for job in jobs
        ]
        return records, final_url


def fetch_url(url: str) -> tuple[str, str, int]:
    response = requests.get(
        url,
        headers={{
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        }},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text, response.url, response.status_code


def stable_external_job_id(url: str) -> str:
    slug = url.rstrip("/").rsplit("/", 1)[-1] or SOURCE_FAMILY
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return f"{{slug}}:{{digest}}"


def build_raw_job_record(
    *,
    job,
    requested_listing_url: str,
    observed_at_utc: str,
    max_followup_requests: int,
) -> RawJobRecord:
    title = normalize_whitespace(job.title) or normalize_whitespace(job.anchor_text) or "Job"
    detail_url = job.final_url or job.requested_url
    return RawJobRecord(
        source_name=SOURCE_NAME,
        source_url=detail_url,
        external_job_id=stable_external_job_id(detail_url),
        raw_data={{
            "source_family": SOURCE_FAMILY,
            "source_target": SOURCE_TARGET,
            "source_type": SOURCE_TYPE,
            "acquisition_boundary": {{
                "listing_url": requested_listing_url,
                "max_followup_requests": max_followup_requests,
                "browser_automation_used": False,
                "raw_html_persisted": False,
                "relevance_gated": False,
                "qualification_deferred": True,
                "generated_from_gate_evidence": True,
            }},
            "result_card": {{
                "title": title,
                "company_name": COMPANY_NAME,
                "detail_url": detail_url,
            }},
            "job": {{
                "title": title,
                "company_name": COMPANY_NAME,
                "source_url": detail_url,
            }},
            "acquisition_evidence": {{
                "proof_kind": job.proof_kind,
                "discovery_source": job.discovery_source,
                "status_code": job.status_code,
                "html_bytes": job.html_bytes,
                "proof_job_persisted": False,
            }},
            "observed_at_utc": observed_at_utc,
        }},
    )
'''


def connector_test_content_v2(candidate: legacy.SourceCandidate) -> str:
    module_name = legacy.module_name_for(candidate)
    class_name = legacy.class_name_for(candidate)
    candidate_host = legacy.source_host(candidate.candidate_url) or "example.test"
    listing_url = candidate.candidate_url
    intermediate_url = f"https://{candidate_host}/careers/open-positions"
    detail_url = f"https://{candidate_host}/jobs/backend-engineer-berlin-12345"
    privacy_url = f"https://{candidate_host}/privacy-policy"

    return f'''from __future__ import annotations

from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.{module_name} import (
    SOURCE_NAME,
    SOURCE_TYPE,
    {class_name},
)


LISTING_URL = {listing_url!r}
INTERMEDIATE_URL = {intermediate_url!r}
DETAIL_URL = {detail_url!r}
PRIVACY_URL = {privacy_url!r}


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


def test_connector_proves_one_real_job_without_profile_or_location_relevance() -> None:
    calls: list[str] = []

    def fake_fetcher(url: str) -> tuple[str, str, int]:
        calls.append(url)
        if url == LISTING_URL:
            return (
                "<html><title>Careers</title><body>"
                f"<a href='{{PRIVACY_URL}}'>Privacy</a>"
                f"<a href='{{INTERMEDIATE_URL}}'>Open positions</a>"
                "</body></html>",
                LISTING_URL,
                200,
            )
        if url == INTERMEDIATE_URL:
            return (
                "<html><title>Open positions</title><body>"
                f"<a href='{{DETAIL_URL}}'>Backend Engineer Berlin</a>"
                "</body></html>",
                INTERMEDIATE_URL,
                200,
            )
        if url == DETAIL_URL:
            return (
                "<html><title>Backend Engineer Berlin</title><body>"
                '<script type="application/ld+json">'
                '{{"@context":"https://schema.org","@type":"JobPosting","title":"Backend Engineer"}}'
                "</script>Apply now. Build distributed services in Berlin."
                "</body></html>",
                DETAIL_URL,
                200,
            )
        raise AssertionError(f"Unexpected URL: {{url}}")

    connector = {class_name}(listing_url=LISTING_URL, max_detail_pages=2, fetcher=fake_fetcher)
    records, final_url = connector.fetch_jobs(
        profile=make_profile(),
        search_term=SearchTerm("Data Hannover", id=1),
    )

    assert final_url == LISTING_URL
    assert calls == [LISTING_URL, INTERMEDIATE_URL, DETAIL_URL]
    assert PRIVACY_URL not in calls
    assert len(records) == 1
    record = records[0]
    assert record.source_name == SOURCE_NAME
    assert record.source_url == DETAIL_URL
    assert record.raw_data["source_type"] == SOURCE_TYPE
    assert record.raw_data["acquisition_boundary"]["relevance_gated"] is False
    assert record.raw_data["acquisition_boundary"]["qualification_deferred"] is True
    assert record.raw_data["acquisition_evidence"]["proof_kind"] == "jsonld_jobposting"
    assert record.raw_data["acquisition_evidence"]["proof_job_persisted"] is False
    assert "Backend Engineer" in record.raw_data["job"]["title"]
    assert "Hannover" not in record.raw_data["job"]["title"]


def test_connector_rejects_generic_privacy_page_even_when_linked_from_career_root() -> None:
    calls: list[str] = []

    def fake_fetcher(url: str) -> tuple[str, str, int]:
        calls.append(url)
        if url == LISTING_URL:
            return (
                "<html><title>Careers</title><body>"
                f"<a href='{{PRIVACY_URL}}'>Privacy Policy</a>"
                "</body></html>",
                LISTING_URL,
                200,
            )
        raise AssertionError(f"Unexpected URL: {{url}}")

    connector = {class_name}(listing_url=LISTING_URL, max_detail_pages=2, fetcher=fake_fetcher)
    records, _ = connector.fetch_jobs(make_profile(), SearchTerm("anything", id=2))

    assert records == []
    assert calls == [LISTING_URL]
'''


def connector_docs_content_v2(candidate: legacy.SourceCandidate, spec: dict) -> str:
    base = legacy.connector_docs_content(candidate, spec)
    return base.replace(
        "## Next Gate",
        "## Acquisition Semantics\n\n"
        "This generated connector is acquisition-first: one genuine employer-origin job detail is enough to prove implementation health. "
        "Profile, role, skill, and location qualification are deferred to downstream stages. Proof execution does not persist a job by itself.\n\n"
        "## Next Gate",
    )


def install_v2_semantics() -> None:
    legacy.validate_gate = validate_gate_v2
    legacy.connector_module_content = connector_module_content_v2
    legacy.connector_test_content = connector_test_content_v2
    legacy.connector_docs_content = connector_docs_content_v2


def run_agent(args) -> int:
    install_v2_semantics()
    return legacy.run_agent(args)


def build_parser():
    return legacy.build_parser()


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
