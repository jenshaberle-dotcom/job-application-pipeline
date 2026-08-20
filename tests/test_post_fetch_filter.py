from src.connectors.base import RawJobRecord, SearchTerm
from src.ingestion.post_fetch_filter import (
    apply_multi_term_keyword_filter,
    get_matching_search_terms,
    job_matches_search_term,
    with_matched_search_terms,
)


def make_record(
    title: str = "Data Engineer",
    description: str = "Python SQL ETL Data Platform",
) -> RawJobRecord:
    return RawJobRecord(
        source_name="personio:example",
        source_url="https://example.jobs.personio.de/job/1",
        external_job_id="1",
        raw_data={
            "job": {
                "title": title,
                "description": description,
                "company_name": "Example GmbH",
                "location": "remote",
            }
        },
    )


def test_get_matching_search_terms_returns_all_matching_terms() -> None:
    record = make_record()

    search_terms = [
        SearchTerm(id=1, search_term="Data Engineer"),
        SearchTerm(id=2, search_term="Analytics Engineer"),
        SearchTerm(id=3, search_term="Data Platform"),
    ]

    matched_terms = get_matching_search_terms(
        record=record,
        search_terms=search_terms,
    )

    assert [term.search_term for term in matched_terms] == [
        "Data Engineer",
        "Data Platform",
    ]


def test_with_matched_search_terms_adds_matching_metadata_without_mutating_original() -> None:
    record = make_record()
    matched_record = with_matched_search_terms(
        record=record,
        matched_terms=[
            SearchTerm(id=1, search_term="Data Engineer"),
            SearchTerm(id=3, search_term="Data Platform"),
        ],
    )

    assert "matching" not in record.raw_data

    assert matched_record.raw_data["matching"] == {
        "matching_mode": "simple_case_insensitive_term_match",
        "matched_terms": ["Data Engineer", "Data Platform"],
        "matched_search_term_ids": [1, 3],
    }


def test_apply_multi_term_keyword_filter_keeps_only_matching_records() -> None:
    matching_record = make_record(
        title="Analytics Engineer",
        description="Data Warehouse and ETL",
    )
    non_matching_record = make_record(
        title="Office Manager",
        description="People operations",
    )

    records = apply_multi_term_keyword_filter(
        records=[matching_record, non_matching_record],
        search_terms=[
            SearchTerm(id=1, search_term="Data Engineer"),
            SearchTerm(id=2, search_term="Analytics Engineer"),
            SearchTerm(id=3, search_term="ETL"),
        ],
    )

    assert len(records) == 1
    assert records[0].external_job_id == "1"
    assert records[0].raw_data["matching"]["matched_terms"] == [
        "Data Engineer",
        "Analytics Engineer",
        "ETL",
    ]


def test_ml_engineer_does_not_match_ml_substring_inside_html() -> None:
    record = make_record(
        title="Software Engineer",
        description="Builds HTML templates and web applications",
    )

    assert job_matches_search_term(record, "ML Engineer") is False


def test_ai_engineer_does_not_match_ai_substring_inside_unrelated_word() -> None:
    record = make_record(
        title="Software Engineer",
        description="Maintains reliable backend services",
    )

    assert job_matches_search_term(record, "AI Engineer") is False


def test_non_contiguous_whole_tokens_remain_supported() -> None:
    record = make_record(
        title="Software Engineer",
        description="Works on ML platforms and model delivery",
    )

    assert job_matches_search_term(record, "ML Engineer") is True


def test_exact_phrase_match_remains_case_insensitive() -> None:
    record = make_record(
        title="Senior MACHINE LEARNING ENGINEER",
        description="Model platform role",
    )

    assert job_matches_search_term(record, "Machine Learning Engineer") is True
