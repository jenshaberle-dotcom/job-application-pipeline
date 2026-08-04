from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.run_eon_controlled_pilot_ingestion import validate_profile_row
from src.connectors.base import RawJobRecord
from src.ingestion.eon_controlled_pilot import (
    APPROVAL_TOKEN,
    EXPECTED_COMPANY_NAME,
    EXPECTED_EXTERNAL_JOB_ID,
    EXPECTED_TITLE,
    PILOT_KEY,
    PILOT_PROFILE_NAME,
    PILOT_SEARCH_TERM,
    PILOT_SOURCE_NAME,
    PreviewApprovalEvidence,
    authorize_fresh_record_for_pipeline,
    is_authorized_pilot_raw_data,
    load_preview_approval_evidence,
)
from src.silver.transformer import (
    get_supported_source_patterns,
    transform_raw_job_to_silver,
)


JOB_URL = (
    "https://careers.eon.com/deutschland/job/"
    "Essen-%28Senior%29-Data-Engineer-Data-%26-AI-%28fmd%29/1414903533/"
)


def preview_payload() -> dict[str, object]:
    return {
        "artifact_type": "successfactors_connector_preview",
        "schema_version": "1.0",
        "target_key": "eon_germany",
        "source_name": PILOT_SOURCE_NAME,
        "listing_url": (
            "https://careers.eon.com/deutschland/go/Germany-Careers/3727101"
            "?q=&sortColumn=sort_title&sortDirection=asc"
        ),
        "search_term": PILOT_SEARCH_TERM,
        "record_count": 1,
        "records": [
            {
                "external_job_id": EXPECTED_EXTERNAL_JOB_ID,
                "title": EXPECTED_TITLE,
                "company_name": EXPECTED_COMPANY_NAME,
                "location": "Essen",
                "source_url": JOB_URL,
                "matched_profile_terms": ["data", "ai", "engineer"],
                "target_employer_verified": True,
                "description_excerpt": "approval evidence only",
            }
        ],
        "provider_requests": 0,
        "pipeline_mutation": False,
        "source_activation_allowed": False,
        "review_output_only_not_pipeline_input": True,
        "boundary": {
            "listing_pages": 1,
            "pagination_enabled": False,
            "max_detail_pages": 5,
            "max_http_requests": 6,
            "browser_automation_used": False,
            "access_control_bypass_used": False,
            "database_write": False,
            "bronze_write": False,
            "silver_write": False,
            "scheduler_change": False,
        },
    }


