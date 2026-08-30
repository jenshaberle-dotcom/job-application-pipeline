from __future__ import annotations

import json

from src.connectors.employer_origin_provider_public_feed import (
    acquire_via_provider_public_feed,
    parse_provider_public_feed,
    provider_public_feed_url,
    provider_public_feed_urls,
)


def test_fixed_feed_urls_require_existing_host_authority() -> None:
    assert provider_public_feed_urls(
        provider="successfactors",
        page_url="https://jobs.example.com/",
        allowed_hosts={"jobs.example.com"},
    ) == (
        "https://jobs.example.com/sitemap.xml",
        "https://jobs.example.com/sitemal.xml",
    )
    assert provider_public_feed_url(
        provider="successfactors",
        page_url="https://jobs.example.com/",
        allowed_hosts={"jobs.example.com"},
    ) == "https://jobs.example.com/sitemap.xml"

    assert provider_public_feed_url(
        provider="softgarden",
        page_url="https://acme.career.softgarden.de/jobs",
        allowed_hosts={"acme.career.softgarden.de"},
    ) == "https://acme.career.softgarden.de/jobs.feed.json"

    assert provider_public_feed_url(
        provider="recruitee",
        page_url="https://acme.recruitee.com/",
        allowed_hosts={"acme.recruitee.com"},
    ) == "https://acme.recruitee.com/api/offers"

    assert provider_public_feed_url(
        provider="dvinci",
        page_url="https://acme.dvinci.de/portal/tech/en/jobs",
        allowed_hosts={"acme.dvinci.de"},
    ) == "https://acme.dvinci.de/portal/tech/jobPublication/list.json?fields=small"


def test_canonical_only_feed_families_reject_branded_or_guessed_hosts() -> None:
    assert provider_public_feed_url(
        provider="softgarden",
        page_url="https://careers.example.com/",
        allowed_hosts={"careers.example.com"},
    ) is None
    assert provider_public_feed_url(
        provider="recruitee",
        page_url="https://careers.example.com/",
        allowed_hosts={"careers.example.com"},
    ) is None
    assert provider_public_feed_url(
        provider="dvinci",
        page_url="https://careers.example.com/",
        allowed_hosts={"careers.example.com"},
    ) is None


