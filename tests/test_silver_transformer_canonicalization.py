from src.silver.transformer import (
    add_canonicalization_fields,
    build_canonical_key_candidate,
    build_normalized_location,
    normalize_text,
)


def test_normalize_text_strips_lowercases_and_collapses_whitespace() -> None:
    assert normalize_text("  Senior   Data Engineer  ") == "senior data engineer"


def test_normalize_text_returns_none_for_empty_or_non_string_values() -> None:
    assert normalize_text("") is None
    assert normalize_text("   ") is None
    assert normalize_text(None) is None
    assert normalize_text(123) is None


def test_build_normalized_location_joins_available_location_parts() -> None:
    assert (
        build_normalized_location(" Hannover ", " 30159 ", " DE ")
        == "hannover | 30159 | de"
    )


def test_build_normalized_location_ignores_missing_parts() -> None:
    assert build_normalized_location("Hannover", None, "") == "hannover"


def test_build_canonical_key_candidate_joins_available_parts() -> None:
    assert (
        build_canonical_key_candidate(
            "volkswagen ag",
            "data engineer",
            "hannover | de",
        )
        == "volkswagen ag :: data engineer :: hannover | de"
    )


def test_build_canonical_key_candidate_returns_none_without_parts() -> None:
    assert build_canonical_key_candidate(None, None, None) is None


def test_add_canonicalization_fields_sets_first_layer_defaults() -> None:
    job = {
        "title": "  Data Engineer  ",
        "company_name": " Volkswagen AG ",
        "city": " Hannover ",
        "postal_code": None,
        "country": " DE ",
    }

    result = add_canonicalization_fields(job)

    assert result["normalized_title"] == "data engineer"
    assert result["normalized_company_name"] == "volkswagen ag"
    assert result["normalized_location"] == "hannover | de"
    assert result["canonical_status"] == "discovery_only"
    assert result["canonical_source_type"] == "unknown"
    assert (
        result["canonical_key_candidate"]
        == "volkswagen ag :: data engineer :: hannover | de"
    )
