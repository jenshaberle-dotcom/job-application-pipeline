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


def test_reviewed_personio_requires_the_authoritative_lifecycle_projection() -> None:
    row = _reviewed_personio_row()
    row["lifecycle_evidence_reason"] = "historical_success_only"

    result = application_employer_origin_authority(
        row,
        generic_source_authorized=False,
    )

    assert result.authorized is False
    assert result.reason == "personio_verified_feed_lifecycle_required"
