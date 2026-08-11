from src.search_intelligence.bounded_origin_candidate_hypotheses import (
    generate_bounded_origin_candidate_hypotheses,
)


def test_small_budget_covers_de_and_com_for_single_brand() -> None:
    urls = [
        item.url
        for item in generate_bounded_origin_candidate_hypotheses(
            company_key="examplebrand",
            company_name="Examplebrand GmbH",
            source_family_candidate="examplebrand",
            max_candidates=12,
        )
    ]

    assert len(urls) == 12
    assert "https://jobs.examplebrand.de/" in urls
    assert "https://jobs.examplebrand.com/" in urls
    assert "https://www.examplebrand.com/stellenangebote" in urls


def test_multi_token_identity_includes_short_leading_brand_host() -> None:
    urls = [
        item.url
        for item in generate_bounded_origin_candidate_hypotheses(
            company_key="example_security_networks",
            company_name="Example Security Networks AG",
            source_family_candidate="example_security_networks",
            max_candidates=12,
        )
    ]

    assert "https://jobs.example.com/" in urls
    assert "https://jobs.example.de/" in urls
    assert any("example-security" in url for url in urls)


def test_locality_only_identity_does_not_generate_brand_hypotheses() -> None:
    urls = generate_bounded_origin_candidate_hypotheses(
        company_key="hannover",
        company_name="Hannover GmbH",
        source_family_candidate="hannover",
        max_candidates=12,
    )

    assert urls == ()
