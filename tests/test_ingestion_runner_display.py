from src.connectors.base import RawJobRecord
from src.ingestion.runner import (
    get_record_display_company,
    get_record_display_title,
)


def make_record(raw_data):
    return RawJobRecord(
        source_name="test",
        source_url="https://example.com/job",
        external_job_id=None,
        raw_data=raw_data,
    )


def test_display_values_from_stepstone_result_card() -> None:
    record = make_record(
        {
            "result_card": {
                "title": "Data Engineer (m/w/d)",
                "company_name": "Example Data GmbH",
            }
        }
    )

    assert get_record_display_title(record) == "Data Engineer (m/w/d)"
    assert get_record_display_company(record) == "Example Data GmbH"


def test_display_values_from_bundesagentur_job_payload() -> None:
    record = make_record(
        {
            "job": {
                "titel": "Data Engineer",
                "arbeitgeber": "Example Arbeitgeber GmbH",
            }
        }
    )

    assert get_record_display_title(record) == "Data Engineer"
    assert get_record_display_company(record) == "Example Arbeitgeber GmbH"


def test_display_values_from_greenhouse_like_job_payload() -> None:
    record = make_record(
        {
            "job": {
                "title": "Analytics Engineer",
            }
        }
    )

    assert get_record_display_title(record) == "Analytics Engineer"
    assert get_record_display_company(record) == "<missing>"


def test_display_values_fall_back_to_missing_marker() -> None:
    record = make_record({})

    assert get_record_display_title(record) == "<missing>"
    assert get_record_display_company(record) == "<missing>"
