from typing import Any

from src.connectors.base import RawJobRecord


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

    if not normalized_search_term:
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
