from __future__ import annotations

from src.search_intelligence.product_v1_application_origin_authority import (
    application_employer_origin_authority,
)


URL = "https://eraneos.jobs.personio.de/job/2767212?language=de"


def _reviewed_personio_row() -> dict[str, object]:
    return {
        "source_name": "personio:eraneos",
        "source_url": URL,
        "lifecycle_status": "active_confirmed",
        "lifecycle_evidence_reason": "authoritative_verified_ats_feed_observation",
        "latest_health_coverage": "complete_inventory",
        "latest_observation_source_url": URL,
        "latest_observation_evidence": {
            "source_url": URL,
            "raw_evidence": {
                "source_type": "employer_origin_ats_backed_career_site",
                "source_target": {"target_key": "eraneos"},
                "job": {"source_url": URL},
                "ats_feed_authority": {
                    "contract_version": "personio-recurring-feed-authority.v1",
                    "reviewed_binding_contract": "runtime_203_personio_target_authority_shadow_v1",
                    "provider": "personio",
                    "target_key": "eraneos",
                    "authority_validated": True,
                    "employer_identity_bound": True,
                    "feed_inventory_complete": True,
                    "product_authority": False,
                    "evidence_fingerprint": "a" * 64,
                    "matched_company_name": "Eraneos Analytics Germany GmbH",
                },
            },
        },
    }


def test_generic_origin_authority_remains_primary_path() -> None:
    result = application_employer_origin_authority(
        {"source_name": "generic_origin:example"},
        generic_source_authorized=True,
    )

    assert result.authorized is True
    assert result.reason == "active_recurring_generic_employer_origin"


def test_reviewed_eraneos_personio_feed_is_admitted_without_broadening_personio() -> None:
    result = application_employer_origin_authority(
        _reviewed_personio_row(),
        generic_source_authorized=False,
    )

    assert result.authorized is True
    assert result.reason == "reviewed_verified_personio_recurring_feed"


def test_unreviewed_personio_target_stays_blocked() -> None:
    row = _reviewed_personio_row()
    row["source_name"] = "personio:not-reviewed"

    result = application_employer_origin_authority(
        row,
        generic_source_authorized=False,
    )

    assert result.authorized is False
    assert result.reason == "personio_target_not_reviewed"


def test_reviewed_personio_must_carry_exact_verified_feed_contract() -> None:
    row = _reviewed_personio_row()
    evidence = row["latest_observation_evidence"]
    assert isinstance(evidence, dict)
    raw = evidence["raw_evidence"]
    assert isinstance(raw, dict)
    authority = raw["ats_feed_authority"]
    assert isinstance(authority, dict)
    authority["authority_validated"] = False

    result = application_employer_origin_authority(
        row,
        generic_source_authorized=False,
    )

    assert result.authorized is False
    assert result.reason == "personio_reviewed_feed_contract_mismatch"


def test_exact_detail_revalidation_does_not_revoke_reviewed_personio_origin() -> None:
    row = _reviewed_personio_row()
    row["lifecycle_evidence_reason"] = "exact_detail_url_and_title_confirmed"
    row["latest_health_coverage"] = "exact_detail"

    result = application_employer_origin_authority(
        row,
        generic_source_authorized=False,
    )

    assert result.authorized is True
    assert result.reason == "reviewed_verified_personio_recurring_feed"


def test_reviewed_personio_still_requires_active_lifecycle() -> None:
    row = _reviewed_personio_row()
    row["lifecycle_status"] = "inactive_confirmed"

    result = application_employer_origin_authority(
        row,
        generic_source_authorized=False,
    )

    assert result.authorized is False
    assert result.reason == "personio_lifecycle_not_active"



def test_validated_active_direct_product_origin_is_generic_f6_authority() -> None:
    result = application_employer_origin_authority(
        {
            "source_name": "finanz_informatik:careers",
            "source_url": "https://jobs.f-i.de/job/12345",
            "canonical_source_type": "unknown",
            "origin_validation_status": "validated",
            "activity_status": "active",
            "lifecycle_status": "active_confirmed",
        },
        generic_source_authorized=False,
    )

    assert result.authorized is True
    assert result.reason == "validated_active_product_employer_origin"


def test_validated_direct_origin_does_not_require_source_specific_allowlist() -> None:
    result = application_employer_origin_authority(
        {
            "source_name": "hannoverre",
            "source_url": "https://jobs.hannover-re.com/job/software-engineer",
            "canonical_source_type": "unknown",
            "origin_validation_status": "validated",
            "activity_status": "active",
            "lifecycle_status": "active_confirmed",
        },
        generic_source_authorized=False,
    )

    assert result.authorized is True
    assert result.reason == "validated_active_product_employer_origin"


def test_validated_aggregator_source_still_fails_closed() -> None:
    result = application_employer_origin_authority(
        {
            "source_name": "stepstone",
            "source_url": "https://www.stepstone.de/stellenangebote--example",
            "canonical_source_type": "aggregator",
            "origin_validation_status": "validated",
            "activity_status": "active",
            "lifecycle_status": "active_confirmed",
        },
        generic_source_authorized=False,
    )

    assert result.authorized is False
    assert result.reason == "validated_origin_requires_direct_https_source"


def test_validated_product_origin_rejects_mismatched_current_observation() -> None:
    result = application_employer_origin_authority(
        {
            "source_name": "company:careers",
            "source_url": "https://jobs.example.test/job/42",
            "canonical_source_type": "employer_origin_career_site",
            "origin_validation_status": "validated",
            "activity_status": "active",
            "lifecycle_status": "active_confirmed",
            "latest_observation_source_url": "https://jobs.example.test/job/99",
        },
        generic_source_authorized=False,
    )

    assert result.authorized is False
    assert result.reason == "current_observation_url_mismatch"


def test_validated_product_origin_requires_current_active_lifecycle() -> None:
    result = application_employer_origin_authority(
        {
            "source_name": "company:careers",
            "source_url": "https://jobs.example.test/job/42",
            "canonical_source_type": "employer_origin_career_site",
            "origin_validation_status": "validated",
            "activity_status": "inactive",
            "lifecycle_status": "inactive_confirmed",
        },
        generic_source_authorized=False,
    )

    assert result.authorized is False
    assert result.reason == "product_origin_lifecycle_not_active"
