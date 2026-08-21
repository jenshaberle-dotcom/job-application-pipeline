from __future__ import annotations

from src.connectors.employer_origin_ats_navigation import (
    authorized_ats_provider,
    provider_detail_urls,
    provider_listing_urls,
)


EMPLOYER = "https://www.example.invalid/careers"
BRANDED_ATS = "https://jobs.example.invalid/"
CANONICAL_ATS = "https://acme.wd5.myworkdayjobs.com/en-US/acme"
GERMANY = "https://jobs.example.invalid/go/germany/4411601"
BELGIUM = "https://jobs.example.invalid/go/belgium/4411501"
PERSONIO = "https://x1f.jobs.personio.de/"
PERSONIO_XML = "https://x1f.jobs.personio.de/xml?language=de"
SMART_DETAIL = (
    "https://jobs.smartrecruiters.com/Wavestone1/"
    "744000143599414-junior-ai-engineer-pittsburgh-pa"
)


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


def test_strict_embedded_canonical_detail_can_recognize_provider_on_employer_page() -> None:
    assert (
        authorized_ats_provider(
            page_url=EMPLOYER,
            html=f'<script>window.jobUrl="{SMART_DETAIL}"</script>',
            allowed_hosts=("www.example.invalid",),
        )
        == "smartrecruiters"
    )


def test_provider_text_or_internal_route_without_public_detail_does_not_authorize() -> None:
    html = (
        "smartrecruiters "
        "https://jobs.smartrecruiters.com/oneclick-ui/company/122/job/151/publication/0"
    )
    assert (
        authorized_ats_provider(
            page_url=EMPLOYER,
            html=html,
            allowed_hosts=("www.example.invalid",),
        )
        is None
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


def test_canonical_personio_host_exposes_existing_public_xml_inventory_route() -> None:
    assert provider_listing_urls(
        provider="personio",
        page_url=PERSONIO,
        html="<html><body>Jobs</body></html>",
        allowed_hosts=("x1f.jobs.personio.de",),
    ) == (PERSONIO_XML,)


def test_personio_xml_inventory_exposes_bounded_same_tenant_detail_urls() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <workzag-jobs>
      <position><id>123456</id><name>Data Engineer</name></position>
      <position><id>abc-789</id><name>Platform Engineer</name></position>
    </workzag-jobs>
    """

    assert provider_detail_urls(
        provider="personio",
        page_url=PERSONIO_XML,
        body=xml,
        allowed_hosts=("x1f.jobs.personio.de",),
    ) == (
        "https://x1f.jobs.personio.de/job/123456?language=de",
        "https://x1f.jobs.personio.de/job/abc-789?language=de",
    )


def test_personio_routes_fail_closed_for_branded_or_malformed_surfaces() -> None:
    assert provider_listing_urls(
        provider="personio",
        page_url="https://jobs.example.invalid/",
        html="https://x1f.jobs.personio.de/",
        allowed_hosts=("jobs.example.invalid",),
    ) == ()
    assert provider_detail_urls(
        provider="personio",
        page_url=PERSONIO_XML,
        body="<workzag-jobs><position><id>bad id!</id></position></workzag-jobs>",
        allowed_hosts=("x1f.jobs.personio.de",),
    ) == ()
    assert provider_detail_urls(
        provider="personio",
        page_url="https://other.jobs.personio.de/xml?language=de",
        body="<position><id>12345</id></position>",
        allowed_hosts=("x1f.jobs.personio.de",),
    ) == ()


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
