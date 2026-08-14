from __future__ import annotations

from scripts.run_provider001b_provider_evidence_discovery import PROVIDER_PATTERNS
from src.search_intelligence.ats_provider_registry import (
    ATS_PROVIDER_REGISTRY_VERSION,
    classify_provider_names,
    is_known_ats_host,
    provider_pattern_dicts,
    recognize_ats_provider,
)
from src.search_intelligence.connector_feasibility import ProbeFetchResult
from src.search_intelligence.listing_surface_evidence import analyze_listing_surface


def test_bridgingit_personio_host_is_recognized_without_granting_authority() -> None:
    recognition = recognize_ats_provider("https://bridgingit.jobs.personio.de/")

    assert recognition is not None
    assert recognition.contract_version == ATS_PROVIDER_REGISTRY_VERSION
    assert recognition.provider == "personio"
    assert recognition.target_hint == "bridgingit"
    assert recognition.next_action == "validate_personio_target_authority"
    assert recognition.provider_recognized is True
    assert recognition.tenant_authority is False
    assert recognition.delegation_permitted is False
    assert recognition.product_authority is False


def test_known_provider_recognition_is_not_a_hostname_lookalike_escape() -> None:
    assert is_known_ats_host("https://bridgingit.jobs.personio.de/") is True
    assert is_known_ats_host("https://bridgingit.jobs.personio.de.evil.test/jobs") is False
    assert is_known_ats_host("https://jobs.evil.test/personio.de/jobs") is False
    assert recognize_ats_provider("https://jobs.evil.test/") is None


def test_registry_covers_existing_provider_evidence_families() -> None:
    projected = {str(item["provider"]) for item in provider_pattern_dicts()}
    assert {
        "greenhouse",
        "personio",
        "workday",
        "successfactors",
        "smartrecruiters",
        "lever",
        "ashby",
        "recruitee",
        "workable",
        "softgarden",
        "dvinci",
        "onlyfy",
        "icims",
        "oracle",
    }.issubset(projected)


def test_legacy_provider_evidence_patterns_cannot_drift_from_registry() -> None:
    assert provider_pattern_dicts() == PROVIDER_PATTERNS


def test_text_classification_is_evidence_only_and_can_find_multiple_providers() -> None:
    providers = classify_provider_names(
        "Observed https://boards.greenhouse.io/acme and https://acme.jobs.personio.de/"
    )
    assert providers == ("greenhouse", "personio")


def test_listing_reuses_registry_for_external_personio_route_before_booster() -> None:
    origin = "https://www.bridging-it.com/de/karriere"
    personio = "https://bridgingit.jobs.personio.de/jobs"
    evidence = analyze_listing_surface(
        origin_url=origin,
        fetch_result=ProbeFetchResult(
            final_url=origin,
            http_status=200,
            body=f'<iframe src="{personio}"></iframe>',
            error=None,
        ),
    )

    assert evidence.classification == "deterministic_listing_route_candidate"
    assert evidence.route_candidates == (personio,)
    assert evidence.external_search_gap is False
    assert evidence.product_authority is False


def test_listing_does_not_trust_personio_lookalike_iframe() -> None:
    origin = "https://www.bridging-it.com/de/karriere"
    lookalike = "https://bridgingit.jobs.personio.de.evil.test/jobs"
    evidence = analyze_listing_surface(
        origin_url=origin,
        fetch_result=ProbeFetchResult(
            final_url=origin,
            http_status=200,
            body=f'<iframe src="{lookalike}"></iframe>',
            error=None,
        ),
    )

    assert evidence.route_candidates == ()
    assert evidence.external_search_gap is True
