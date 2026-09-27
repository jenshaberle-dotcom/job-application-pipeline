from __future__ import annotations

from src.search_intelligence.official_site_inventory_evidence import (
    discover_official_site_inventory,
)
from src.search_intelligence.origin_jobspace_discovery import FetchedOriginPage


def _page(url: str, body: str, status: int = 200) -> FetchedOriginPage:
    return FetchedOriginPage(
        requested_url=url,
        final_url=url,
        status_code=status,
        html=body,
    )


def test_official_inventory_reads_robots_and_one_bounded_sitemap_index() -> None:
    root = "https://www.example.com/"
    robots = """User-agent: *
Sitemap: https://www.example.com/sitemap-index.xml
Sitemap: https://evil.invalid/sitemap.xml
"""
    index = """<?xml version="1.0"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://www.example.com/pages.xml</loc></sitemap>
  <sitemap><loc>https://careers.example.com/jobs.xml</loc></sitemap>
  <sitemap><loc>https://evil.invalid/jobs.xml</loc></sitemap>
</sitemapindex>
"""
    pages = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.example.com/about</loc></url>
  <url><loc>https://www.example.com/careers</loc></url>
</urlset>
"""
    jobs = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://careers.example.com/jobs/platform-engineer</loc></url>
  <url><loc>https://other.invalid/jobs/nope</loc></url>
</urlset>
"""

    mapping = {
        "https://www.example.com/robots.txt": _page(
            "https://www.example.com/robots.txt", robots
        ),
        "https://www.example.com/sitemap.xml": _page(
            "https://www.example.com/sitemap.xml", "", 404
        ),
        "https://www.example.com/sitemap_index.xml": _page(
            "https://www.example.com/sitemap_index.xml", "", 404
        ),
        "https://www.example.com/sitemap-index.xml": _page(
            "https://www.example.com/sitemap-index.xml", index
        ),
        "https://www.example.com/pages.xml": _page(
            "https://www.example.com/pages.xml", pages
        ),
        "https://careers.example.com/jobs.xml": _page(
            "https://careers.example.com/jobs.xml", jobs
        ),
    }

    def fetch(url: str) -> FetchedOriginPage:
        return mapping.get(url, _page(url, "", 404))

    result = discover_official_site_inventory(
        company_name="Example AG",
        official_domain_urls=(root,),
        fetch_page=fetch,
    )

    assert result.official_root_count == 1
    assert result.robots_fetch_count == 1
    assert result.sitemap_index_count == 1
    assert result.sitemap_urlset_count == 2
    assert [item.url for item in result.evidence] == [
        "https://www.example.com/careers",
        "https://careers.example.com/jobs/platform-engineer",
    ]
    assert {item.provider for item in result.evidence} == {
        "official_site_inventory"
    }


def test_official_inventory_never_crosses_unrelated_host_boundary() -> None:
    root = "https://www.example.com/"
    robots = "Sitemap: https://other.invalid/jobs.xml\n"

    def fetch(url: str) -> FetchedOriginPage:
        if url.endswith("/robots.txt"):
            return _page(url, robots)
        return _page(url, "", 404)

    result = discover_official_site_inventory(
        company_name="Example AG",
        official_domain_urls=(root,),
        fetch_page=fetch,
    )

    assert result.evidence == ()
    assert result.candidate_url_count == 0


def test_official_inventory_is_empty_without_official_domain_evidence() -> None:
    calls: list[str] = []

    def fetch(url: str) -> FetchedOriginPage:
        calls.append(url)
        return _page(url, "", 404)

    result = discover_official_site_inventory(
        company_name="Unknown AG",
        official_domain_urls=(),
        fetch_page=fetch,
    )

    assert result.official_root_count == 0
    assert result.evidence == ()
    assert calls == []
