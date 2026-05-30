from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.connectors.base import RawJobRecord
from src.normalization.company_keys import (
    find_matching_company_key,
    normalize_company_key,
)


COMPANY_PATHS = (
    ("result_card", "company_name"),
    ("job", "company_name"),
    ("job", "company"),
    ("job", "arbeitgeber"),
)


@dataclass(frozen=True)
class SuppressedAggregatorRecord:
    company_name: str
    normalized_company_key: str
    title: str | None
    source_url: str


@dataclass(frozen=True)
class AggregatorDiscoveryFilterResult:
    kept_records: list[RawJobRecord]
    suppressed_records: list[SuppressedAggregatorRecord]

    @property
    def suppressed_count(self) -> int:
        return len(self.suppressed_records)


def normalize_exclusion_keys(values: Iterable[str]) -> set[str]:
    return {key for key in (normalize_company_key(value) for value in values) if key}


def get_nested_value(data: dict, path: tuple[str, ...]) -> str | None:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)

    if current is None:
        return None

    value = str(current).strip()
    return value or None


def record_company_name(record: RawJobRecord) -> str | None:
    for path in COMPANY_PATHS:
        value = get_nested_value(record.raw_data, path)
        if value:
            return value
    return None


def record_title(record: RawJobRecord) -> str | None:
    return (
        get_nested_value(record.raw_data, ("result_card", "title"))
        or get_nested_value(record.raw_data, ("job", "titel"))
        or get_nested_value(record.raw_data, ("job", "title"))
    )


def filter_known_employer_origin_candidates(
    *,
    records: list[RawJobRecord],
    excluded_company_keys: set[str],
) -> AggregatorDiscoveryFilterResult:
    if not records or not excluded_company_keys:
        return AggregatorDiscoveryFilterResult(
            kept_records=list(records),
            suppressed_records=[],
        )

    kept_records: list[RawJobRecord] = []
    suppressed_records: list[SuppressedAggregatorRecord] = []

    for record in records:
        company_name = record_company_name(record)
        normalized_company_key = normalize_company_key(company_name)

        if normalized_company_key and find_matching_company_key(
            normalized_company_key,
            excluded_company_keys,
        ):
            suppressed_records.append(
                SuppressedAggregatorRecord(
                    company_name=company_name or "<missing>",
                    normalized_company_key=normalized_company_key,
                    title=record_title(record),
                    source_url=record.source_url,
                )
            )
            continue

        kept_records.append(record)

    return AggregatorDiscoveryFilterResult(
        kept_records=kept_records,
        suppressed_records=suppressed_records,
    )
