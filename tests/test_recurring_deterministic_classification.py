from __future__ import annotations

from copy import deepcopy

import pytest

from src.ingestion.recurring_observation_evidence import (
    RECURRING_OBSERVATION_EVIDENCE_CONTRACT_VERSION,
)
from src.search_intelligence.recurring_connector_economics import (
    RecurringDeterministicOutcome,
    RecurringGapKind,
    normalized_evidence_hash,
)
from src.search_intelligence.recurring_deterministic_classification import (
    classify_recurring_observation_evidence,
)


def _classify(*, source_name: str, evidence: dict, persisted_hash: str | None = None):
    return classify_recurring_observation_evidence(
        source_name=source_name,
        external_job_id="job-42",
        normalized_evidence=evidence,
        persisted_evidence_hash=persisted_hash or normalized_evidence_hash(evidence),
        evidence_contract_version=RECURRING_OBSERVATION_EVIDENCE_CONTRACT_VERSION,
    )


def _assert_supported(result) -> None:
    assert result.deterministic_outcome is RecurringDeterministicOutcome.SUPPORTED
    assert result.gap_kind is RecurringGapKind.NONE
    assert result.reason_code == "deterministic_silver_structure_supported"
    assert result.source_url_present is True
    assert result.title_present is True
    assert result.company_name_present is True
    assert result.evidence_hash_bound is True
    assert result.evidence_contract_bound is True
    assert result.provider_requests == 0
    assert result.llm_requests == 0
    assert result.database_requests == 0
    assert result.product_writes == 0
    assert result.product_authority is False


def test_personio_observation_evidence_is_supported_by_existing_silver_parser() -> None:
    evidence = {
        "source_url": "https://example.jobs.personio.de/job/42",
        "raw_evidence": {
            "job": {
                "title": "Data Engineer",
                "company_name": "Example GmbH",
                "location": "Hannover",
                "source_url": "https://example.jobs.personio.de/job/42",
            }
        },
    }

    _assert_supported(_classify(source_name="personio:example", evidence=evidence))


def test_greenhouse_observation_evidence_is_supported_by_existing_silver_parser() -> None:
    evidence = {
        "source_url": "https://boards.greenhouse.io/example/jobs/42",
        "raw_evidence": {
            "job": {
                "title": "Analytics Engineer",
                "company_name": "Example Inc.",
                "absolute_url": "https://boards.greenhouse.io/example/jobs/42",
                "location": {"name": "Berlin"},
            }
        },
    }

    _assert_supported(_classify(source_name="greenhouse:example", evidence=evidence))


def test_typed_employer_origin_evidence_is_supported_by_generic_silver_parser() -> None:
    evidence = {
        "source_url": "https://jobs.example.test/42",
        "raw_evidence": {
            "source_type": "employer_origin_career_site",
            "job": {
                "title": "Data Engineer",
                "company_name": "Example GmbH",
                "location": "Hannover",
                "source_url": "https://jobs.example.test/42",
            },
        },
    }

    _assert_supported(_classify(source_name="example:discovery", evidence=evidence))


def test_unknown_untyped_source_is_unresolved_structural_drift() -> None:
    evidence = {
        "source_url": "https://future.example.test/42",
        "raw_evidence": {
            "job": {"title": "Data Engineer", "company_name": "Future GmbH"},
        },
    }

    result = _classify(source_name="future_vendor:discovery", evidence=evidence)

    assert result.deterministic_outcome is RecurringDeterministicOutcome.UNRESOLVED
    assert result.gap_kind is RecurringGapKind.STRUCTURAL_DRIFT
    assert result.reason_code == "deterministic_silver_transform_unsupported"
    assert result.evidence_hash_bound is True
    assert result.evidence_contract_bound is True


@pytest.mark.parametrize(
    ("evidence", "reason"),
    [
        (None, "observation_evidence_missing_or_malformed"),
        ({"source_url": "https://jobs.example.test/42"}, "observation_evidence_projection_shape_invalid"),
        ({"source_url": "", "raw_evidence": {}}, "observation_evidence_projection_shape_invalid"),
    ],
)
def test_missing_or_malformed_observation_evidence_fails_closed(evidence, reason) -> None:
    result = classify_recurring_observation_evidence(
        source_name="personio:example",
        external_job_id="job-42",
        normalized_evidence=evidence,
        persisted_evidence_hash=(
            normalized_evidence_hash(evidence) if isinstance(evidence, dict) else None
        ),
        evidence_contract_version=RECURRING_OBSERVATION_EVIDENCE_CONTRACT_VERSION,
    )

    assert result.deterministic_outcome is RecurringDeterministicOutcome.UNRESOLVED
    assert result.gap_kind is RecurringGapKind.STRUCTURAL_DRIFT
    assert result.reason_code == reason


def test_missing_core_silver_field_is_unresolved_structural_drift() -> None:
    evidence = {
        "source_url": "https://example.jobs.personio.de/job/42",
        "raw_evidence": {
            "job": {
                "title": "Data Engineer",
                "company_name": "",
                "location": "Hannover",
            }
        },
    }

    result = _classify(source_name="personio:example", evidence=evidence)

    assert result.deterministic_outcome is RecurringDeterministicOutcome.UNRESOLVED
    assert result.gap_kind is RecurringGapKind.STRUCTURAL_DRIFT
    assert result.reason_code == "deterministic_silver_core_fields_incomplete"
    assert result.title_present is True
    assert result.company_name_present is False


def test_wrong_contract_never_becomes_supported() -> None:
    evidence = {
        "source_url": "https://example.jobs.personio.de/job/42",
        "raw_evidence": {
            "job": {"title": "Data Engineer", "company_name": "Example GmbH"},
        },
    }

    result = classify_recurring_observation_evidence(
        source_name="personio:example",
        external_job_id="job-42",
        normalized_evidence=evidence,
        persisted_evidence_hash=normalized_evidence_hash(evidence),
        evidence_contract_version="future-contract.v2",
    )

    assert result.deterministic_outcome is RecurringDeterministicOutcome.UNRESOLVED
    assert result.gap_kind is RecurringGapKind.STRUCTURAL_DRIFT
    assert result.reason_code == "observation_evidence_contract_mismatch"
    assert result.evidence_contract_bound is False


def test_hash_mismatch_never_becomes_supported() -> None:
    evidence = {
        "source_url": "https://example.jobs.personio.de/job/42",
        "raw_evidence": {
            "job": {"title": "Data Engineer", "company_name": "Example GmbH"},
        },
    }

    result = _classify(
        source_name="personio:example",
        evidence=evidence,
        persisted_hash="0" * 64,
    )

    assert result.deterministic_outcome is RecurringDeterministicOutcome.UNRESOLVED
    assert result.gap_kind is RecurringGapKind.STRUCTURAL_DRIFT
    assert result.reason_code == "observation_evidence_hash_mismatch"
    assert result.evidence_hash_bound is False


def test_result_json_exposes_no_external_or_product_authority() -> None:
    evidence = {
        "source_url": "https://example.jobs.personio.de/job/42",
        "raw_evidence": {
            "job": {"title": "Data Engineer", "company_name": "Example GmbH"},
        },
    }

    payload = _classify(source_name="personio:example", evidence=deepcopy(evidence)).to_json()

    assert payload["provider_requests"] == 0
    assert payload["llm_requests"] == 0
    assert payload["database_requests"] == 0
    assert payload["product_writes"] == 0
    assert payload["product_authority"] is False
