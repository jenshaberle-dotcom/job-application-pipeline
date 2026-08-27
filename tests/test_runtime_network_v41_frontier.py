from __future__ import annotations

import pytest

from src.search_intelligence.runtime_network_acquisition import (
    NetworkObservation,
    recognize_job_payload,
    runtime_job_record_proof,
)


def _observation() -> NetworkObservation:
    return NetworkObservation(
        request_method="POST",
        request_url="https://jobs.example.com/career/api-v1/get-all-jobs",
        response_url="https://jobs.example.com/career/api-v1/get-all-jobs",
        status_code=200,
        content_type="application/json",
        resource_type="xhr",
        page_url="https://jobs.example.com/career",
    )


@pytest.mark.parametrize(
    ("apply_key", "external_key"),
    [
        ("applyLink", "externalLink"),
        ("apply_link", "external_link"),
        ("apply-link", "external-link"),
        ("APPLYLINK", "EXTERNALLINK"),
    ],
)
def test_v40_bjak_like_url_fields_do_not_gain_url_authority_before_v41(
    apply_key: str,
    external_key: str,
) -> None:
    """V40 field names alone are evidence, not parser or proof authority.

    V41 exists to classify the values behind normalized ``applylink`` and
    ``externallink``. Until that diagnostic proves generic URL semantics, these
    fields must not silently become candidate URLs even when the surrounding record
    is otherwise strongly job-shaped.
    """

    payload = {
        "jobs": [
            {
                "title": "Data Engineer",
                "jobId": "JOB-42",
                "location": "Hannover",
                apply_key: "/career/jobs/JOB-42/apply",
                external_key: "https://other.example/jobs/JOB-42",
            }
        ]
    }

    result = recognize_job_payload(
        _observation(),
        payload,
        allowed_hosts=("jobs.example.com",),
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.title == "Data Engineer"
    assert candidate.identity == "JOB-42"
    assert candidate.candidate_url == ""
    assert candidate.host_authorized is False
    assert (
        runtime_job_record_proof(
            result,
            candidate,
            allowed_page_hosts=("jobs.example.com",),
            allowed_response_hosts=("jobs.example.com",),
        )
        is None
    )


def test_existing_applyurl_contract_remains_distinct_from_unproven_applylink() -> None:
    payload = {
        "jobs": [
            {
                "title": "ML Engineer",
                "jobId": "JOB-43",
                "applyUrl": "/career/jobs/JOB-43/apply",
                "applyLink": "/unproven/JOB-43",
            }
        ]
    }

    result = recognize_job_payload(
        _observation(),
        payload,
        allowed_hosts=("jobs.example.com",),
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.candidate_url == "https://jobs.example.com/career/jobs/JOB-43/apply"
    assert candidate.host_authorized is True
    assert (
        runtime_job_record_proof(
            result,
            candidate,
            allowed_page_hosts=("jobs.example.com",),
            allowed_response_hosts=("jobs.example.com",),
        )
        == "runtime_authorized_inventory_record"
    )
