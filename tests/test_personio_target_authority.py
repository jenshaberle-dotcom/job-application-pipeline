from __future__ import annotations

from pathlib import Path

from src.search_intelligence.ats_delegation_evidence import analyze_ats_delegation
from src.search_intelligence.personio_target_authority import (
    validate_personio_target_authority,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "personio_jobs_sample.xml"


def test_existing_personio_fixture_can_bind_exact_target_to_employer() -> None:
    feed = "https://schluetersche-mediengruppe.jobs.personio.de/xml?language=de"
    evidence = validate_personio_target_authority(
        candidate_url="https://schluetersche-mediengruppe.jobs.personio.de/",
        requested_url=feed,
        final_url=feed,
        xml_content=FIXTURE_PATH.read_bytes(),
        company_key="schluetersche_mediengruppe",
        company_name="Schlütersche Verlagsgesellschaft mbH & Co. KG",
    )

    assert evidence.target_key == "schluetersche-mediengruppe"
    assert evidence.host_identity_valid is True
    assert evidence.feed_route_valid is True
    assert evidence.xml_valid is True
    assert evidence.position_count == 2
    assert evidence.employer_identity_bound is True
    assert evidence.authority_validated is True
    authority = evidence.to_validated_authority()
    assert authority is not None
    assert authority.provider == "personio"
    assert authority.target_key == "schluetersche-mediengruppe"
    assert authority.employer_identity_bound is True


def test_bridgingit_company_identity_can_validate_personio_target_without_llm_authority() -> None:
    xml = b"""
    <workzag-jobs>
      <position>
        <id>42</id>
        <name>Data Engineer</name>
        <subcompany>BridgingIT GmbH</subcompany>
        <office>Stuttgart</office>
      </position>
    </workzag-jobs>
    """
    feed = "https://bridgingit.jobs.personio.de/xml?language=de"
    evidence = validate_personio_target_authority(
        candidate_url="https://bridgingit.jobs.personio.de/",
        requested_url=feed,
        final_url=feed,
        xml_content=xml,
        company_key="bridgingit",
        company_name="BridgingIT GmbH",
    )

    assert evidence.target_key == "bridgingit"
    assert evidence.feed_route_valid is True
    assert evidence.matched_company_name == "BridgingIT GmbH"
    assert evidence.employer_identity_bound is True
    assert evidence.authority_validated is True
    assert evidence.product_authority is False

    delegation = analyze_ats_delegation(
        candidate_urls=("https://bridgingit.jobs.personio.de/",),
        employer_backed_urls=("https://bridgingit.jobs.personio.de/",),
        validated_authority=evidence.to_validated_authority(),
    )
    assert delegation.classification == "ats_delegation_ready"
    assert delegation.delegation_permitted is True
    assert delegation.product_authority is False


def test_personio_target_host_lookalike_cannot_gain_authority() -> None:
    xml = b"<workzag-jobs><position><company>BridgingIT GmbH</company></position></workzag-jobs>"
    evidence = validate_personio_target_authority(
        candidate_url="https://bridgingit.jobs.personio.de/",
        requested_url="https://bridgingit.jobs.personio.de/xml?language=de",
        final_url="https://bridgingit.jobs.personio.de.evil.test/xml?language=de",
        xml_content=xml,
        company_key="bridgingit",
        company_name="BridgingIT GmbH",
    )

    assert evidence.host_identity_valid is False
    assert evidence.feed_route_valid is False
    assert evidence.employer_identity_bound is True
    assert evidence.authority_validated is False
    assert evidence.to_validated_authority() is None


def test_personio_same_host_non_feed_xml_cannot_gain_authority() -> None:
    xml = b"<workzag-jobs><position><company>BridgingIT GmbH</company></position></workzag-jobs>"
    non_feed = "https://bridgingit.jobs.personio.de/jobs"
    evidence = validate_personio_target_authority(
        candidate_url="https://bridgingit.jobs.personio.de/",
        requested_url=non_feed,
        final_url=non_feed,
        xml_content=xml,
        company_key="bridgingit",
        company_name="BridgingIT GmbH",
    )

    assert evidence.host_identity_valid is True
    assert evidence.feed_route_valid is False
    assert evidence.employer_identity_bound is True
    assert evidence.authority_validated is False
    assert "personio_public_xml_feed_route_not_proven" in evidence.reason_codes


def test_personio_wrong_employer_identity_fails_closed() -> None:
    xml = b"<workzag-jobs><position><company>Unrelated Systems GmbH</company></position></workzag-jobs>"
    feed = "https://bridgingit.jobs.personio.de/xml?language=de"
    evidence = validate_personio_target_authority(
        candidate_url="https://bridgingit.jobs.personio.de/",
        requested_url=feed,
        final_url=feed,
        xml_content=xml,
        company_key="bridgingit",
        company_name="BridgingIT GmbH",
    )

    assert evidence.host_identity_valid is True
    assert evidence.feed_route_valid is True
    assert evidence.employer_identity_bound is False
    assert evidence.authority_validated is False
    assert "personio_company_identity_does_not_match_employer" in evidence.reason_codes


def test_personio_invalid_or_empty_xml_never_becomes_authority() -> None:
    feed = "https://bridgingit.jobs.personio.de/xml?language=de"
    invalid = validate_personio_target_authority(
        candidate_url="https://bridgingit.jobs.personio.de/",
        requested_url=feed,
        final_url=feed,
        xml_content=b"<broken",
        company_key="bridgingit",
        company_name="BridgingIT GmbH",
    )
    empty = validate_personio_target_authority(
        candidate_url="https://bridgingit.jobs.personio.de/",
        requested_url=feed,
        final_url=feed,
        xml_content=b"<workzag-jobs></workzag-jobs>",
        company_key="bridgingit",
        company_name="BridgingIT GmbH",
    )

    assert invalid.xml_valid is False
    assert invalid.authority_validated is False
    assert empty.xml_valid is True
    assert empty.position_count == 0
    assert empty.authority_validated is False


def test_personio_target_authority_fingerprint_is_stable_for_same_evidence() -> None:
    xml = b"<workzag-jobs><position><company>BridgingIT GmbH</company></position></workzag-jobs>"
    feed = "https://bridgingit.jobs.personio.de/xml?language=de"
    kwargs = dict(
        candidate_url="https://bridgingit.jobs.personio.de/",
        requested_url=feed,
        final_url=feed,
        xml_content=xml,
        company_key="bridgingit",
        company_name="BridgingIT GmbH",
    )

    assert (
        validate_personio_target_authority(**kwargs).evidence_fingerprint
        == validate_personio_target_authority(**kwargs).evidence_fingerprint
    )
