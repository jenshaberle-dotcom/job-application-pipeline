from __future__ import annotations

from src.search_intelligence.ats_delegation_evidence import (
    ValidatedATSAuthority,
    analyze_ats_delegation,
)


def test_known_personio_hypothesis_routes_to_deterministic_authority_before_booster() -> None:
    evidence = analyze_ats_delegation(
        candidate_urls=("https://bridgingit.jobs.personio.de/",),
    )

    assert evidence.provider == "personio"
    assert evidence.classification == "ats_provider_recognized_binding_required"
    assert evidence.target_hints == ("bridgingit",)
    assert evidence.semantic_booster_eligible is False
    assert evidence.tenant_authority is False
    assert evidence.delegation_permitted is False
    assert evidence.next_action == "validate_personio_target_authority"
    assert evidence.product_authority is False


def test_employer_backed_personio_url_still_requires_provider_specific_authority() -> None:
    personio = "https://bridgingit.jobs.personio.de/"
    evidence = analyze_ats_delegation(
        candidate_urls=(personio,),
        employer_backed_urls=(personio,),
    )

    assert evidence.provider == "personio"
    assert evidence.employer_backed_provider_binding is True
    assert evidence.classification == "ats_provider_target_authority_required"
    assert evidence.semantic_booster_eligible is False
    assert evidence.tenant_authority is False
    assert evidence.delegation_permitted is False


def test_only_matching_provider_specific_authority_can_enable_delegation() -> None:
    personio = "https://bridgingit.jobs.personio.de/"
    evidence = analyze_ats_delegation(
        candidate_urls=(personio,),
        employer_backed_urls=(personio,),
        validated_authority=ValidatedATSAuthority(
            provider="personio",
            target_key="bridgingit",
            employer_identity_bound=True,
            evidence_ref="fixture://bridgingit/personio-authority",
        ),
    )

    assert evidence.classification == "ats_delegation_ready"
    assert evidence.tenant_authority is True
    assert evidence.delegation_permitted is True
    assert evidence.semantic_booster_eligible is False
    assert evidence.authority_evidence_ref == "fixture://bridgingit/personio-authority"
    assert evidence.product_authority is False


def test_wrong_target_or_unbound_authority_cannot_enable_delegation() -> None:
    personio = "https://bridgingit.jobs.personio.de/"
    wrong_target = analyze_ats_delegation(
        candidate_urls=(personio,),
        employer_backed_urls=(personio,),
        validated_authority=ValidatedATSAuthority(
            provider="personio",
            target_key="other-company",
            employer_identity_bound=True,
            evidence_ref="fixture://wrong-target",
        ),
    )
    unbound = analyze_ats_delegation(
        candidate_urls=(personio,),
        employer_backed_urls=(personio,),
        validated_authority=ValidatedATSAuthority(
            provider="personio",
            target_key="bridgingit",
            employer_identity_bound=False,
            evidence_ref="fixture://unbound",
        ),
    )

    for evidence in (wrong_target, unbound):
        assert evidence.tenant_authority is False
        assert evidence.delegation_permitted is False
        assert evidence.classification == "ats_provider_target_authority_required"


def test_unknown_provider_is_the_only_first_slice_semantic_gap() -> None:
    evidence = analyze_ats_delegation(
        candidate_urls=("https://careers.unknown-example.test/jobs",),
    )

    assert evidence.provider is None
    assert evidence.classification == "ats_provider_unrecognized"
    assert evidence.semantic_booster_eligible is True
    assert evidence.delegation_permitted is False
    assert evidence.next_action == "external_ats_information_eligible"


def test_multiple_known_providers_fail_closed_before_semantic_booster() -> None:
    evidence = analyze_ats_delegation(
        candidate_urls=(
            "https://bridgingit.jobs.personio.de/",
            "https://boards.greenhouse.io/bridgingit",
        ),
    )

    assert evidence.provider is None
    assert evidence.classification == "ats_provider_conflict"
    assert evidence.semantic_booster_eligible is False
    assert evidence.delegation_permitted is False
    assert evidence.next_action == "resolve_provider_conflict_deterministically"


def test_evidence_fingerprint_is_order_stable() -> None:
    first = analyze_ats_delegation(
        candidate_urls=(
            "https://bridgingit.jobs.personio.de/jobs",
            "https://bridgingit.jobs.personio.de/",
        ),
    )
    second = analyze_ats_delegation(
        candidate_urls=(
            "https://bridgingit.jobs.personio.de/",
            "https://bridgingit.jobs.personio.de/jobs",
        ),
    )

    assert first.evidence_fingerprint == second.evidence_fingerprint
