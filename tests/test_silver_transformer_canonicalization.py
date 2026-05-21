from src.silver.transformer import (
    add_canonicalization_fields,
    build_canonical_key_candidate,
    build_normalized_location,
    get_supported_source_patterns,
    normalize_text,
    transform_raw_job_to_silver,
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


def test_transform_personio_raw_job_uses_stable_bronze_job_fields() -> None:
    raw_job = {
        "id": 5959,
        "source_name": "personio:schluetersche-mediengruppe",
        "external_job_id": "2498694",
        "source_url": "https://schluetersche-mediengruppe.jobs.personio.de/xml?language=de",
        "raw_data": {
            "source_target": {
                "source_family": "personio",
                "target_key": "schluetersche-mediengruppe",
            },
            "job": {
                "id": "2498694",
                "title": "Data Engineer (m/w/d)",
                "company_name": "Schlütersche Verlagsgesellschaft mbH & Co. KG",
                "location": "Hannover",
                "source_url": (
                    "https://schluetersche-mediengruppe.jobs.personio.de"
                    "/job/2498694?language=de"
                ),
            },
            "source_specific": {
                "raw_position": {
                    "name": "Data Engineer (m/w/d)",
                },
            },
        },
    }

    result = transform_raw_job_to_silver(raw_job)

    assert result["raw_job_id"] == 5959
    assert result["source_name"] == "personio:schluetersche-mediengruppe"
    assert result["external_job_id"] == "2498694"
    assert result["source_url"] == (
        "https://schluetersche-mediengruppe.jobs.personio.de"
        "/job/2498694?language=de"
    )
    assert result["title"] == "Data Engineer (m/w/d)"
    assert result["company_name"] == "Schlütersche Verlagsgesellschaft mbH & Co. KG"
    assert result["city"] == "Hannover"
    assert result["postal_code"] is None
    assert result["country"] is None
    assert result["publication_date"] is None
    assert result["normalized_title"] == "data engineer (m/w/d)"
    assert (
        result["normalized_company_name"]
        == "schlütersche verlagsgesellschaft mbh & co. kg"
    )
    assert result["normalized_location"] == "hannover"
    assert result["canonical_status"] == "discovery_only"
    assert result["canonical_source_type"] == "unknown"
    assert result["canonical_key_candidate"] == (
        "schlütersche verlagsgesellschaft mbh & co. kg"
        " :: data engineer (m/w/d)"
        " :: hannover"
    )


def test_supported_source_patterns_include_personio() -> None:
    assert "personio:%" in get_supported_source_patterns()


def test_transform_stepstone_raw_job_uses_result_card_fields() -> None:
    raw_job = {
        "id": 6001,
        "source_name": "stepstone",
        "external_job_id": "123456",
        "source_url": "https://www.stepstone.de/jobs/data-engineer/in-hannover",
        "raw_data": {
            "result_card": {
                "title": "Senior Data Engineer (m/w/d)",
                "company_name": "Example GmbH",
                "location": "Hannover",
                "detail_url": (
                    "https://www.stepstone.de/stellenangebote--"
                    "Senior-Data-Engineer-Hannover-Example-GmbH--123456-inline.html"
                ),
                "external_job_id_candidate": "123456",
            },
            "source_specific": {
                "raw_card_text": "Evidence only. Silver must not parse this field.",
            },
            "extraction": {
                "extracted_from": "search_result_page",
                "detail_page_fetched": False,
                "pagination_used": False,
                "connector_mode": "limited_result_card",
            },
        },
    }

    result = transform_raw_job_to_silver(raw_job)

    assert result["raw_job_id"] == 6001
    assert result["source_name"] == "stepstone"
    assert result["external_job_id"] == "123456"
    assert result["source_url"] == (
        "https://www.stepstone.de/stellenangebote--"
        "Senior-Data-Engineer-Hannover-Example-GmbH--123456-inline.html"
    )
    assert result["title"] == "Senior Data Engineer (m/w/d)"
    assert result["company_name"] == "Example GmbH"
    assert result["city"] == "Hannover"
    assert result["postal_code"] is None
    assert result["country"] is None
    assert result["publication_date"] is None
    assert result["normalized_title"] == "senior data engineer (m/w/d)"
    assert result["normalized_company_name"] == "example gmbh"
    assert result["normalized_location"] == "hannover"
    assert result["canonical_status"] == "discovery_only"
    assert result["canonical_source_type"] == "unknown"
    assert result["canonical_key_candidate"] == (
        "example gmbh :: senior data engineer (m/w/d) :: hannover"
    )


def test_supported_source_patterns_include_stepstone() -> None:
    assert "stepstone" in get_supported_source_patterns()
