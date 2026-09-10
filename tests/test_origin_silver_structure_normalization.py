from datetime import date

from src.silver.transformer import transform_raw_job_to_silver


def test_generic_origin_uses_source_published_date_and_primary_structured_location() -> None:
    raw_job = {
        "id": 9001,
        "source_name": "generic_origin:example",
        "external_job_id": "REQ-42",
        "source_url": "https://jobs.example.test/req-42",
        "raw_data": {
            "source_type": "employer_origin_career_site",
            "job": {
                "title": "Data Platform Engineer",
                "company_name": "Example GmbH",
                "source_url": "https://jobs.example.test/req-42",
                "location": "Hannover | DE | Münster | DE",
                "locations": [
                    {
                        "city": "Hannover",
                        "country_code": "DE",
                        "evidence_source": "generic_origin_schema_job_location",
                        "evidence_text": "Hannover | DE",
                    },
                    {
                        "city": "Münster",
                        "country_code": "DE",
                        "evidence_source": "generic_origin_schema_job_location",
                        "evidence_text": "Münster | DE",
                    },
                ],
                "metadata": {
                    "date_posted": "2026-09-09",
                    "structured_identifier": "REQ-42",
                    "parser_family": "schema_org_json_ld",
                },
            },
            "result_card": {
                "title": "Data Platform Engineer",
                "company_name": "Example GmbH",
                "detail_url": "https://jobs.example.test/req-42",
            },
        },
    }

    result = transform_raw_job_to_silver(raw_job)

    assert result["city"] == "Hannover"
    assert result["country"] == "DE"
    assert result["publication_date"] == date(2026, 9, 9)
    assert result["normalized_location"] == "hannover | de"
    assert result["canonical_source_type"] == "employer_origin_career_site"


def test_finanz_informatik_uses_first_detail_location_as_legacy_city() -> None:
    raw_job = {
        "id": 9002,
        "source_name": "finanz_informatik:hannover",
        "external_job_id": "ai-engineer:123",
        "source_url": "https://www.f-i.de/de/karriere/offene-stellen/ai-engineer",
        "raw_data": {
            "job": {
                "title": "AI Engineer / KI-Entwickler (m/w/d)",
                "company_name": "Finanz Informatik GmbH & Co. KG",
                "source_url": "https://www.f-i.de/de/karriere/offene-stellen/ai-engineer",
                "location": "Hannover; Münster; Frankfurt",
                "locations": [
                    {
                        "city": "Hannover",
                        "country_code": "DE",
                        "evidence_source": "finanz_informatik_detail_text",
                        "evidence_text": "origin detail page explicitly names Hannover",
                    },
                    {
                        "city": "Münster",
                        "country_code": "DE",
                        "evidence_source": "finanz_informatik_detail_text",
                        "evidence_text": "origin detail page explicitly names Münster",
                    },
                ],
            },
            "result_card": {
                "title": "AI Engineer / KI-Entwickler (m/w/d)",
                "company_name": "Finanz Informatik GmbH & Co. KG",
                "detail_url": "https://www.f-i.de/de/karriere/offene-stellen/ai-engineer",
            },
        },
    }

    result = transform_raw_job_to_silver(raw_job)

    assert result["city"] == "Hannover"
    assert result["country"] == "DE"
    assert result["normalized_location"] == "hannover | de"
