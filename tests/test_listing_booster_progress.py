from __future__ import annotations

from src.search_intelligence.listing_booster_progress import (
    ListingProgressLedger,
    normalize_listing_candidate_url,
)


def test_functional_query_identity_is_preserved() -> None:
    first = normalize_listing_candidate_url(
        "https://jobs.example.com/de?id=458ccb&utm_source=test#fragment"
    )
    second = normalize_listing_candidate_url(
        "https://jobs.example.com/de?id=999999&utm_medium=email"
    )
    assert first == "https://jobs.example.com/de?id=458ccb"
    assert second == "https://jobs.example.com/de?id=999999"
    assert first != second


def test_plausible_listing_route_is_not_rejected_before_listing_validation() -> None:
    assert normalize_listing_candidate_url(
        "https://jobs.example.com/open-positions"
    ) == "https://jobs.example.com/open-positions"


def test_tracking_only_differences_dedupe() -> None:
    ledger = ListingProgressLedger()
    urls = ledger.novel_urls(
        [
            "https://jobs.example.com/jobs?utm_source=a",
            "https://jobs.example.com/jobs?utm_source=b#top",
        ]
    )
    assert urls == ("https://jobs.example.com/jobs",)


def test_auth_and_aggregator_shapes_are_rejected() -> None:
    assert normalize_listing_candidate_url("https://jobs.example.com/login") is None
    assert normalize_listing_candidate_url("https://www.stepstone.de/jobs/data") is None


def test_clone_checks_novelty_without_consuming_original() -> None:
    ledger = ListingProgressLedger()
    ledger.novel_urls(["https://jobs.example.com/jobs"])
    probe = ledger.clone()
    assert probe.novel_urls(["https://jobs.example.com/jobs?id=1"]) == (
        "https://jobs.example.com/jobs?id=1",
    )
    assert "https://jobs.example.com/jobs?id=1" not in ledger.attempted_urls


def test_query_no_repeat_is_case_and_whitespace_insensitive() -> None:
    ledger = ListingProgressLedger()
    assert ledger.novel_queries([" Example   Jobs "]) == ("Example   Jobs",)
    assert ledger.novel_queries(["example jobs"]) == ()
