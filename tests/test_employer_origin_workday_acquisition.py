from __future__ import annotations

import json

from src.connectors.employer_origin_acquisition_v4_forms import (
    MeteredRequest,
    WORKDAY_DETAIL_SOURCE,
    acquire_genuine_job_pages,
)
from src.connectors.employer_origin_workday_navigation import (
    workday_board_route,
    workday_detail_urls_from_inventory,
    workday_inventory_json_fields,
)


EMPLOYER = "https://www.example.invalid/careers"
EMPLOYER_HOST = "www.example.invalid"
WORKDAY_HOST = "acme.wd3.myworkdayjobs.com"
WORKDAY_BOARD = f"https://{WORKDAY_HOST}/en-US/External"
WORKDAY_INVENTORY = f"https://{WORKDAY_HOST}/wday/cxs/acme/External/jobs"
WORKDAY_DETAIL = (
    f"https://{WORKDAY_HOST}/en-US/External/job/Platform-Engineer_JR12345"
)
EMPLOYER_SEARCH = "https://www.example.invalid/search"


def _job_html() -> str:
    return (
        "<html><title>Platform Engineer</title><body>"
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"JobPosting","title":"Platform Engineer"}'
        "</script>Apply now. Responsibilities and requirements."
        "</body></html>"
    )


def test_workday_board_contract_derives_exact_cxs_inventory() -> None:
    route = workday_board_route(WORKDAY_BOARD, allowed_hosts=(WORKDAY_HOST,))

    assert route is not None
    assert route.tenant == "acme"
    assert route.site == "External"
    assert route.locale == "en-US"
    assert route.public_board_url == WORKDAY_BOARD
    assert route.inventory_url == WORKDAY_INVENTORY


def test_workday_board_contract_fails_closed_for_control_paths_and_unbound_host() -> None:
    assert (
        workday_board_route(
            f"https://{WORKDAY_HOST}/login",
            allowed_hosts=(WORKDAY_HOST,),
        )
        is None
    )
    assert (
        workday_board_route(
            WORKDAY_BOARD,
            allowed_hosts=("other.wd3.myworkdayjobs.com",),
        )
        is None
    )


def test_workday_inventory_projects_only_same_board_job_paths() -> None:
    body = json.dumps(
        {
            "jobPostings": [
                {"externalPath": "/job/Platform-Engineer_JR12345"},
                {"externalPath": "https://evil.invalid/job/escape"},
                {"externalPath": "/job/../login"},
                {"externalPath": "/login"},
            ]
        }
    )

    assert workday_detail_urls_from_inventory(
        inventory_url=WORKDAY_INVENTORY,
        body=body,
        public_board_url=WORKDAY_BOARD,
        allowed_hosts=(WORKDAY_HOST,),
    ) == (WORKDAY_DETAIL,)


def test_explicit_delegated_workday_board_outranks_generic_form_and_proves_in_four() -> None:
    calls: list[MeteredRequest] = []
    inventory_request = MeteredRequest(
        WORKDAY_INVENTORY,
        "POST",
        (),
        workday_inventory_json_fields(),
    )

    def executor(request: MeteredRequest):
        calls.append(request)
        if request == MeteredRequest(EMPLOYER):
            return (
                "<html><title>Careers</title><body>"
                f"<a href='{WORKDAY_BOARD}'>View jobs</a>"
                "<form method='get' action='/search'>"
                "<input name='q' type='text' value=''>"
                "</form></body></html>",
                EMPLOYER,
                200,
            )
        if request == MeteredRequest(WORKDAY_BOARD):
            return "<html><title>Careers</title><body>Job search</body></html>", WORKDAY_BOARD, 200
        if request == inventory_request:
            return (
                json.dumps(
                    {
                        "total": 1,
                        "jobPostings": [
                            {
                                "title": "Platform Engineer",
                                "externalPath": "/job/Platform-Engineer_JR12345",
                            }
                        ],
                    }
                ),
                WORKDAY_INVENTORY,
                200,
            )
        if request == MeteredRequest(WORKDAY_DETAIL):
            return _job_html(), WORKDAY_DETAIL, 200
        if request.url == EMPLOYER_SEARCH:
            raise AssertionError("generic employer search must remain behind delegated ATS board")
        raise AssertionError(request)

    jobs, observed_root = acquire_genuine_job_pages(
        listing_url=EMPLOYER,
        allowed_hosts=(EMPLOYER_HOST,),
        known_detail_urls=(),
        fetcher=lambda url: (_ for _ in ()).throw(AssertionError(url)),
        request_executor=executor,
        max_followup_requests=2,
    )

    assert observed_root == EMPLOYER
    assert calls == [
        MeteredRequest(EMPLOYER),
        MeteredRequest(WORKDAY_BOARD),
        inventory_request,
        MeteredRequest(WORKDAY_DETAIL),
    ]
    assert len(jobs) == 1
    assert jobs[0].final_url == WORKDAY_DETAIL
    assert jobs[0].proof_kind == "jsonld_jobposting"
    assert jobs[0].discovery_source == WORKDAY_DETAIL_SOURCE


def test_workday_json_request_requires_metered_executor() -> None:
    def fetcher(url: str):
        if url == WORKDAY_BOARD:
            return "<html><title>Careers</title><body>Job search</body></html>", WORKDAY_BOARD, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=WORKDAY_BOARD,
        allowed_hosts=(WORKDAY_HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        request_executor=None,
        max_followup_requests=2,
    )

    assert jobs == []
