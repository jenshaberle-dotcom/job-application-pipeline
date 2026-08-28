from __future__ import annotations

import json

from src.connectors.employer_origin_workday_navigation import (
    explicit_workday_board_routes_from_employer_page,
    workday_board_route,
    workday_detail_urls_from_inventory,
)


EMPLOYER = "https://jobs.example.com/"
EMPLOYER_HOST = "jobs.example.com"
WORKDAY_HOST = "acme.wd5.myworkdayjobs.com"
BOARD = f"https://{WORKDAY_HOST}/en-US/acmecareers"
INVENTORY = f"https://{WORKDAY_HOST}/wday/cxs/acme/acmecareers/jobs"
DETAIL = f"{BOARD}/job/Platform-Engineer_JR12345"


def test_control_path_consensus_derives_exact_workday_board() -> None:
    html = f"""
    <html><body>
      <a href="https://{WORKDAY_HOST}/en-US/acmecareers/introduceYourself">Join talent community</a>
      <a href="https://{WORKDAY_HOST}/en-US/acmecareers/login">Sign In</a>
    </body></html>
    """

    routes = explicit_workday_board_routes_from_employer_page(
        page_url=EMPLOYER,
        html=html,
        allowed_hosts={EMPLOYER_HOST},
    )

    assert len(routes) == 1
    assert routes[0].host == WORKDAY_HOST
    assert routes[0].tenant == "acme"
    assert routes[0].site == "acmecareers"
    assert routes[0].locale == "en-US"
    assert routes[0].public_board_url == BOARD
    assert routes[0].inventory_url == INVENTORY


def test_one_control_path_is_insufficient_to_create_board_authority() -> None:
    html = (
        f'<a href="https://{WORKDAY_HOST}/en-US/acmecareers/login">Sign In</a>'
    )

    assert explicit_workday_board_routes_from_employer_page(
        page_url=EMPLOYER,
        html=html,
        allowed_hosts={EMPLOYER_HOST},
    ) == ()


def test_conflicting_control_sites_fail_closed() -> None:
    html = f"""
    <a href="https://{WORKDAY_HOST}/en-US/acmecareers/introduceYourself">Join</a>
    <a href="https://{WORKDAY_HOST}/en-US/other/login">Sign In</a>
    """

    assert explicit_workday_board_routes_from_employer_page(
        page_url=EMPLOYER,
        html=html,
        allowed_hosts={EMPLOYER_HOST},
    ) == ()


def test_explicit_visible_board_anchor_is_sufficient() -> None:
    html = f'<a href="{BOARD}">View jobs</a>'

    routes = explicit_workday_board_routes_from_employer_page(
        page_url=EMPLOYER,
        html=html,
        allowed_hosts={EMPLOYER_HOST},
    )

    assert len(routes) == 1
    assert routes[0].public_board_url == BOARD


def test_unbound_employer_page_cannot_delegate_workday() -> None:
    html = f"""
    <a href="https://{WORKDAY_HOST}/en-US/acmecareers/introduceYourself">Join</a>
    <a href="https://{WORKDAY_HOST}/en-US/acmecareers/login">Sign In</a>
    """

    assert explicit_workday_board_routes_from_employer_page(
        page_url=EMPLOYER,
        html=html,
        allowed_hosts={"other.example.com"},
    ) == ()


def test_workday_board_contract_and_inventory_projection_remain_strict() -> None:
    route = workday_board_route(BOARD, allowed_hosts={WORKDAY_HOST})
    assert route is not None
    assert route.inventory_url == INVENTORY

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
        inventory_url=INVENTORY,
        body=body,
        public_board_url=BOARD,
        allowed_hosts={WORKDAY_HOST},
        limit=1,
    ) == (DETAIL,)
