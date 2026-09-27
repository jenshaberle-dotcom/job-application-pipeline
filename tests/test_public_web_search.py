from __future__ import annotations

from src.search_intelligence.public_web_search import (
    PublicSearchResult,
    deduplicate_public_results,
    parse_duckduckgo_html_results,
)


def test_duckduckgo_html_parser_is_provider_generic_and_decodes_outbound_urls() -> None:
    html = """
    <html><body>
      <a href="/html/">DuckDuckGo</a>
      <a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.linkedin.com%2Fjobs%2Fview%2F123456%2F">
        HDI Group sucht AI Engineer
      </a>
      <a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fcareers">Example Careers</a>
    </body></html>
    """

    results = parse_duckduckgo_html_results(
        html,
        query='site:linkedin.com/jobs/view "AI Engineer" Hannover',
        base_url="https://html.duckduckgo.com/html/?q=x",
        max_results=10,
    )

    assert [item.url for item in results] == [
        "https://www.linkedin.com/jobs/view/123456/",
        "https://example.com/careers",
    ]
    assert results[0].title == "HDI Group sucht AI Engineer"
    assert results[0].snippet == ""
    assert results[0].provider == "duckduckgo_html"


def test_duckduckgo_parser_deduplicates_and_respects_bound() -> None:
    html = """
    <a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa">A</a>
    <a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa">A duplicate</a>
    <a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fb">B</a>
    """

    results = parse_duckduckgo_html_results(
        html,
        query="q",
        max_results=1,
    )

    assert len(results) == 1
    assert results[0].url == "https://example.com/a"


def test_public_result_dedup_is_transport_level_not_platform_specific() -> None:
    values = (
        PublicSearchResult("https://example.com/a", "A", "", "q", "duckduckgo_html"),
        PublicSearchResult("https://example.com/a", "A2", "", "q2", "duckduckgo_html"),
        PublicSearchResult("https://example.com/a", "A3", "", "q", "tavily"),
    )

    assert len(deduplicate_public_results(values)) == 2
