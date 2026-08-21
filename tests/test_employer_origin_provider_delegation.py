from __future__ import annotations

from src.connectors.employer_origin_provider_delegation import (
    canonical_provider_delegated_detail_urls,
    canonical_provider_detail_host,
)


PAGE = "https://karriere.example.invalid/stellenboerse"
DVINCI_DETAIL = "https://example-karriere.dvinci-hr.com/de/jobs/118/intro"


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


def test_canonical_provider_detail_host_must_match_provider_and_https() -> None:
    assert canonical_provider_detail_host(provider="dvinci", url=DVINCI_DETAIL) == (
        "example-karriere.dvinci-hr.com"
    )
    assert canonical_provider_detail_host(provider="personio", url=DVINCI_DETAIL) is None
    assert canonical_provider_detail_host(
        provider="dvinci",
        url="http://example-karriere.dvinci-hr.com/de/jobs/118/intro",
    ) is None
