from __future__ import annotations

from src.connectors.employer_origin_sitemap_navigation import (
    sitemap_detail_urls,
    standard_same_host_sitemap_url,
)


HOST = "jobs.example.invalid"
SITEMAP = f"https://{HOST}/sitemap.xml"
DETAIL = f"https://{HOST}/job/Berlin-Platform-Engineer-BE-10115/1234567890"


def test_standard_sitemap_stays_on_exact_authorized_https_host() -> None:
    assert standard_same_host_sitemap_url(
        page_url=f"https://{HOST}/careers",
        allowed_hosts=(HOST,),
    ) == SITEMAP
    assert standard_same_host_sitemap_url(
        page_url="http://jobs.example.invalid/careers",
        allowed_hosts=(HOST,),
    ) is None
    assert standard_same_host_sitemap_url(
        page_url=f"https://{HOST}/careers",
        allowed_hosts=("other.example.invalid",),
    ) is None


def test_urlset_emits_only_strict_same_host_detail_shapes() -> None:
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>{DETAIL}</loc></url>
      <url><loc>https://{HOST}/go/Germany/1234</loc></url>
      <url><loc>https://other.example.invalid/job/Paris-Engineer/987654321</loc></url>
    </urlset>
    """
    assert sitemap_detail_urls(
        sitemap_url=SITEMAP,
        body=xml,
        allowed_hosts=(HOST,),
    ) == (DETAIL,)


def test_sitemap_index_does_not_create_unbounded_second_stage() -> None:
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://{HOST}/jobs-sitemap.xml</loc></sitemap>
    </sitemapindex>
    """
    assert sitemap_detail_urls(
        sitemap_url=SITEMAP,
        body=xml,
        allowed_hosts=(HOST,),
    ) == ()


def test_malformed_xml_fails_closed() -> None:
    assert sitemap_detail_urls(
        sitemap_url=SITEMAP,
        body="<urlset><url>",
        allowed_hosts=(HOST,),
    ) == ()
