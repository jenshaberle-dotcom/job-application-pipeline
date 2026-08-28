from __future__ import annotations

from scripts.run_deterministic_origin_plan_audit import audit_row


def _row(company_key: str, company_name: str) -> dict[str, object]:
    return {
        "id": 1,
        "company_key": company_key,
        "company_name": company_name,
        "candidate_url": None,
        "source_family_candidate": None,
        "status": "discovery",
        "risk_level": "unknown",
    }


def test_budget_audit_detects_host_family_monoculture_and_delayed_compact_brand() -> None:
    result = audit_row(
        _row("sport_alliance", "Sport Alliance"),
        budget=12,
        expanded_budget=500,
    )

    assert result["budget_saturated"] is True
    assert result["domain_family_monoculture"] is True
    assert result["bounded_unique_host_family_count"] == 1
    assert result["compact_key_first_position"] is not None
    assert result["compact_key_first_position"] > 12
    assert result["compact_key_delayed_beyond_budget"] is True


def test_short_brand_is_reported_when_acronym_is_absorbed_into_identity_tokens() -> None:
    result = audit_row(
        _row("mtu_maintenance", "MTU Maintenance"),
        budget=12,
        expanded_budget=500,
    )

    assert "mtu" in result["identity_tokens"]
    assert "mtu" in result["acronym_tokens"]
    assert result["acronym_first_position"] is None
    assert result["acronym_absorbed_into_identity"] is True
    assert result["short_brand_missing_from_expanded_plan"] is True
    assert any(
        "no standalone host hypothesis" in reason
        for reason in result["reasons"]
    )


def test_existing_short_brand_base_can_be_delayed_by_plan_geometry() -> None:
    result = audit_row(
        _row("kkh", "KKH Kaufmännische Krankenkasse"),
        budget=12,
        expanded_budget=500,
    )

    assert "kkh" in result["identity_tokens"]
    assert "kkh" in result["acronym_tokens"]
    assert result["acronym_first_position"] is not None
    assert result["acronym_first_position"] > 12
    assert result["acronym_delayed_beyond_budget"] is True
    assert result["short_brand_missing_from_expanded_plan"] is False
