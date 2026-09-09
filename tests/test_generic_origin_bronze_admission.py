from __future__ import annotations

from src.connectors.base import RawJobRecord
from src.ingestion.generic_origin_bronze_admission import (
    BRONZE_ADMISSION_GATE,
    admit_generic_origin_bronze_record,
    evaluate_generic_origin_bronze_record,
)


def _record(**overrides: object) -> RawJobRecord:
    source_url = str(overrides.pop("source_url", "https://example.test/jobs/data-engineer-123"))
    raw_data = {
        "source_type": "employer_origin_career_site",
        "source_family": "generic_origin",
        "source_target": "example",
        "result_card": {
            "title": "Data Engineer",
            "company_name": "Example GmbH",
            "detail_url": source_url,
        },
        "job": {
            "title": "Data Engineer",
            "company_name": "Example GmbH",
            "source_url": source_url,
        },
        "acquisition_evidence": {
            "proof_kind": "jsonld_jobposting",
            "discovery_source": "anchor_detail",
            "candidate_id": 17,
            "generic_layer_product": True,
        },
    }
    raw_updates = overrides.pop("raw_updates", None)
    if isinstance(raw_updates, dict):
        raw_data.update(raw_updates)
    return RawJobRecord(
        source_name=str(overrides.pop("source_name", "generic_origin:example")),
        source_url=source_url,
        external_job_id=overrides.pop("external_job_id", "data-engineer-123"),
        raw_data=raw_data,
    )


def test_valid_generic_job_is_admitted_and_stamped() -> None:
    admitted = admit_generic_origin_bronze_record(_record())

    assert admitted is not None
    assert admitted.raw_data["bronze_admission"] == {
        "status": "pass",
        "gate": BRONZE_ADMISSION_GATE,
        "source_validity_is_separate": True,
    }


def test_generic_title_is_not_persisted_to_bronze() -> None:
    record = _record()
    record.raw_data["result_card"]["title"] = "Job"
    record.raw_data["job"]["title"] = "Job"

    decision = evaluate_generic_origin_bronze_record(record)

    assert decision.passed is False
    assert "missing_or_generic_job_title" in decision.failures
    assert admit_generic_origin_bronze_record(record) is None


def test_non_https_job_url_is_not_persisted_to_bronze() -> None:
    decision = evaluate_generic_origin_bronze_record(
        _record(source_url="http://example.test/jobs/data-engineer-123")
    )

    assert decision.passed is False
    assert "non_https_or_missing_job_url" in decision.failures


def test_missing_genuine_job_proof_is_not_persisted_to_bronze() -> None:
    record = _record()
    record.raw_data["acquisition_evidence"]["proof_kind"] = ""

    decision = evaluate_generic_origin_bronze_record(record)

    assert decision.passed is False
    assert "missing_genuine_job_proof" in decision.failures


def test_detail_identity_mismatch_is_not_persisted_to_bronze() -> None:
    record = _record()
    record.raw_data["result_card"]["detail_url"] = "https://example.test/jobs/other"
    record.raw_data["job"]["source_url"] = "https://example.test/jobs/other"

    decision = evaluate_generic_origin_bronze_record(record)

    assert decision.passed is False
    assert "detail_url_identity_mismatch" in decision.failures
