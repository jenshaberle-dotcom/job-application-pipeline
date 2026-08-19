from scripts.run_product_v1_control_center import _merge_structured_job_locations


def test_control_center_attaches_structured_locations_without_rewriting_legacy_city() -> None:
    payload = {
        "job_readiness": [
            {
                "silver_job_id": 466,
                "city": "Essen",
                "title": "(Senior) Data Engineer Data & AI (f/m/d)",
            },
            {"silver_job_id": 900, "city": "Hannover", "title": "Other"},
        ],
        "top_jobs": [{"silver_job_id": 466, "city": "Essen"}],
    }
    rows = [
        {
            "silver_job_id": 466,
            "city": "Essen",
            "country_code": "DE",
            "is_primary": True,
            "evidence_source": "fixture",
        },
        {
            "silver_job_id": 466,
            "city": "Hannover",
            "country_code": "DE",
            "is_primary": False,
            "evidence_source": "fixture",
        },
        {
            "silver_job_id": 466,
            "city": "München",
            "country_code": "DE",
            "is_primary": False,
            "evidence_source": "fixture",
        },
    ]

    result = _merge_structured_job_locations(payload, rows)

    eon = result["job_readiness"][0]
    untouched = result["job_readiness"][1]
    ranked = result["top_jobs"][0]

    assert eon["city"] == "Essen"
    assert [location["city"] for location in eon["structured_locations"]] == [
        "Essen",
        "Hannover",
        "München",
    ]
    assert untouched["city"] == "Hannover"
    assert untouched["structured_locations"] == []
    assert ranked["city"] == "Essen"
    assert len(ranked["structured_locations"]) == 3


def test_control_center_location_projection_is_pure() -> None:
    payload = {"job_readiness": [{"silver_job_id": 1, "city": "Legacy"}], "top_jobs": []}
    original = {"job_readiness": [{"silver_job_id": 1, "city": "Legacy"}], "top_jobs": []}

    _merge_structured_job_locations(
        payload,
        [
            {
                "silver_job_id": 1,
                "city": "Structured",
                "country_code": "DE",
                "is_primary": True,
                "evidence_source": "fixture",
            }
        ],
    )

    assert payload == original
