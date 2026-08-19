from dataclasses import replace

import pytest

from src.job_lifecycle_health import JobHealthTarget, ensure_expected_target


URL = "https://careers.example.test/job/Data-Engineer/42/"


def target() -> JobHealthTarget:
    return JobHealthTarget(
        silver_job_id=42,
        raw_job_id=420,
        ingestion_run_id=7,
        source_name="successfactors:example",
        external_job_id="42",
        source_url=URL,
        title="Data Engineer",
        canonical_source_type="employer_origin_ats_backed_career_site",
        raw_source_type="employer_origin_ats_backed_career_site",
    )


def test_verified_ats_backed_employer_origin_target_is_health_probe_eligible() -> None:
    ensure_expected_target(
        target(),
        expected_source_name="successfactors:example",
        expected_source_url=URL,
    )


def test_non_employer_origin_target_remains_rejected() -> None:
    with pytest.raises(ValueError, match="not an employer_origin_career_site"):
        ensure_expected_target(
            replace(
                target(),
                canonical_source_type="aggregator",
                raw_source_type="aggregator_result_card",
            ),
            expected_source_name="successfactors:example",
            expected_source_url=URL,
        )
