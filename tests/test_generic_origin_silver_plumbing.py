from src.silver.transformer import (
    EMPLOYER_ORIGIN_CAREER_SITE_SOURCE_TYPE,
    get_supported_source_patterns,
    transform_raw_job_to_silver,
)


def test_generic_origin_family_is_selected_by_default_silver() -> None:
    assert "generic_origin:%" in get_supported_source_patterns()


def test_generic_origin_bronze_record_uses_generic_employer_origin_transformer() -> None:
    raw_job = {
        "id": 17,
        "source_name": "generic_origin:example",
        "external_job_id": "vacancy-17",
        "source_url": "https://jobs.example.test/job/vacancy-17",
        "raw_data": {
            "source_type": EMPLOYER_ORIGIN_CAREER_SITE_SOURCE_TYPE,
            "job": {
                "title": "Data Engineer",
                "company_name": "Example GmbH",
                "source_url": "https://jobs.example.test/job/vacancy-17",
                "location": "Hannover",
                "country": "DE",
            },
        },
    }

    silver = transform_raw_job_to_silver(raw_job)

    assert silver["source_name"] == "generic_origin:example"
    assert silver["title"] == "Data Engineer"
    assert silver["city"] == "Hannover"
    assert silver["country"] == "DE"
    assert silver["canonical_source_type"] == EMPLOYER_ORIGIN_CAREER_SITE_SOURCE_TYPE
