from __future__ import annotations

from src.silver.origin_location_projection import (
    FINANZ_INFORMATIK_LOCATION_EVIDENCE_SOURCE,
    GENERIC_LOCATION_EVIDENCE_SOURCE,
    build_origin_location_projection,
)


def test_generic_origin_structured_locations_become_authoritative_silver_rows() -> None:
    raw_job = {
        "source_name": "generic_origin:example",
        "raw_data": {
            "observed_at_utc": "2026-09-10T09:00:00+00:00",
            "job": {
                "locations": [
                    {
                        "city": "Hannover",
                        "country_code": "DE",
                        "evidence_source": GENERIC_LOCATION_EVIDENCE_SOURCE,
                        "evidence_text": "Hannover | DE",
                    },
                    {
                        "city": "Münster",
                        "country_code": "DE",
                        "evidence_source": GENERIC_LOCATION_EVIDENCE_SOURCE,
                        "evidence_text": "Münster | DE",
                    },
                ]
            },
        },
    }

    projection = build_origin_location_projection(raw_job, legacy_city="Hannover | Münster")

    assert projection.authoritative is True
    assert projection.evidence_source == GENERIC_LOCATION_EVIDENCE_SOURCE
    assert [(row.city, row.is_primary) for row in projection.rows] == [
        ("Hannover", True),
        ("Münster", False),
    ]


def test_finanz_informatik_detail_locations_use_same_silver_contract() -> None:
    raw_job = {
        "source_name": "finanz_informatik:hannover",
        "raw_data": {
            "observed_at_utc": "2026-09-10T09:00:00+00:00",
            "job": {
                "locations": [
                    {
                        "city": "Hannover",
                        "country_code": "DE",
                        "evidence_source": FINANZ_INFORMATIK_LOCATION_EVIDENCE_SOURCE,
                        "evidence_text": "origin detail page explicitly names Hannover",
                    },
                    {
                        "city": "Münster",
                        "country_code": "DE",
                        "evidence_source": FINANZ_INFORMATIK_LOCATION_EVIDENCE_SOURCE,
                        "evidence_text": "origin detail page explicitly names Münster",
                    },
                    {
                        "city": "Frankfurt",
                        "country_code": "DE",
                        "evidence_source": FINANZ_INFORMATIK_LOCATION_EVIDENCE_SOURCE,
                        "evidence_text": "origin detail page explicitly names Frankfurt",
                    },
                ]
            },
        },
    }

    projection = build_origin_location_projection(
        raw_job,
        legacy_city="Hannover; Münster; Frankfurt",
    )

    assert projection.authoritative is True
    assert [row.city for row in projection.rows] == ["Hannover", "Münster", "Frankfurt"]
    assert projection.rows[0].is_primary is True


def test_unknown_country_is_not_invented_into_silver_location_truth() -> None:
    raw_job = {
        "source_name": "generic_origin:example",
        "raw_data": {
            "job": {
                "locations": [
                    {
                        "city": "Hannover",
                        "country_code": "",
                        "evidence_source": GENERIC_LOCATION_EVIDENCE_SOURCE,
                        "evidence_text": "Hannover",
                    }
                ]
            }
        },
    }

    projection = build_origin_location_projection(raw_job, legacy_city="Hannover")

    assert projection.authoritative is True
    assert projection.rows == ()


def test_legacy_string_locations_do_not_gain_false_structured_authority() -> None:
    raw_job = {
        "source_name": "generic_origin:example",
        "raw_data": {"job": {"locations": ["Hannover | DE", "Münster | DE"]}},
    }

    projection = build_origin_location_projection(raw_job, legacy_city="Hannover")

    assert projection.authoritative is True
    assert projection.rows == ()
