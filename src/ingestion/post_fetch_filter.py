import re
from typing import Any

from src.connectors.base import RawJobRecord, SearchTerm


# Search-profile terms describe the kind of work, not the employer or commute
# surface. Keeping company/location out of this boundary prevents cross-field
# constructions such as company="Heartbeat AI" + title="Software Engineer" from
# becoming an artificial "AI Engineer" match.
SEARCHABLE_JOB_FIELDS = (
    "titel",
    "title",
    "beschreibung",
    "description",
    "content",
    "departments",
    "offices",
)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).lower().strip()


def normalize_profile_phrase(value: Any) -> str:
    text = normalize_text(value)
    text = re.sub(r"[-_/]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def flatten_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, dict):
        return " ".join(flatten_value(item) for item in value.values())

    if isinstance(value, list):
        return " ".join(flatten_value(item) for item in value)

    return normalize_text(value)


def build_search_segments(record: RawJobRecord) -> list[str]:
    raw_data = record.raw_data
    job_data = raw_data.get("job", {})
    result_card = raw_data.get("result_card", {})

    if not isinstance(job_data, dict):
        job_data = {}
    if not isinstance(result_card, dict):
        result_card = {}

    values: list[Any] = []
    for field in SEARCHABLE_JOB_FIELDS:
        values.append(job_data.get(field))
        values.append(raw_data.get(field))
        values.append(result_card.get(field))

    # Generated employer-origin connectors preserve exact profile signals proven
    # by the detail page here instead of persisting the full detail-page body.
    values.append(job_data.get("profile_terms"))

    return [
        segment
        for value in values
        if (segment := normalize_profile_phrase(flatten_value(value)))
    ]


def build_search_text(record: RawJobRecord) -> str:
    """Compatibility projection for diagnostics/tests; matching is field scoped."""

    return " ".join(build_search_segments(record))


def contains_whole_token(search_text: str, token: str) -> bool:
    """Match one normalized token without accepting substrings inside words."""

    return re.search(
        rf"(?<!\w){re.escape(token)}(?!\w)",
        search_text,
        flags=re.IGNORECASE,
    ) is not None


def job_matches_search_term(record: RawJobRecord, search_term: str) -> bool:
    normalized_search_term = normalize_profile_phrase(search_term)

    if not normalized_search_term or normalized_search_term == "*":
        return True

    segments = build_search_segments(record)
    if not segments:
        return False

    # Single-token discovery keeps the historical substring behaviour. Multi-word
    # role terms are intentionally stricter: every token must occur in the same
    # source-local semantic field. This prevents unrelated fields from being
    # concatenated into a synthetic role while still allowing punctuation and
    # modest word separation inside one title/description field.
    tokens = normalized_search_term.split()
    if len(tokens) == 1:
        return any(normalized_search_term in segment for segment in segments)

    for segment in segments:
        if normalized_search_term in segment:
            return True
        if all(contains_whole_token(segment, token) for token in tokens):
            return True

    return False


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
    matching["matching_mode"] = "field_scoped_case_insensitive_term_match"
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
