from __future__ import annotations

from src.connectors.base import RawJobRecord
from src.ingestion.recurring_observation_evidence import (
    RECURRING_OBSERVATION_EVIDENCE_CONTRACT_VERSION,
    recurring_observation_evidence,
    recurring_observation_evidence_hash,
)


def _record(
    *,
    source_url: str = "https://jobs.example.test/42",
    raw_data: dict[str, object] | None = None,
) -> RawJobRecord:
    return RawJobRecord(
        source_name="personio:example",
        source_url=source_url,
        external_job_id="42",
        raw_data=raw_data
        or {
            "source_target": {"source_family": "personio", "target_key": "example"},
            "job": {
                "title": "Senior Data Engineer",
                "location": "Hannover",
                "description": "Build data platforms",
            },
            "source_specific": {"department": "Data"},
        },
    )


def test_contract_version_is_explicit_and_stable() -> None:
    assert RECURRING_OBSERVATION_EVIDENCE_CONTRACT_VERSION == (
        "recurring-observation-evidence.v1"
    )


def test_execution_and_search_metadata_do_not_change_hash() -> None:
    first = _record(
        raw_data={
            "job": {"title": "Senior Data Engineer", "location": "Hannover"},
            "source_specific": {"department": "Data"},
            "search_profile": {"search_term": "Data Engineer", "profile_name": "A"},
            "search_context": {"requested_url": "https://search.test/a"},
            "extraction": {"observed_at_utc": "2026-08-14T10:00:00Z"},
            "matching": {"matched_terms": ["Data Engineer"]},
            "quality_signals": {"has_title": True},
            "acquisition_evidence": {"heuristic_profile_terms": ["data"]},
        }
    )
    repeated = _record(
        raw_data={
            "job": {"location": "Hannover", "title": "Senior   Data Engineer"},
            "source_specific": {"department": "Data"},
            "search_profile": {"search_term": "ML Engineer", "profile_name": "B"},
            "search_context": {"requested_url": "https://search.test/b"},
            "extraction": {"observed_at_utc": "2026-08-15T10:00:00Z"},
            "matching": {"matched_terms": ["ML Engineer"]},
            "quality_signals": {"has_title": True, "other": "changed derivative"},
            "acquisition_evidence": {"heuristic_profile_terms": ["ml"]},
        }
    )

    assert recurring_observation_evidence_hash(first) == recurring_observation_evidence_hash(
        repeated
    )


def test_current_job_change_changes_hash() -> None:
    first = _record(
        raw_data={"job": {"title": "Data Engineer", "location": "Hannover"}}
    )
    changed = _record(
        raw_data={"job": {"title": "Senior Data Engineer", "location": "Hannover"}}
    )

    assert recurring_observation_evidence_hash(first) != recurring_observation_evidence_hash(
        changed
    )


def test_source_structural_change_changes_hash() -> None:
    first = _record(
        raw_data={
            "job": {"title": "Data Engineer"},
            "source_specific": {"board": "old"},
        }
    )
    changed = _record(
        raw_data={
            "job": {"title": "Data Engineer"},
            "source_specific": {"board": "new"},
        }
    )

    assert recurring_observation_evidence_hash(first) != recurring_observation_evidence_hash(
        changed
    )


def test_exact_source_url_change_changes_hash() -> None:
    first = _record(source_url="https://jobs.example.test/42")
    changed = _record(source_url="https://jobs.example.test/jobs/42")

    assert recurring_observation_evidence_hash(first) != recurring_observation_evidence_hash(
        changed
    )


def test_projection_contains_no_excluded_execution_context() -> None:
    record = _record(
        raw_data={
            "job": {"title": "Data Engineer"},
            "search_profile": {"search_term": "Data"},
            "extraction": {"observed_at_utc": "now"},
            "matching": {"matched_terms": ["Data"]},
        }
    )

    projection = recurring_observation_evidence(record)
    assert projection == {
        "source_url": "https://jobs.example.test/42",
        "raw_evidence": {"job": {"title": "Data Engineer"}},
    }
