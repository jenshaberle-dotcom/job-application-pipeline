from __future__ import annotations

from src.search_intelligence.runtime_network_acquisition import (
    NetworkObservation,
    recognize_job_payload,
    runtime_delegated_candidate_host,
    runtime_job_record_proof,
)


def _observation() -> NetworkObservation:
    return NetworkObservation(
        request_method="POST",
        request_url="https://www.example.com/api/get-greenhouse-jobs",
        response_url="https://www.example.com/api/get-greenhouse-jobs",
        status_code=200,
        content_type="application/json",
        resource_type="fetch",
        page_url="https://www.example.com/careers/search",
    )


def test_absolute_url_in_explicit_jobs_container_uses_existing_runtime_proof() -> None:
    payload = {
        "jobs": [
            {
                "title": "Data Engineer",
                "id": "12345",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/12345",
                "locations": [{"name": "Berlin"}],
            }
        ]
    }

    result = recognize_job_payload(
        _observation(),
        payload,
        allowed_hosts=("www.example.com",),
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.identity == "12345"
    assert candidate.candidate_url == "https://boards.greenhouse.io/acme/jobs/12345"
    assert candidate.job_context is True
    assert candidate.explicit_job_key is False
    assert candidate.score >= 7
    assert (
        runtime_job_record_proof(
            result,
            candidate,
            allowed_page_hosts=("www.example.com",),
            allowed_response_hosts=("www.example.com",),
        )
        == "runtime_authorized_inventory_record"
    )
    assert (
        runtime_delegated_candidate_host(
            result,
            candidate,
            allowed_page_hosts=("www.example.com",),
            allowed_response_hosts=("www.example.com",),
        )
        == "boards.greenhouse.io"
    )


def test_absolute_url_does_not_turn_explicit_product_container_into_job_inventory() -> None:
    payload = {
        "products": [
            {
                "title": "Cloud Platform",
                "id": "product-7",
                "absolute_url": "https://www.example.com/products/cloud-platform",
                "location": "EU",
            }
        ]
    }

    result = recognize_job_payload(
        _observation(),
        payload,
        allowed_hosts=("www.example.com",),
    )

    assert result.candidates == ()
