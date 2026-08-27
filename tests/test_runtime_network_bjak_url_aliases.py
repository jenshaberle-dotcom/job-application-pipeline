from __future__ import annotations

import pytest

from src.search_intelligence.runtime_network_acquisition import (
    EXPLICIT_JOB_KEYS,
    URL_KEYS,
    NetworkObservation,
    recognize_job_payload,
    runtime_delegated_candidate_host,
    runtime_job_record_proof,
)


def _cross_host_observation() -> NetworkObservation:
    return NetworkObservation(
        request_method="GET",
        request_url="https://api.vendor.example/career/api-v1/get-all-jobs",
        response_url="https://api.vendor.example/career/api-v1/get-all-jobs",
        status_code=200,
        content_type="application/json",
        resource_type="xhr",
        page_url="https://careers.example.com/careers",
    )


@pytest.mark.parametrize(
    ("raw_key", "normalized_key"),
    [
        ("applyLink", "applylink"),
        ("externalLink", "externallink"),
    ],
)
def test_runtime_url_alias_is_recognized_without_granting_explicit_authority(
    raw_key: str,
    normalized_key: str,
) -> None:
    assert normalized_key in URL_KEYS
    assert normalized_key not in EXPLICIT_JOB_KEYS

    payload = {
        "jobs": [
            {
                "title": "Data Engineer",
                "id": "job-1",
                raw_key: "https://third.example/jobs/job-1",
            }
        ]
    }

    result = recognize_job_payload(
        _cross_host_observation(),
        payload,
        allowed_hosts=("careers.example.com",),
    )

    assert len(result.candidates) == 1

    candidate = result.candidates[0]

    assert candidate.identity == "job-1"
    assert candidate.candidate_url == "https://third.example/jobs/job-1"
    assert candidate.job_context is True

    # The URL alias itself is recognition vocabulary only.
    assert candidate.explicit_job_key is False
    assert candidate.host_authorized is False

    # Authorized page -> unrelated response -> third candidate host
    # remains outside the bounded one-hop proof contract.
    assert (
        runtime_job_record_proof(
            result,
            candidate,
            allowed_page_hosts=("careers.example.com",),
            allowed_response_hosts=("careers.example.com",),
        )
        is None
    )

    assert (
        runtime_delegated_candidate_host(
            result,
            candidate,
            allowed_page_hosts=("careers.example.com",),
            allowed_response_hosts=("careers.example.com",),
        )
        is None
    )


@pytest.mark.parametrize(
    "raw_key",
    [
        "applyLink",
        "externalLink",
    ],
)
def test_runtime_url_alias_does_not_promote_product_container(
    raw_key: str,
) -> None:
    payload = {
        "products": [
            {
                "title": "Cloud Platform",
                "id": "product-7",
                raw_key: "https://third.example/products/cloud-platform",
                "location": "EU",
            }
        ]
    }

    result = recognize_job_payload(
        _cross_host_observation(),
        payload,
        allowed_hosts=("careers.example.com",),
    )

    assert result.candidates == ()