def test_successfactors_sitemap_parser_keeps_strict_same_host_detail_shapes() -> None:
    body = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://jobs.example.com/job/Berlin-Engineer/1234567890</loc></url>
      <url><loc>https://jobs.example.com/content/about</loc></url>
      <url><loc>https://evil.example/job/Berlin-Engineer/9999999999</loc></url>
    </urlset>
    """
    assert parse_provider_public_feed(
        provider="successfactors",
        feed_url="https://jobs.example.com/sitemap.xml",
        body=body,
        allowed_hosts={"jobs.example.com"},
    ) == ("https://jobs.example.com/job/Berlin-Engineer/1234567890",)


def test_successfactors_rss_parser_emits_same_host_links_only() -> None:
    body = """
    <rss version="2.0"><channel>
      <item><title>One</title><link>https://jobs.example.com/job/one/123-en_US/</link></item>
      <item><title>Cross</title><link>https://evil.example/job/two/456-en_US/</link></item>
    </channel></rss>
    """
    assert parse_provider_public_feed(
        provider="successfactors",
        feed_url="https://jobs.example.com/sitemal.xml",
        body=body,
        allowed_hosts={"jobs.example.com"},
    ) == ("https://jobs.example.com/job/one/123-en_US",)


def test_softgarden_datafeed_requires_consistent_count_and_job_rows() -> None:
    good = json.dumps(
        {
            "numberOfItems": 1,
            "dataFeedElement": [
                {
                    "item": {
                        "@type": "JobPosting",
                        "url": "https://acme.career.softgarden.de/job/123",
                    }
                }
            ],
        }
    )
    assert parse_provider_public_feed(
        provider="softgarden",
        feed_url="https://acme.career.softgarden.de/jobs.feed.json",
        body=good,
        allowed_hosts={"acme.career.softgarden.de"},
    ) == ("https://acme.career.softgarden.de/job/123",)

    bad = json.dumps({"numberOfItems": 2, "dataFeedElement": []})
    assert not parse_provider_public_feed(
        provider="softgarden",
        feed_url="https://acme.career.softgarden.de/jobs.feed.json",
        body=bad,
        allowed_hosts={"acme.career.softgarden.de"},
    )


def test_recruitee_parser_uses_concrete_careers_url_without_slug_guessing() -> None:
    body = json.dumps(
        {
            "offers": [
                {
                    "id": 7,
                    "careers_url": "https://acme.recruitee.com/o/data-engineer",
                }
            ]
        }
    )
    assert parse_provider_public_feed(
        provider="recruitee",
        feed_url="https://acme.recruitee.com/api/offers",
        body=body,
        allowed_hosts={"acme.recruitee.com"},
    ) == ("https://acme.recruitee.com/o/data-engineer",)


def test_dvinci_parser_rejects_external_publication_urls() -> None:
    body = json.dumps(
        [
            {
                "id": 5,
                "jobPublicationURL": "https://acme.dvinci.de/de/jobs/5/data-engineer",
            },
            {
                "id": 6,
                "jobPublicationURL": "https://external.example/jobs/6",
            },
        ]
    )
    assert parse_provider_public_feed(
        provider="dvinci",
        feed_url="https://acme.dvinci.de/jobPublication/list.json?fields=small",
        body=body,
        allowed_hosts={"acme.dvinci.de"},
    ) == ("https://acme.dvinci.de/de/jobs/5/data-engineer",)


def test_acquisition_prefers_historical_successfactors_sitemap_and_unchanged_proof() -> None:
    root = "https://jobs.example.com/"
    sitemap = "https://jobs.example.com/sitemap.xml"
    detail = "https://jobs.example.com/job/data-engineer/1234567890"
    payloads = {
        root.rstrip("/"): (
            '<html><head><title>Jobs</title></head><body>'
            '<script src="https://hcm55.sapsf.eu/platform.js"></script>'
            "</body></html>",
            root,
            200,
        ),
        sitemap: (
            f"<urlset><url><loc>{detail}</loc></url></urlset>",
            sitemap,
            200,
        ),
        detail: (
            "<html><head><title>Data Engineer</title></head>"
            "<body>Job Description Responsibilities Requirements Apply now</body></html>",
            detail,
            200,
        ),
    }
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        return payloads[url.rstrip("/") if url.rstrip("/") in payloads else url]

    result = acquire_via_provider_public_feed(
        listing_url=root,
        allowed_hosts=("jobs.example.com",),
        fetcher=fetcher,
        max_detail_attempts=1,
    )

    assert result is not None
    assert result.provider == "successfactors"
    assert result.feed_url == sitemap
    assert result.acquired_job is not None
    assert result.acquired_job.proof_kind == "job_url_and_job_content"
    assert result.acquired_job.discovery_source == "successfactors_provider_public_feed"
    assert calls == [root, sitemap, detail]


def test_successfactors_rss_is_bounded_fallback_when_sitemap_has_no_inventory() -> None:
    root = "https://jobs.example.com/"
    sitemap = "https://jobs.example.com/sitemap.xml"
    rss = "https://jobs.example.com/sitemal.xml"
    detail = "https://jobs.example.com/job/data-engineer/123-en_US/"
    payloads = {
        root.rstrip("/"): (
            '<html><script src="https://hcm55.sapsf.eu/platform.js"></script></html>',
            root,
            200,
        ),
        sitemap: ("<html>not a sitemap</html>", sitemap, 200),
        rss: (
            f"<rss><channel><item><link>{detail}</link></item></channel></rss>",
            rss,
            200,
        ),
        detail.rstrip("/"): (
            "<html><title>Data Engineer</title><body>"
            "Responsibilities Requirements Apply now</body></html>",
            detail,
            200,
        ),
    }
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        return payloads[url.rstrip("/") if url.rstrip("/") in payloads else url]

    result = acquire_via_provider_public_feed(
        listing_url=root,
        allowed_hosts=("jobs.example.com",),
        fetcher=fetcher,
        max_detail_attempts=1,
    )

    assert result is not None
    assert result.feed_url == rss
    assert result.acquired_job is not None
    assert calls == [root, sitemap, rss, detail]


def test_acquisition_fails_closed_when_neither_successfactors_feed_validates() -> None:
    root = "https://jobs.example.com/"
    sitemap = "https://jobs.example.com/sitemap.xml"
    rss = "https://jobs.example.com/sitemal.xml"
    payloads = {
        root.rstrip("/"): (
            '<html><script src="https://hcm55.sapsf.eu/platform.js"></script></html>',
            root,
            200,
        ),
        sitemap: ("<html>not sitemap</html>", sitemap, 200),
        rss: ("<html>not rss</html>", rss, 200),
    }

    def fetcher(url: str):
        return payloads[url.rstrip("/") if url.rstrip("/") in payloads else url]

    result = acquire_via_provider_public_feed(
        listing_url=root,
        allowed_hosts=("jobs.example.com",),
        fetcher=fetcher,
        max_detail_attempts=1,
    )

    assert result is not None
    assert result.acquired_job is None
    assert result.detail_candidates == ()
