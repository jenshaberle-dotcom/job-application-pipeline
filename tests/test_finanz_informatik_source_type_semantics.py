from scripts.create_source_value_snapshot import source_family, source_target, source_type
from src.silver.transformer import add_canonicalization_fields, canonical_source_type


def test_finanz_informatik_source_value_snapshot_uses_explicit_source_type() -> None:
    source_name = "finanz_informatik:hannover"

    assert source_family(source_name) == "finanz_informatik"
    assert source_target(source_name) == "hannover"
    assert source_type(source_name) == "employer_origin_career_site"


def test_existing_source_type_classification_stays_unchanged() -> None:
    assert source_type("bundesagentur_fuer_arbeit") == "official_api"
    assert source_type("stepstone") == "commercial_aggregator"
    assert source_type("greenhouse:contentful") == "ats_company_board"
    assert source_type("personio:example") == "ats_company_board"


def test_finanz_informatik_silver_canonical_source_type_is_explicit() -> None:
    job = add_canonicalization_fields(
        {
            "source_name": "finanz_informatik:hannover",
            "title": "Product Owner OSPlus Versiegelung (m/w/d)",
            "company_name": "Finanz Informatik GmbH & Co. KG",
            "city": "Hannover",
            "postal_code": None,
            "country": "DE",
        }
    )

    assert job["canonical_source_type"] == "employer_origin_career_site"


def test_other_silver_canonical_source_type_defaults_to_unknown() -> None:
    assert canonical_source_type("stepstone") == "unknown"

    job = add_canonicalization_fields(
        {
            "source_name": "stepstone",
            "title": "Product Owner",
            "company_name": "Example GmbH",
            "city": "Hannover",
            "postal_code": None,
            "country": "DE",
        }
    )

    assert job["canonical_source_type"] == "unknown"
