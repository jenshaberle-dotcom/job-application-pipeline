from __future__ import annotations

from src.connectors.employer_origin_provider_delegation import (
    canonical_provider_delegated_detail_urls,
    canonical_provider_detail_host,
    explicit_canonical_provider_detail_urls,
)


PAGE = "https://karriere.example.invalid/stellenboerse"
DVINCI_DETAIL = "https://example-karriere.dvinci-hr.com/de/jobs/118/intro"
PERSONIO_DETAIL = "https://comrce.jobs.personio.de/job/1958197?language=de&display=de"
SMART_DETAIL = (
    "https://jobs.smartrecruiters.com/Wavestone1/"
    "744000143599414-junior-ai-engineer-pittsburgh-pa"
)
SMART_UUID_DETAIL = (
    "https://jobs.smartrecruiters.com/ni/Wavestone1/"
    "1f6eb995-5980-4237-b137-4bf2b16d80ce-ai-for-digital-foundations-consultant"
)


def test_dvinci_detail_requires_canonical_same_provider_host_and_strict_route() -> None:
    html = (
        f"<a href='{DVINCI_DETAIL}'>Initiativbewerbung</a>"
        "<a href='https://example-karriere.dvinci-hr.com/de/jobs'>Jobs</a>"
        "<a href='https://other.jobs.personio.de/job/12345'>Other ATS</a>"
        "<a href='https://example-karriere.dvinci-hr.com/de/jobs/119/role'></a>"
    )

    assert canonical_provider_delegated_detail_urls(
        provider="dvinci",
        page_url=PAGE,
        html=html,
        allowed_hosts=("karriere.example.invalid",),
    ) == (DVINCI_DETAIL,)


def test_explicit_personio_detail_can_delegate_only_from_canonical_jobs_tenant() -> None:
    html = (
        "<script>window.jobs={\"detail\":\""
        + PERSONIO_DETAIL
        + "\",\"marketing\":\"https://www.personio.de/job/1958197\","
        + "\"slug\":\"https://other.jobs.personio.de/job/not-numeric\"}</script>"
    )

    assert explicit_canonical_provider_detail_urls(
        page_url=PAGE,
        html=html,
        allowed_hosts=("karriere.example.invalid",),
    ) == (("personio", PERSONIO_DETAIL),)
    assert canonical_provider_delegated_detail_urls(
        provider="personio",
        page_url=PAGE,
        html=html,
        allowed_hosts=("karriere.example.invalid",),
    ) == (PERSONIO_DETAIL,)


def test_explicit_smartrecruiters_details_can_be_embedded_without_anchor_markup() -> None:
    html = (
        "<script>window.jobs={\"one\":\""
        + SMART_DETAIL
        + "\",\"two\":\""
        + SMART_UUID_DETAIL
        + "\",\"internal\":\""
        + "https://jobs.smartrecruiters.com/oneclick-ui/company/122/job/151/publication/0"
        + "\"}</script>"
    )

    assert explicit_canonical_provider_detail_urls(
        page_url=PAGE,
        html=html,
        allowed_hosts=("karriere.example.invalid",),
    ) == (
        ("smartrecruiters", SMART_DETAIL),
        ("smartrecruiters", SMART_UUID_DETAIL),
    )
    assert canonical_provider_delegated_detail_urls(
        provider="smartrecruiters",
        page_url=PAGE,
        html=html,
        allowed_hosts=("karriere.example.invalid",),
    ) == (SMART_DETAIL, SMART_UUID_DETAIL)


def test_explicit_provider_surface_requires_authorized_source_and_strict_public_detail() -> None:
    html = (
        f"smartrecruiters {SMART_DETAIL} "
        "https://jobs.smartrecruiters.com/Wavestone1 "
        "https://jobs.smartrecruiters.com/oneclick-ui/company/122/job/151/publication/0 "
        "https://example.invalid/Wavestone1/744000143599414-junior-ai-engineer"
    )

    assert explicit_canonical_provider_detail_urls(
        page_url=PAGE,
        html=html,
        allowed_hosts=("other.example.invalid",),
    ) == ()
    assert explicit_canonical_provider_detail_urls(
        page_url=PAGE,
        html="smartrecruiters only, no concrete canonical detail",
        allowed_hosts=("karriere.example.invalid",),
    ) == ()


def test_provider_name_alone_or_wrong_source_host_never_delegates() -> None:
    html = f"dvinci <a href='{DVINCI_DETAIL}'>Initiativbewerbung</a>"

    assert canonical_provider_delegated_detail_urls(
        provider="dvinci",
        page_url=PAGE,
        html=html,
        allowed_hosts=("other.example.invalid",),
    ) == ()
    assert canonical_provider_delegated_detail_urls(
        provider="workday",
        page_url=PAGE,
        html=html,
        allowed_hosts=("karriere.example.invalid",),
    ) == ()


def test_canonical_provider_detail_host_must_match_provider_and_strict_route() -> None:
    assert canonical_provider_detail_host(provider="dvinci", url=DVINCI_DETAIL) == (
        "example-karriere.dvinci-hr.com"
    )
    assert canonical_provider_detail_host(provider="personio", url=PERSONIO_DETAIL) == (
        "comrce.jobs.personio.de"
    )
    assert canonical_provider_detail_host(provider="smartrecruiters", url=SMART_DETAIL) == (
        "jobs.smartrecruiters.com"
    )
    assert canonical_provider_detail_host(provider="personio", url=DVINCI_DETAIL) is None
    assert canonical_provider_detail_host(
        provider="personio",
        url="https://www.personio.de/job/1958197",
    ) is None
    assert canonical_provider_detail_host(
        provider="personio",
        url="https://other.jobs.personio.de/job/not-numeric",
    ) is None
    assert canonical_provider_detail_host(
        provider="dvinci",
        url="http://example-karriere.dvinci-hr.com/de/jobs/118/intro",
    ) is None
