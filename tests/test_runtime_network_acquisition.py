from __future__ import annotations

from src.search_intelligence.runtime_network_acquisition import (
    NetworkObservation,
    recognize_job_payload,
    sanitize_observation,
    sanitize_url,
)


def _observation(
    *,
    request_url: str = "https://jobs.example.com/api/jobs",
    response_url: str = "https://jobs.example.com/api/jobs",
    status_code: int = 200,
    content_type: str = "application/json; charset=utf-8",
    resource_type: str = "xhr",
) -> NetworkObservation:
    return NetworkObservation(
        request_method="post",
        request_url=request_url,
        response_url=response_url,
        status_code=status_code,
        content_type=content_type,
        resource_type=resource_type,
    )


def test_recognizes_job_objects_from_generic_jobs_container() -> None:
    payload = {
        "data": {
            "jobs": [
                {
                    "jobTitle": "Machine Learning Engineer",
                    "jobId": "REQ-42",
                    "location": "Berlin",
                    "jobUrl": "/job/REQ-42",
                },
                {
                    "jobTitle": "Data Engineer",
                    "jobId": "REQ-43",
                    "location": "Hannover",
                    "jobUrl": "/job/REQ-43",
                },
            ]
        }
    }

    result = recognize_job_payload(
        _observation(),
        payload,
        allowed_hosts=("jobs.example.com",),
    )

    assert [candidate.identity for candidate in result.candidates] == ["REQ-42", "REQ-43"]
    assert all(candidate.host_authorized for candidate in result.candidates)
    assert all(candidate.explicit_job_key for candidate in result.candidates)
    assert all(candidate.job_context for candidate in result.candidates)
    assert result.no_product_authority is True


def test_recognizes_graphql_position_nodes_without_provider_specific_keys() -> None:
    payload = {
        "data": {
            "positions": {
                "edges": [
                    {
                        "node": {
                            "title": "Reliability Engineer",
                            "id": "abc-1",
                            "url": "/positions/abc-1",
                            "location": "Remote Germany",
                        }
                    }
                ]
            }
        }
    }

    result = recognize_job_payload(
        _observation(response_url="https://careers.example.com/graphql"),
        payload,
        allowed_hosts=("careers.example.com",),
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.title == "Reliability Engineer"
    assert candidate.identity == "abc-1"
    assert candidate.candidate_url == "https://careers.example.com/positions/abc-1"
    assert candidate.explicit_job_key is False
    assert candidate.job_context is True
    assert candidate.host_authorized is True


def test_rejects_generic_product_objects_even_when_shape_looks_similar() -> None:
    payload = {
        "products": [
            {
                "title": "Cloud Platform",
                "id": "product-7",
                "url": "/products/cloud-platform",
                "location": "EU",
            }
        ]
    }

    result = recognize_job_payload(
        _observation(),
        payload,
        allowed_hosts=("jobs.example.com",),
    )

    assert result.candidates == ()


def test_cross_host_job_url_is_hypothesis_but_not_authorized() -> None:
    payload = {
        "jobs": [
            {
                "jobTitle": "Data Engineer",
                "jobId": "REQ-1",
                "jobUrl": "https://unbound.example.net/jobs/REQ-1",
            }
        ]
    }

    result = recognize_job_payload(
        _observation(),
        payload,
        allowed_hosts=("jobs.example.com",),
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].host_authorized is False
    assert result.candidates[0].candidate_url == "https://unbound.example.net/jobs/REQ-1"


def test_sensitive_query_values_are_redacted_from_persistable_metadata() -> None:
    raw = "https://jobs.example.com/graphql?tenant=acme&token=secret&api_key=also-secret"
    safe = sanitize_url(raw)

    assert "tenant=acme" in safe
    assert "secret" not in safe
    assert "token=%3Credacted%3E" in safe
    assert "api_key=%3Credacted%3E" in safe

    observation = sanitize_observation(
        _observation(request_url=raw, response_url=raw, content_type="APPLICATION/JSON; x=y")
    )
    assert observation.request_method == "POST"
    assert observation.content_type == "application/json"
    assert "secret" not in observation.request_url
    assert "secret" not in observation.response_url


def test_non_structured_document_response_is_not_interpreted_as_job_payload() -> None:
    result = recognize_job_payload(
        _observation(content_type="text/html", resource_type="document"),
        {"jobs": [{"jobTitle": "Engineer", "jobId": "1", "jobUrl": "/jobs/1"}]},
        allowed_hosts=("jobs.example.com",),
    )

    assert result.nodes_examined == 0
    assert result.candidates == ()


def test_http_error_is_not_interpreted_as_job_payload() -> None:
    result = recognize_job_payload(
        _observation(status_code=429),
        {"jobs": [{"jobTitle": "Engineer", "jobId": "1", "jobUrl": "/jobs/1"}]},
        allowed_hosts=("jobs.example.com",),
    )

    assert result.nodes_examined == 0
    assert result.candidates == ()


def test_traversal_limits_fail_closed_and_report_truncation() -> None:
    payload = {"outer": {"middle": {"jobs": [{"jobTitle": "Engineer", "jobId": "1"}]}}}

    result = recognize_job_payload(
        _observation(),
        payload,
        allowed_hosts=("jobs.example.com",),
        max_nodes=2,
        max_depth=8,
    )

    assert result.traversal_truncated is True
    assert result.candidates == ()


def test_candidate_limit_is_bounded() -> None:
    payload = {
        "jobs": [
            {"jobTitle": f"Engineer {index}", "jobId": str(index), "jobUrl": f"/jobs/{index}"}
            for index in range(10)
        ]
    }

    result = recognize_job_payload(
        _observation(),
        payload,
        allowed_hosts=("jobs.example.com",),
        max_candidates=3,
    )

    assert len(result.candidates) == 3
    assert result.traversal_truncated is True
