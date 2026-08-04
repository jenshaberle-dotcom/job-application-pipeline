from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from src.connectors.base import RawJobRecord


PILOT_KEY = "EON-CONTROLLED-PILOT-INGESTION-001"
PILOT_PROFILE_NAME = "eon_successfactors_data_controlled_pilot"
PILOT_SOURCE_NAME = "successfactors:eon_germany"
PILOT_TARGET_KEY = "eon_germany"
PILOT_SEARCH_TERM = "Data"
PILOT_PAGE_SIZE = 1
EXPECTED_EXTERNAL_JOB_ID = "eon_germany:1414903533"
EXPECTED_TITLE = "(Senior) Data Engineer Data & AI (f/m/d)"
EXPECTED_COMPANY_NAME = "E.ON Digital Technology GmbH"
EXPECTED_HOST = "careers.eon.com"
APPROVAL_TOKEN = PILOT_KEY


@dataclass(frozen=True)
class PreviewApprovalEvidence:
    artifact_path: str
    artifact_sha256: str
    external_job_id: str
    title: str
    company_name: str
    source_url: str


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{label} must be an object")
    return value


def _allowed_job_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").casefold() == EXPECTED_HOST
        and parsed.path.startswith("/deutschland/job/")
        and "/1414903533/" in parsed.path
    )


