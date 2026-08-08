import pytest

from src.silver.transformer import transform_raw_job_to_silver


EMPLOYER_ORIGIN_SOURCE_TYPE = "employer_origin_career_site"


def employer_origin_raw_job(
    *,
    raw_job_id: int,
    source_name: str,
    external_job_id: str,
    source_url: str,
    title: str,
    company_name: str,
    location: str,
    source_type: str = EMPLOYER_ORIGIN_SOURCE_TYPE,
) -> dict:
    return {
        "id": raw_job_id,
        "source_name": source_name,
        "external_job_id": external_job_id,
        "source_url": source_url,
        "raw_data": {
            "source_type": source_type,
            "result_card": {
                "title": title,
                "company_name": company_name,
                "location": location,
                "detail_url": source_url,
            },
            "job": {
                "title": title,
                "company_name": company_name,
                "location": location,
                "source_url": source_url,
                "profile_terms": ["data", "ai"],
            },
        },
    }


def test_computacenter_typed_employer_origin_uses_generic_silver_path() -> None:
    raw_job = employer_origin_raw_job(
        raw_job_id=30951,
        source_name="computacenter:discovery",
        external_job_id="1403194333:ac54d9b4b7fd",
        source_url=(
            "https://jobs.computacenter.com/job/M%C3%BCnchen-Lead-Consultant-"
            "%28mwd%29-Data-Center-AI-Infrastructures-80797/1403194333/"
        ),
        title="Lead Consultant (m/w/d) Data Center AI Infrastructures",
        company_name="Computacenter AG & Co. oHG",
        location="deutschland; bundesweit; hybrid",
    )

    result = transform_raw_job_to_silver(raw_job)

    assert result["raw_job_id"] == 30951
    assert result["source_name"] == "computacenter:discovery"
    assert result["title"] == "Lead Consultant (m/w/d) Data Center AI Infrastructures"
    assert result["company_name"] == "Computacenter AG & Co. oHG"
    assert result["city"] == "deutschland; bundesweit; hybrid"
    assert result["country"] == "DE"
    assert result["canonical_source_type"] == EMPLOYER_ORIGIN_SOURCE_TYPE
    assert result["canonical_key_candidate"] == (
        "computacenter ag & co. ohg :: "
        "lead consultant (m/w/d) data center ai infrastructures :: "
        "deutschland; bundesweit; hybrid | de"
    )


def test_accompio_typed_employer_origin_uses_same_generic_silver_path() -> None:
    raw_job = employer_origin_raw_job(
        raw_job_id=40001,
        source_name="accompio:discovery",
        external_job_id="de:51980f",
        source_url="https://karriere.accompio.com/de?id=51980f",
        title="Senior Data Engineer (m/w/d)",
        company_name="accompio GmbH",
        location="hannover; remote; deutschland",
    )

    result = transform_raw_job_to_silver(raw_job)

    assert result["source_name"] == "accompio:discovery"
    assert result["source_url"] == "https://karriere.accompio.com/de?id=51980f"
    assert result["title"] == "Senior Data Engineer (m/w/d)"
    assert result["company_name"] == "accompio GmbH"
    assert result["city"] == "hannover; remote; deutschland"
    assert result["country"] == "DE"
    assert result["canonical_source_type"] == EMPLOYER_ORIGIN_SOURCE_TYPE


def test_unknown_untyped_source_remains_fail_closed() -> None:
    raw_job = {
        "id": 50001,
        "source_name": "future_vendor:discovery",
        "external_job_id": "future-1",
        "source_url": "https://jobs.example.test/future-1",
        "raw_data": {
            "job": {
                "title": "Data Engineer",
                "company_name": "Future Vendor GmbH",
                "location": "Hannover",
            }
        },
    }

    with pytest.raises(
        ValueError,
        match="No Silver transformer implemented for source: future_vendor:discovery",
    ):
        transform_raw_job_to_silver(raw_job)


def test_unknown_source_with_unsupported_type_remains_fail_closed() -> None:
    raw_job = employer_origin_raw_job(
        raw_job_id=50002,
        source_name="future_vendor:discovery",
        external_job_id="future-2",
        source_url="https://jobs.example.test/future-2",
        title="Data Engineer",
        company_name="Future Vendor GmbH",
        location="Hannover",
        source_type="unsupported_future_source_type",
    )

    with pytest.raises(
        ValueError,
        match="No Silver transformer implemented for source: future_vendor:discovery",
    ):
        transform_raw_job_to_silver(raw_job)