def write_preview(tmp_path: Path, payload: dict[str, object] | None = None) -> Path:
    path = tmp_path / "eon_preview.json"
    path.write_text(
        json.dumps(payload or preview_payload(), ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path


def fresh_record(*, description: str = "fresh live job description") -> RawJobRecord:
    return RawJobRecord(
        source_name=PILOT_SOURCE_NAME,
        source_url=JOB_URL,
        external_job_id=EXPECTED_EXTERNAL_JOB_ID,
        raw_data={
            "source_family": "successfactors",
            "source_target": "eon_germany",
            "source_type": "employer_origin_ats_backed_career_site",
            "acquisition_boundary": {
                "listing_pages_fetched": 1,
                "pagination_enabled": False,
                "max_detail_pages": 1,
                "request_count": 2,
                "browser_automation_used": False,
                "access_control_bypass_used": False,
                "provider_requests": 0,
                "pipeline_mutation": False,
                "raw_html_persisted": False,
                "review_output_only_not_pipeline_input": True,
            },
            "result_card": {
                "title": EXPECTED_TITLE,
                "company_name": EXPECTED_COMPANY_NAME,
                "location": "Essen",
                "detail_url": JOB_URL,
            },
            "job": {
                "title": EXPECTED_TITLE,
                "company_name": EXPECTED_COMPANY_NAME,
                "location": "Essen",
                "source_url": JOB_URL,
                "description": description,
                "employment_metadata": ["Permanent", "Full time"],
            },
            "listing_evidence": {
                "listing_url": (
                    "https://careers.eon.com/deutschland/go/Germany-Careers/3727101"
                ),
                "title_hint": EXPECTED_TITLE,
                "location_hint": "Essen",
                "matched_profile_terms": ["data", "ai", "engineer"],
                "requested_term_match": True,
            },
            "detail_evidence": {
                "status_code": 200,
                "html_bytes": 1234,
                "target_employer_verified": True,
                "raw_html_persisted": False,
            },
            "observed_at_utc": "2026-08-04T16:18:57+00:00",
        },
    )


def test_preview_artifact_is_validated_only_as_review_evidence(tmp_path: Path) -> None:
    evidence = load_preview_approval_evidence(write_preview(tmp_path))

    assert evidence.external_job_id == EXPECTED_EXTERNAL_JOB_ID
    assert len(evidence.artifact_sha256) == 64
    assert evidence.source_url == JOB_URL


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    [
        ("provider_requests", 1),
        ("pipeline_mutation", True),
        ("source_activation_allowed", True),
        ("review_output_only_not_pipeline_input", False),
    ],
)
def test_preview_artifact_fails_closed_on_boundary_drift(
    tmp_path: Path,
    field: str,
    unsafe_value: object,
) -> None:
    payload = preview_payload()
    payload[field] = unsafe_value

    with pytest.raises(ValueError):
        load_preview_approval_evidence(write_preview(tmp_path, payload))


def test_fresh_record_authorization_creates_a_separate_pipeline_dataset(
    tmp_path: Path,
) -> None:
    evidence = load_preview_approval_evidence(write_preview(tmp_path))
    source_record = fresh_record(description="fresh-data-marker")

    authorized = authorize_fresh_record_for_pipeline(
        source_record,
        evidence=evidence,
        reviewed_by="jens",
        approval_token=APPROVAL_TOKEN,
    )

    assert source_record.raw_data["acquisition_boundary"][
        "review_output_only_not_pipeline_input"
    ] is True
    assert authorized.raw_data["acquisition_boundary"][
        "review_output_only_not_pipeline_input"
    ] is False
    assert authorized.raw_data["job"]["description"] == "fresh-data-marker"
    pilot = authorized.raw_data["pilot_ingestion"]
    assert pilot["pilot_key"] == PILOT_KEY
    assert pilot["preview_artifact_usage"] == (
        "approval_evidence_only_not_job_data_input"
    )
    assert pilot["preview_record_payload_used_as_job_data"] is False
    assert pilot["job_data_origin"] == "fresh_bounded_successfactors_live_fetch"
    assert pilot["provider_requests"] == 0
    assert pilot["assessment_insert_allowed"] is False
    assert pilot["score_invention_allowed"] is False
    assert pilot["scheduler_activation_allowed"] is False
    assert pilot["production_activation_allowed"] is False
    assert is_authorized_pilot_raw_data(authorized.raw_data)


def test_fresh_record_authorization_rejects_wrong_evidence_binding() -> None:
    evidence = PreviewApprovalEvidence(
        artifact_path="preview.json",
        artifact_sha256="a" * 64,
        external_job_id="eon_germany:wrong",
        title=EXPECTED_TITLE,
        company_name=EXPECTED_COMPANY_NAME,
        source_url=JOB_URL,
    )

    with pytest.raises(ValueError, match="does not bind"):
        authorize_fresh_record_for_pipeline(
            fresh_record(),
            evidence=evidence,
            reviewed_by="jens",
            approval_token=APPROVAL_TOKEN,
        )


def test_profile_validation_requires_inactive_one_record_data_binding() -> None:
    binding = validate_profile_row(
        {
            "profile_id": 79,
            "profile_name": PILOT_PROFILE_NAME,
            "source_name": PILOT_SOURCE_NAME,
            "search_location": None,
            "search_radius_km": None,
            "offer_type": 1,
            "page_size": 1,
            "profile_is_active": False,
            "search_term_id": 7901,
            "search_term": PILOT_SEARCH_TERM,
            "term_is_active": True,
        }
    )

    assert binding.profile_is_active is False
    assert binding.term_is_active is True
    assert binding.profile.page_size == 1


def test_profile_validation_stops_if_scheduler_could_select_profile() -> None:
    row = {
        "profile_id": 79,
        "profile_name": PILOT_PROFILE_NAME,
        "source_name": PILOT_SOURCE_NAME,
        "search_location": None,
        "search_radius_km": None,
        "offer_type": 1,
        "page_size": 1,
        "profile_is_active": True,
        "search_term_id": 7901,
        "search_term": PILOT_SEARCH_TERM,
        "term_is_active": True,
    }

    with pytest.raises(ValueError, match="inactive"):
        validate_profile_row(row)


def test_successfactors_silver_transformer_uses_ats_backed_origin_type() -> None:
    raw = fresh_record().raw_data
    raw["acquisition_boundary"]["review_output_only_not_pipeline_input"] = False
    raw_job = {
        "id": 1414903533,
        "source_name": PILOT_SOURCE_NAME,
        "external_job_id": EXPECTED_EXTERNAL_JOB_ID,
        "source_url": JOB_URL,
        "raw_data": raw,
    }

    silver = transform_raw_job_to_silver(raw_job)

    assert silver["raw_job_id"] == 1414903533
    assert silver["title"] == EXPECTED_TITLE
    assert silver["company_name"] == EXPECTED_COMPANY_NAME
    assert silver["city"] == "Essen"
    assert silver["country"] == "DE"
    assert (
        silver["canonical_source_type"]
        == "employer_origin_ats_backed_career_site"
    )
    assert "successfactors:%" in get_supported_source_patterns()


def test_migration_creates_only_inactive_pilot_profile_and_data_term() -> None:
    migration = Path(
        "db/migrations/084_create_eon_controlled_pilot_profile.sql"
    ).read_text(encoding="utf-8")

    assert PILOT_PROFILE_NAME in migration
    assert PILOT_SOURCE_NAME in migration
    assert "'Data'" in migration
    assert "FALSE" in migration
    assert "page_size" in migration
    assert "UPDATE search_profiles" not in migration
    assert "scheduler" in migration.casefold()
    assert "job_product_assessments" not in migration
    assert "raw_jobs" not in migration
    assert "silver_jobs" not in migration


def test_runner_preserves_atomic_and_no_assessment_contract() -> None:
    source = Path(
        "scripts/run_eon_controlled_pilot_ingestion.py"
    ).read_text(encoding="utf-8")

    assert source.count("conn.commit()") == 1
    assert source.count("conn.rollback()") >= 3
    assert "INSERT INTO raw_jobs" in source
    assert "INSERT INTO job_observations" in source
    assert "INSERT INTO silver_jobs" in source
    assert "INSERT INTO silver_processing_decisions" in source
    assert "gold_product_v1_job_readiness" in source
    assert "INSERT INTO job_product_assessments" not in source
    assert "SuccessFactorsPreviewConnector" in source
    assert "max_detail_pages=PILOT_PAGE_SIZE" in source


def test_runner_is_directly_executable_from_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_eon_controlled_pilot_ingestion.py",
            "--help",
        ],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "isolated E.ON Bronze-to-Product-V1 pilot" in result.stdout