def approval_token_sha256(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def load_preview_approval_evidence(path: Path) -> PreviewApprovalEvidence:
    raw_bytes = path.read_bytes()
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("preview artifact must be valid UTF-8 JSON") from exc

    root = _mapping(payload, "preview artifact")
    _require(
        root.get("artifact_type") == "successfactors_connector_preview",
        "unexpected preview artifact type",
    )
    _require(root.get("schema_version") == "1.0", "unexpected preview schema version")
    _require(root.get("target_key") == PILOT_TARGET_KEY, "preview target mismatch")
    _require(root.get("source_name") == PILOT_SOURCE_NAME, "preview source mismatch")
    _require(
        str(root.get("search_term") or "").casefold() == PILOT_SEARCH_TERM.casefold(),
        "preview must use the exact Data search term",
    )
    _require(root.get("record_count") == 1, "preview must contain exactly one record")
    records = root.get("records")
    _require(isinstance(records, list) and len(records) == 1, "preview records mismatch")
    _require(root.get("provider_requests") == 0, "preview used provider requests")
    _require(root.get("pipeline_mutation") is False, "preview mutated pipeline state")
    _require(
        root.get("source_activation_allowed") is False,
        "preview grants source activation",
    )
    _require(
        root.get("review_output_only_not_pipeline_input") is True,
        "preview must remain review-only evidence",
    )

    boundary = _mapping(root.get("boundary"), "preview boundary")
    for key in (
        "database_write",
        "bronze_write",
        "silver_write",
        "scheduler_change",
        "browser_automation_used",
        "access_control_bypass_used",
    ):
        _require(boundary.get(key) is False, f"unsafe preview boundary: {key}")
    _require(boundary.get("listing_pages") == 1, "preview listing-page boundary mismatch")
    _require(boundary.get("pagination_enabled") is False, "preview enabled pagination")

    record = _mapping(records[0], "preview record")
    _require(
        record.get("external_job_id") == EXPECTED_EXTERNAL_JOB_ID,
        "preview external job id mismatch",
    )
    _require(record.get("title") == EXPECTED_TITLE, "preview title mismatch")
    _require(
        record.get("company_name") == EXPECTED_COMPANY_NAME,
        "preview employer mismatch",
    )
    _require(
        record.get("target_employer_verified") is True,
        "preview employer was not verified",
    )
    _require(_allowed_job_url(record.get("source_url")), "preview job URL mismatch")

    return PreviewApprovalEvidence(
        artifact_path=str(path),
        artifact_sha256=sha256(raw_bytes).hexdigest(),
        external_job_id=EXPECTED_EXTERNAL_JOB_ID,
        title=EXPECTED_TITLE,
        company_name=EXPECTED_COMPANY_NAME,
        source_url=str(record["source_url"]),
    )


def validate_fresh_pilot_record(record: RawJobRecord) -> None:
    _require(record.source_name == PILOT_SOURCE_NAME, "fresh source mismatch")
    _require(
        record.external_job_id == EXPECTED_EXTERNAL_JOB_ID,
        "fresh external job id mismatch",
    )
    _require(_allowed_job_url(record.source_url), "fresh job URL mismatch")

    raw_data = _mapping(record.raw_data, "fresh raw data")
    _require(raw_data.get("source_family") == "successfactors", "fresh family mismatch")
    _require(raw_data.get("source_target") == PILOT_TARGET_KEY, "fresh target mismatch")
    _require(
        raw_data.get("source_type") == "employer_origin_ats_backed_career_site",
        "fresh source type mismatch",
    )

    result_card = _mapping(raw_data.get("result_card"), "fresh result card")
    _require(result_card.get("title") == EXPECTED_TITLE, "fresh title mismatch")
    _require(
        result_card.get("company_name") == EXPECTED_COMPANY_NAME,
        "fresh employer mismatch",
    )

    job = _mapping(raw_data.get("job"), "fresh job")
    _require(job.get("title") == EXPECTED_TITLE, "fresh job title mismatch")
    _require(
        job.get("company_name") == EXPECTED_COMPANY_NAME,
        "fresh job employer mismatch",
    )
    _require(_allowed_job_url(job.get("source_url")), "fresh job source URL mismatch")

    listing = _mapping(raw_data.get("listing_evidence"), "fresh listing evidence")
    _require(
        listing.get("requested_term_match") is True,
        "fresh record does not match the requested Data term",
    )

    detail = _mapping(raw_data.get("detail_evidence"), "fresh detail evidence")
    _require(
        detail.get("target_employer_verified") is True,
        "fresh employer was not verified",
    )
    _require(detail.get("status_code") == 200, "fresh detail request was not HTTP 200")

    boundary = _mapping(raw_data.get("acquisition_boundary"), "fresh boundary")
    expected = {
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
    }
    for key, value in expected.items():
        _require(boundary.get(key) == value, f"fresh boundary mismatch: {key}")


def authorize_fresh_record_for_pipeline(
    record: RawJobRecord,
    *,
    evidence: PreviewApprovalEvidence,
    reviewed_by: str,
    approval_token: str,
) -> RawJobRecord:
    validate_fresh_pilot_record(record)
    _require(bool(reviewed_by.strip()), "reviewer identity is required")
    _require(approval_token == APPROVAL_TOKEN, "invalid pilot approval token")
    _require(
        evidence.external_job_id == record.external_job_id,
        "approval evidence does not bind the fresh record",
    )

    raw_data = deepcopy(record.raw_data)
    source_boundary = dict(_mapping(raw_data["acquisition_boundary"], "fresh boundary"))
    raw_data["acquisition_boundary"] = {
        **source_boundary,
        "pipeline_mutation": True,
        "review_output_only_not_pipeline_input": False,
        "explicitly_authorized_pipeline_dataset": True,
    }
    raw_data["pilot_ingestion"] = {
        "schema_version": "eon_controlled_pilot_ingestion.v1",
        "pilot_key": PILOT_KEY,
        "authorization_status": "explicitly_authorized_pipeline_dataset",
        "authorization_scope": "single_record_bronze_silver_product_readiness_pilot",
        "reviewed_by": reviewed_by.strip(),
        "approval_token_sha256": approval_token_sha256(approval_token),
        "preview_artifact_sha256": evidence.artifact_sha256,
        "preview_artifact_usage": "approval_evidence_only_not_job_data_input",
        "preview_record_payload_used_as_job_data": False,
        "job_data_origin": "fresh_bounded_successfactors_live_fetch",
        "source_record_boundary_before_authorization": source_boundary,
        "record_limit": 1,
        "http_request_limit": 2,
        "provider_requests": 0,
        "assessment_insert_allowed": False,
        "score_invention_allowed": False,
        "scheduler_activation_allowed": False,
        "production_activation_allowed": False,
    }

    return RawJobRecord(
        source_name=record.source_name,
        source_url=record.source_url,
        external_job_id=record.external_job_id,
        raw_data=raw_data,
    )


def is_authorized_pilot_raw_data(raw_data: object) -> bool:
    if not isinstance(raw_data, Mapping):
        return False
    pilot = raw_data.get("pilot_ingestion")
    boundary = raw_data.get("acquisition_boundary")
    return (
        isinstance(pilot, Mapping)
        and pilot.get("pilot_key") == PILOT_KEY
        and pilot.get("authorization_status")
        == "explicitly_authorized_pipeline_dataset"
        and pilot.get("preview_record_payload_used_as_job_data") is False
        and pilot.get("production_activation_allowed") is False
        and isinstance(boundary, Mapping)
        and boundary.get("explicitly_authorized_pipeline_dataset") is True
        and boundary.get("review_output_only_not_pipeline_input") is False
    )
