from typing import Any

from src.connectors.base import RawJobRecord, SearchTerm


SEARCHABLE_JOB_FIELDS = (
    "titel",
    "title",
    "beschreibung",
    "description",
    "content",
    "arbeitgeber",
    "company",
    "company_name",
    "arbeitsort",
    "location",
    "departments",
    "offices",
)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).lower().strip()


def flatten_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, dict):
        return " ".join(flatten_value(item) for item in value.values())

    if isinstance(value, list):
        return " ".join(flatten_value(item) for item in value)

    return normalize_text(value)


def build_search_text(record: RawJobRecord) -> str:
    raw_data = record.raw_data
    job_data = raw_data.get("job", {})

    values: list[Any] = []

    for field in SEARCHABLE_JOB_FIELDS:
        values.append(job_data.get(field))
        values.append(raw_data.get(field))

    return " ".join(
        flattened
        for value in values
        if (flattened := flatten_value(value))
    )


def job_matches_search_term(record: RawJobRecord, search_term: str) -> bool:
    normalized_search_term = normalize_text(search_term)

    if not normalized_search_term or normalized_search_term == "*":
        return True

    search_text = build_search_text(record)

    if normalized_search_term in search_text:
        return True

    tokens = normalized_search_term.split()

    return all(token in search_text for token in tokens)

def apply_keyword_filter(
    records: list[RawJobRecord],
    search_term: str,
) -> list[RawJobRecord]:
    return [
        record
        for record in records
        if job_matches_search_term(record, search_term)
    ]


def get_matching_search_terms(
    record: RawJobRecord,
    search_terms: list[SearchTerm],
) -> list[SearchTerm]:
    return [
        search_term
        for search_term in search_terms
        if job_matches_search_term(record, search_term.search_term)
    ]


def with_matched_search_terms(
    record: RawJobRecord,
    matched_terms: list[SearchTerm],
) -> RawJobRecord:
    raw_data = dict(record.raw_data)

    matching = raw_data.get("matching", {})
    if not isinstance(matching, dict):
        matching = {}

    matching = dict(matching)
    matching["matching_mode"] = "simple_case_insensitive_term_match"
    matching["matched_terms"] = [
        search_term.search_term
        for search_term in matched_terms
    ]
    matching["matched_search_term_ids"] = [
        search_term.id
        for search_term in matched_terms
        if search_term.id is not None
    ]

    raw_data["matching"] = matching

    return RawJobRecord(
        source_name=record.source_name,
        source_url=record.source_url,
        external_job_id=record.external_job_id,
        raw_data=raw_data,
    )


def apply_multi_term_keyword_filter(
    records: list[RawJobRecord],
    search_terms: list[SearchTerm],
) -> list[RawJobRecord]:
    matched_records: list[RawJobRecord] = []

    for record in records:
        matched_terms = get_matching_search_terms(
            record=record,
            search_terms=search_terms,
        )

        if not matched_terms:
            continue

        matched_records.append(
            with_matched_search_terms(
                record=record,
                matched_terms=matched_terms,
            )
        )

    return matched_records
