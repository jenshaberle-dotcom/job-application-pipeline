from __future__ import annotations

from src.connectors.employer_origin_ats_navigation import (
    authorized_ats_provider,
    provider_listing_urls,
)


EMPLOYER = "https://www.example.invalid/careers"
BRANDED_ATS = "https://jobs.example.invalid/"
CANONICAL_ATS = "https://acme.wd5.myworkdayjobs.com/en-US/acme"
GERMANY = "https://jobs.example.invalid/go/germany/4411601"
BELGIUM = "https://jobs.example.invalid/go/belgium/4411501"


def successfactors_html() -> str:
    return (
        "<html><body>"
        '<a href="https://career5.successfactors.eu/career?company=acme">Sign in</a>'
        f'<a href="{GERMANY}/">Germany</a>'
        f'<a href="{BELGIUM}/">Belgium</a>'
        "</body></html>"
    )


def test_branded_delegated_recruiting_host_can_recognize_one_ats_family() -> None:
    assert (
        authorized_ats_provider(
            page_url=BRANDED_ATS,
            html=successfactors_html(),
            allowed_hosts=("jobs.example.invalid",),
            delegated_hosts=("jobs.example.invalid",),
        )
        == "successfactors"
    )


def test_branded_recruiting_host_must_already_be_authorized() -> None:
    assert (
        authorized_ats_provider(
            page_url=BRANDED_ATS,
            html=successfactors_html(),
            allowed_hosts=("www.example.invalid",),
            delegated_hosts=("jobs.example.invalid",),
        )
        is None
    )


def test_canonical_ats_host_recognition_does_not_depend_on_html_hint() -> None:
    assert (
        authorized_ats_provider(
            page_url=CANONICAL_ATS,
            html="<html><body>Loading...</body></html>",
            allowed_hosts=("acme.wd5.myworkdayjobs.com",),
        )
        == "workday"
    )


def test_successfactors_go_routes_are_bounded_to_same_authorized_host() -> None:
    html = (
        successfactors_html()
        + '<a href="https://other.invalid/go/france/1234/">France</a>'
        + '<a href="/privacy">Privacy</a>'
    )

    assert provider_listing_urls(
        provider="successfactors",
        page_url=BRANDED_ATS,
        html=html,
        allowed_hosts=("jobs.example.invalid",),
    ) == (GERMANY, BELGIUM)


def test_unknown_or_unsupported_provider_exposes_no_listing_route() -> None:
    assert (
        provider_listing_urls(
            provider="workday",
            page_url=BRANDED_ATS,
            html=successfactors_html(),
            allowed_hosts=("jobs.example.invalid",),
        )
        == ()
    )
