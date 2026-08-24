from __future__ import annotations

from src.search_intelligence.runtime_network_acquisition import (
    NetworkObservation,
    recognize_job_payload,
    runtime_delegated_candidate_host,
    runtime_job_record_proof,
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
    page_url: str = "https://jobs.example.com/careers",
) -> NetworkObservation:
    return NetworkObservation(
        request_method="post",
        request_url=request_url,
        response_url=response_url,
        status_code=status_code,
        content_type=content_type,
        resource_type=resource_type,
        page_url=page_url,
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


def test_response_endpoint_job_context_recognizes_generic_runtime_job_object() -> None:
    payload = [
        {
            "title": "Manufacturing Engineer",
            "id": "WD49313",
            "url": "https://tenant.example-ats.com/site/job/Germany/Manufacturing-Engineer_WD49313/apply",
            "location": "Germany - Hannover",
            "jobLevel": "Professional",
        }
    ]

    result = recognize_job_payload(
        _observation(
            request_url="https://jobs.example.com/google-search/process/get-jobs.php?ajax=1",
            response_url="https://jobs.example.com/google-search/process/get-jobs.php?ajax=1",
        ),
        payload,
        allowed_hosts=("jobs.example.com",),
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.identity == "WD49313"
    assert candidate.job_context is True
    assert candidate.explicit_job_key is False
    assert candidate.host_authorized is False


def test_non_job_cms_endpoint_does_not_promote_title_id_url_location_card() -> None:
    payload = [
        {
            "title": "Benefits in EMEA",
            "id": "cta-1",
            "url": "https://www.example.com/careers/benefits-emea",
            "location": "EMEA",
            "jobLevel": "all",
        }
    ]

    result = recognize_job_payload(
        _observation(
            request_url="https://jobs.example.com/admin/api/content/items/CTA?locale=en",
            response_url="https://jobs.example.com/admin/api/content/items/CTA?locale=en",
        ),
        payload,
        allowed_hosts=("jobs.example.com",),
    )

    assert result.candidates == ()


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


def test_endpoint_job_context_does_not_leak_into_explicit_non_job_containers() -> None:
    for container in ("news", "articles", "content", "products"):
        payload = {
            container: [
                {
                    "title": "Platform update",
                    "id": "card-1",
                    "url": "/updates/platform",
                    "location": "EU",
                }
            ]
        }

        result = recognize_job_payload(
            _observation(
                request_url="https://jobs.example.com/process/get-jobs.php",
                response_url="https://jobs.example.com/process/get-jobs.php",
            ),
            payload,
            allowed_hosts=("jobs.example.com",),
        )

        assert result.candidates == (), container


def test_explicit_jobs_path_inside_content_container_still_has_job_context() -> None:
    payload = {
        "content": {
            "jobs": [
                {
                    "title": "Data Engineer",
                    "id": "job-7",
                    "url": "/jobs/job-7",
                    "location": "Hannover",
                }
            ]
        }
    }

    result = recognize_job_payload(
        _observation(
            request_url="https://jobs.example.com/process/get-jobs.php",
            response_url="https://jobs.example.com/process/get-jobs.php",
        ),
        payload,
        allowed_hosts=("jobs.example.com",),
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].identity == "job-7"
    assert result.candidates[0].job_context is True


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


def test_authorized_runtime_inventory_can_prove_and_delegate_cross_host_job() -> None:
    payload = [
        {
            "title": "Manufacturing Engineer",
            "id": "WD49313",
            "url": "https://tenant.example-ats.com/site/job/Hannover/Manufacturing_WD49313/apply",
            "location": "Hannover",
        }
    ]
    result = recognize_job_payload(
        _observation(
            request_url="https://jobs.example.com/process/get-jobs.php",
            response_url="https://jobs.example.com/process/get-jobs.php",
            page_url="https://jobs.example.com/",
        ),
        payload,
        allowed_hosts=("jobs.example.com",),
    )
    candidate = result.candidates[0]

    assert (
        runtime_job_record_proof(
            result,
            candidate,
            allowed_page_hosts=("jobs.example.com",),
            allowed_response_hosts=("jobs.example.com",),
        )
        == "runtime_authorized_inventory_record"
    )
    assert (
        runtime_delegated_candidate_host(
            result,
            candidate,
            allowed_page_hosts=("jobs.example.com",),
            allowed_response_hosts=("jobs.example.com",),
        )
        == "tenant.example-ats.com"
    )


def test_cross_host_inventory_loaded_by_authorized_page_can_prove_same_host_job() -> None:
    payload = {
        "jobs": [
            {
                "jobTitle": "Senior Data Engineer",
                "jobId": "16613264",
                "jobUrl": "https://jobs.vendor.example/companies/acme/16613264",
                "location": "Remote",
            }
        ]
    }
    result = recognize_job_payload(
        _observation(
            request_url="https://jobs.vendor.example/api/widget/jobs",
            response_url="https://jobs.vendor.example/api/widget/jobs",
            page_url="https://www.example.com/careers",
        ),
        payload,
        allowed_hosts=("www.example.com",),
    )
    candidate = result.candidates[0]

    assert (
        runtime_job_record_proof(
            result,
            candidate,
            allowed_page_hosts=("www.example.com",),
            allowed_response_hosts=("www.example.com",),
        )
        == "runtime_page_delegated_inventory_record"
    )
    assert (
        runtime_delegated_candidate_host(
            result,
            candidate,
            allowed_page_hosts=("www.example.com",),
            allowed_response_hosts=("www.example.com",),
        )
        == "jobs.vendor.example"
    )


def test_unrelated_cross_host_response_cannot_delegate_third_host() -> None:
    payload = {
        "jobs": [
            {
                "jobTitle": "Data Engineer",
                "jobId": "REQ-1",
                "jobUrl": "https://third.example/jobs/REQ-1",
                "location": "Berlin",
            }
        ]
    }
    result = recognize_job_payload(
        _observation(
            request_url="https://analytics.vendor.example/api/jobs",
            response_url="https://analytics.vendor.example/api/jobs",
            page_url="https://www.example.com/careers",
        ),
        payload,
        allowed_hosts=("www.example.com",),
    )
    candidate = result.candidates[0]

    assert (
        runtime_job_record_proof(
            result,
            candidate,
            allowed_page_hosts=("www.example.com",),
            allowed_response_hosts=("www.example.com",),
        )
        is None
    )
    assert (
        runtime_delegated_candidate_host(
            result,
            candidate,
            allowed_page_hosts=("www.example.com",),
            allowed_response_hosts=("www.example.com",),
        )
        is None
    )


def test_runtime_proof_requires_authorized_browser_page() -> None:
    payload = {
        "jobs": [
            {
                "jobTitle": "Data Engineer",
                "jobId": "REQ-1",
                "jobUrl": "https://jobs.vendor.example/jobs/REQ-1",
                "location": "Berlin",
            }
        ]
    }
    result = recognize_job_payload(
        _observation(
            request_url="https://jobs.vendor.example/api/jobs",
            response_url="https://jobs.vendor.example/api/jobs",
            page_url="https://untrusted.example/careers",
        ),
        payload,
        allowed_hosts=("www.example.com",),
    )
    candidate = result.candidates[0]

    assert (
        runtime_job_record_proof(
            result,
            candidate,
            allowed_page_hosts=("www.example.com",),
            allowed_response_hosts=("www.example.com",),
        )
        is None
    )


def test_sensitive_query_values_are_redacted_from_persistable_metadata() -> None:
    raw = "https://jobs.example.com/graphql?tenant=acme&token=secret&api_key=also-secret"
    safe = sanitize_url(raw)

    assert "tenant=acme" in safe
    assert "secret" not in safe
    assert "token=%3Credacted%3E" in safe
    assert "api_key=%3Credacted%3E" in safe

    observation = sanitize_observation(
        _observation(
            request_url=raw,
            response_url=raw,
            page_url="https://jobs.example.com/careers?session=secret-page",
            content_type="APPLICATION/JSON; x=y",
        )
    )
    assert observation.request_method == "POST"
    assert observation.content_type == "application/json"
    assert "secret" not in observation.request_url
    assert "secret" not in observation.response_url
    assert "secret-page" not in observation.page_url


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
