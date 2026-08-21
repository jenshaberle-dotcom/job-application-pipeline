from __future__ import annotations

import json

from src.connectors.employer_origin_acquisition_v4 import acquire_genuine_job_pages


EMPLOYER = "https://commercetools.com/careers"
METADATA = "https://boards-api.greenhouse.io/v1/boards/commercetools"
JOBS = "https://boards-api.greenhouse.io/v1/boards/commercetools/jobs"
DETAIL = "https://job-boards.greenhouse.io/commercetools/jobs/7774985003"


def test_greenhouse_cascade_stays_inside_same_four_request_meter() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == EMPLOYER:
            return (
                f'<html><script src="{JOBS}?content=true"></script><body>Careers</body></html>',
                EMPLOYER,
                200,
            )
        if url == METADATA:
            return json.dumps({"name": "commercetools"}), METADATA, 200
        if url == JOBS:
            return (
                json.dumps(
                    {
                        "jobs": [
                            {
                                "id": 7774985003,
                                "title": "Senior Data Engineer",
                                "absolute_url": DETAIL,
                            }
                        ]
                    }
                ),
                JOBS,
                200,
            )
        if url == DETAIL:
            return (
                "<html><title>Senior Data Engineer</title><body>"
                '<script type="application/ld+json">'
                '{"@context":"https://schema.org","@type":"JobPosting","title":"Senior Data Engineer"}'
                "</script>Apply now. Responsibilities and requirements for this concrete role."
                "</body></html>",
                DETAIL,
                200,
            )
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=EMPLOYER,
        allowed_hosts=("commercetools.com",),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [EMPLOYER, METADATA, JOBS, DETAIL]
    assert len(jobs) == 1
    assert jobs[0].final_url == DETAIL
    assert jobs[0].discovery_source == "greenhouse_provider_delegated_detail:commercetools"
    assert jobs[0].proof_kind == "jsonld_jobposting"


def test_greenhouse_cascade_stops_before_jobs_when_board_identity_does_not_match() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == EMPLOYER:
            return f'<script src="{JOBS}"></script>', EMPLOYER, 200
        if url == METADATA:
            return json.dumps({"name": "unrelated employer"}), METADATA, 200
        if url in {JOBS, DETAIL}:
            raise AssertionError("identity mismatch must stop provider cascade")
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=EMPLOYER,
        allowed_hosts=("commercetools.com",),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [EMPLOYER, METADATA]
    assert jobs == []
