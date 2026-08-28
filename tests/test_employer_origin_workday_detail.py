from __future__ import annotations

import json

from src.connectors.employer_origin_acquisition import genuine_job_detail_proof
from src.connectors.employer_origin_workday_detail import (
    parse_workday_cxs_detail,
    workday_cxs_detail_page,
    workday_cxs_detail_url,
)


WORKDAY_HOST = "acme.wd5.myworkdayjobs.com"
BOARD = f"https://{WORKDAY_HOST}/en-US/acmecareers"
PUBLIC_DETAIL = f"{BOARD}/job/Germany-Berlin/Platform-Engineer_JR12345"
CXS_DETAIL = (
    f"https://{WORKDAY_HOST}/wday/cxs/acme/acmecareers"
    "/job/Germany-Berlin/Platform-Engineer_JR12345"
)


def _detail_body(*, description: str | None = None) -> str:
    body = description or (
        "<h2>Your responsibilities</h2>"
        "<p>You build reliable platform services, operate production systems, "
        "improve observability, review architecture, and collaborate closely "
        "with engineering teams across the organization.</p>"
    )
    return json.dumps(
        {
            "jobPostingInfo": {
                "title": "Platform Engineer",
                "jobReqId": "JR12345",
                "jobPostingId": "Platform-Engineer_JR12345",
                "jobDescription": body,
            }
        }
    )


def test_exact_public_detail_projects_to_same_host_cxs_detail() -> None:
    assert workday_cxs_detail_url(
        PUBLIC_DETAIL,
        public_board_url=BOARD,
        allowed_hosts={WORKDAY_HOST},
    ) == CXS_DETAIL


def test_cxs_detail_derivation_rejects_unbound_or_malformed_public_details() -> None:
    assert workday_cxs_detail_url(
        "https://evil.invalid/en-US/acmecareers/job/Germany-Berlin/X_JR1",
        public_board_url=BOARD,
        allowed_hosts={WORKDAY_HOST},
    ) is None
    assert workday_cxs_detail_url(
        f"{BOARD}/login",
        public_board_url=BOARD,
        allowed_hosts={WORKDAY_HOST},
    ) is None
    assert workday_cxs_detail_url(
        f"{BOARD}/job/../login",
        public_board_url=BOARD,
        allowed_hosts={WORKDAY_HOST},
    ) is None
    assert workday_cxs_detail_url(
        f"{PUBLIC_DETAIL}?token=secret",
        public_board_url=BOARD,
        allowed_hosts={WORKDAY_HOST},
    ) is None


def test_structured_detail_requires_title_description_and_identity() -> None:
    detail = parse_workday_cxs_detail(_detail_body())
    assert detail is not None
    assert detail.title == "Platform Engineer"
    assert detail.identity == "JR12345"

    assert parse_workday_cxs_detail(json.dumps({"jobPostingInfo": {}})) is None
    assert parse_workday_cxs_detail(
        json.dumps(
            {
                "jobPostingInfo": {
                    "title": "Platform Engineer",
                    "jobDescription": "x" * 200,
                }
            }
        )
    ) is None


def test_cxs_projection_passes_unchanged_genuine_job_proof_on_real_content() -> None:
    page = workday_cxs_detail_page(
        public_detail_url=PUBLIC_DETAIL,
        public_board_url=BOARD,
        response_url=CXS_DETAIL,
        status_code=200,
        body=_detail_body(),
        allowed_hosts={WORKDAY_HOST},
    )
    assert page is not None
    assert page.final_url == CXS_DETAIL
    assert page.title == "Platform Engineer"

    assert genuine_job_detail_proof(
        page,
        allowed_hosts={WORKDAY_HOST},
        known_detail=True,
    ) == "known_detail_and_job_content"


def test_json_container_name_cannot_accidentally_satisfy_job_content_proof() -> None:
    description = (
        "<p>Build reliable distributed systems with a collaborative engineering "
        "team while improving platform stability, observability, deployment "
        "automation, and technical quality across services.</p>"
    )
    page = workday_cxs_detail_page(
        public_detail_url=PUBLIC_DETAIL,
        public_board_url=BOARD,
        response_url=CXS_DETAIL,
        status_code=200,
        body=_detail_body(description=description),
        allowed_hosts={WORKDAY_HOST},
    )
    assert page is not None

    # The raw JSON contains the key `jobPostingInfo`, which includes the existing
    # `jobposting` marker. The projection intentionally excludes that wrapper so
    # metadata alone cannot turn a weak description into a passing proof.
    assert "jobposting" not in f"{page.title} {page.text} {page.html}".casefold()
    assert genuine_job_detail_proof(
        page,
        allowed_hosts={WORKDAY_HOST},
        known_detail=True,
    ) is None


def test_cxs_projection_fails_closed_on_wrong_endpoint_or_http_failure() -> None:
    assert workday_cxs_detail_page(
        public_detail_url=PUBLIC_DETAIL,
        public_board_url=BOARD,
        response_url=f"https://{WORKDAY_HOST}/wday/cxs/acme/other/job/X",
        status_code=200,
        body=_detail_body(),
        allowed_hosts={WORKDAY_HOST},
    ) is None
    assert workday_cxs_detail_page(
        public_detail_url=PUBLIC_DETAIL,
        public_board_url=BOARD,
        response_url=CXS_DETAIL,
        status_code=404,
        body=_detail_body(),
        allowed_hosts={WORKDAY_HOST},
    ) is None
