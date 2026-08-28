from __future__ import annotations

import json

import pytest

from src.connectors.employer_origin_workday_acquisition import (
    WorkdayAcquisitionRequest,
    acquire_workday_job_page,
)


EMPLOYER = "https://jobs.example.com/"
EMPLOYER_HOST = "jobs.example.com"
WORKDAY_HOST = "acme.wd5.myworkdayjobs.com"
BOARD = f"https://{WORKDAY_HOST}/en-US/acmecareers"
INVENTORY = f"https://{WORKDAY_HOST}/wday/cxs/acme/acmecareers/jobs"
PUBLIC_DETAIL = f"{BOARD}/job/Germany-Berlin/Platform-Engineer_JR12345"
CXS_DETAIL = (
    f"https://{WORKDAY_HOST}/wday/cxs/acme/acmecareers"
    "/job/Germany-Berlin/Platform-Engineer_JR12345"
)


def _root_html(*, both_controls: bool = True) -> str:
    login = f'<a href="{BOARD}/login">Sign In</a>'
    introduce = (
        f'<a href="{BOARD}/introduceYourself">Join talent community</a>'
        if both_controls
        else ""
    )
    return f"<html><body>{login}{introduce}</body></html>"


def _inventory_body() -> str:
    return json.dumps(
        {
            "jobPostings": [
                {
                    "title": "Platform Engineer",
                    "externalPath": "/job/Germany-Berlin/Platform-Engineer_JR12345",
                }
            ]
        }
    )


def _detail_body(*, strong: bool = True) -> str:
    description = (
        "<h2>Your responsibilities</h2>"
        "<p>You build reliable platform services, improve observability, operate "
        "production systems, review architecture, and collaborate with engineering "
        "teams across the organization.</p>"
        if strong
        else (
            "<p>Build reliable distributed systems with a collaborative engineering "
            "team while improving platform stability, observability, deployment "
            "automation, and technical quality across services.</p>"
        )
    )
    return json.dumps(
        {
            "jobPostingInfo": {
                "title": "Platform Engineer",
                "jobReqId": "JR12345",
                "jobPostingId": "Platform-Engineer_JR12345",
                "jobDescription": description,
            }
        }
    )


def test_delegated_workday_path_proves_job_in_exactly_three_requests() -> None:
    calls: list[WorkdayAcquisitionRequest] = []

    def execute(request: WorkdayAcquisitionRequest) -> tuple[str, str, int]:
        calls.append(request)
        if request.url == EMPLOYER and request.method == "GET":
            return _root_html(), EMPLOYER, 200
        if request.url == INVENTORY and request.method == "POST":
            assert dict(request.json_fields) == {
                "appliedFacets": {},
                "limit": 20,
                "offset": 0,
                "searchText": "",
            }
            return _inventory_body(), INVENTORY, 200
        if request.url == CXS_DETAIL and request.method == "GET":
            return _detail_body(), CXS_DETAIL, 200
        raise AssertionError(f"unexpected request: {request}")

    job, observed_root = acquire_workday_job_page(
        listing_url=EMPLOYER,
        allowed_hosts=(EMPLOYER_HOST,),
        request_executor=execute,
    )

    assert job is not None
    assert observed_root == EMPLOYER
    assert job.final_url == PUBLIC_DETAIL
    assert job.requested_url == PUBLIC_DETAIL
    assert job.title == "Platform Engineer"
    assert job.proof_kind == "job_url_and_job_content"
    assert job.discovery_source == "workday_cxs_inventory_detail"
    assert [(item.method, item.url) for item in calls] == [
        ("GET", EMPLOYER),
        ("POST", INVENTORY),
        ("GET", CXS_DETAIL),
    ]
    assert PUBLIC_DETAIL not in [item.url for item in calls]
    assert BOARD not in [item.url for item in calls]


def test_single_control_path_fails_closed_before_external_request() -> None:
    calls: list[WorkdayAcquisitionRequest] = []

    def execute(request: WorkdayAcquisitionRequest) -> tuple[str, str, int]:
        calls.append(request)
        if request.url == EMPLOYER:
            return _root_html(both_controls=False), EMPLOYER, 200
        raise AssertionError("weak Workday authority must not trigger an external request")

    job, observed_root = acquire_workday_job_page(
        listing_url=EMPLOYER,
        allowed_hosts=(EMPLOYER_HOST,),
        request_executor=execute,
    )

    assert job is None
    assert observed_root == EMPLOYER
    assert [(item.method, item.url) for item in calls] == [("GET", EMPLOYER)]


def test_inventory_must_stay_on_exact_derived_cxs_endpoint() -> None:
    calls: list[WorkdayAcquisitionRequest] = []

    def execute(request: WorkdayAcquisitionRequest) -> tuple[str, str, int]:
        calls.append(request)
        if request.url == EMPLOYER:
            return _root_html(), EMPLOYER, 200
        if request.url == INVENTORY:
            return _inventory_body(), f"https://{WORKDAY_HOST}/login", 200
        raise AssertionError("invalid inventory response must stop acquisition")

    job, _ = acquire_workday_job_page(
        listing_url=EMPLOYER,
        allowed_hosts=(EMPLOYER_HOST,),
        request_executor=execute,
    )

    assert job is None
    assert len(calls) == 2


def test_cxs_detail_metadata_alone_does_not_weaken_proof() -> None:
    calls: list[WorkdayAcquisitionRequest] = []

    def execute(request: WorkdayAcquisitionRequest) -> tuple[str, str, int]:
        calls.append(request)
        if request.url == EMPLOYER:
            return _root_html(), EMPLOYER, 200
        if request.url == INVENTORY:
            return _inventory_body(), INVENTORY, 200
        if request.url == CXS_DETAIL:
            return _detail_body(strong=False), CXS_DETAIL, 200
        raise AssertionError(f"unexpected request: {request}")

    job, _ = acquire_workday_job_page(
        listing_url=EMPLOYER,
        allowed_hosts=(EMPLOYER_HOST,),
        request_executor=execute,
    )

    assert job is None
    assert len(calls) == 3


def test_root_binding_mismatch_is_rejected() -> None:
    def execute(_request: WorkdayAcquisitionRequest) -> tuple[str, str, int]:
        return _root_html(), "https://unrelated.invalid/", 200

    with pytest.raises(RuntimeError, match="root source binding mismatch"):
        acquire_workday_job_page(
            listing_url=EMPLOYER,
            allowed_hosts=(EMPLOYER_HOST,),
            request_executor=execute,
        )
