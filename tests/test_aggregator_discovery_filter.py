from src.connectors.base import RawJobRecord
from src.ingestion.aggregator_discovery_filter import (
    filter_known_employer_origin_candidates,
    normalize_exclusion_keys,
)


def make_record(company_name: str, title: str = "Data Engineer") -> RawJobRecord:
    return RawJobRecord(
        source_name="stepstone",
        source_url=f"https://example.com/{company_name}",
        external_job_id=None,
        raw_data={
            "result_card": {
                "title": title,
                "company_name": company_name,
            }
        },
    )


def test_normalize_exclusion_keys_removes_legal_suffix_noise() -> None:
    keys = normalize_exclusion_keys({"HDI AG", "Finanz Informatik GmbH & Co. KG"})

    assert keys == {"hdi", "finanz_informatik"}


def test_filter_known_employer_origin_candidates_suppresses_matching_companies() -> None:
    result = filter_known_employer_origin_candidates(
        records=[
            make_record("HDI AG"),
            make_record("Adesso SE"),
            make_record("Finanz Informatik GmbH & Co. KG"),
            make_record("HDI Global"),
        ],
        excluded_company_keys={"hdi", "finanz_informatik"},
    )

    assert [record.raw_data["result_card"]["company_name"] for record in result.kept_records] == [
        "Adesso SE"
    ]
    assert [record.normalized_company_key for record in result.suppressed_records] == [
        "hdi",
        "finanz_informatik",
        "hdi_global",
    ]


def test_filter_known_employer_origin_candidates_keeps_unknown_companies() -> None:
    records = [make_record("Wertgarantie Group")]

    result = filter_known_employer_origin_candidates(
        records=records,
        excluded_company_keys={"hdi"},
    )

    assert result.kept_records == records
    assert result.suppressed_records == []
