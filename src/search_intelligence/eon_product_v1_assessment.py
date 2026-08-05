from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping

from src.ingestion.eon_controlled_pilot import (
    EXPECTED_EXTERNAL_JOB_ID,
    EXPECTED_TITLE,
    PILOT_SOURCE_NAME,
    is_authorized_pilot_raw_data,
)

ASSESSMENT_KEY = "EON-PRODUCT-V1-ASSESSMENT-001"
APPROVAL_TOKEN = ASSESSMENT_KEY
EXPECTED_CANONICAL_SOURCE_TYPE = "employer_origin_ats_backed_career_site"
EXPECTED_POST_ASSESSMENT_STATUS = "hard_filter_decision_required"
DEFAULT_ASSESSED_BY = "deterministic_eon_partial_product_v1"


@dataclass(frozen=True)
class EonAssessmentBinding:
    raw_job_id: int
    silver_job_id: int
    source_name: str
    external_job_id: str
    title: str
    canonical_source_type: str
    raw_data: Mapping[str, Any]


@dataclass(frozen=True)
class PartialProductAssessment:
    silver_job_id: int
    origin_validation_status: str
    activity_status: str
    hard_filter_status: str
    profile_direction_score: float | None
    data_focus_score: float | None
    reliability_focus_score: float | None
    evidence_quality_score: float | None
    overall_quality_score: float | None
    work_model: str
    commute_minutes: int | None
    public_transport_quality: str
    ranking_factors: Mapping[str, Any]
    explanations: tuple[Mapping[str, Any], ...]
    uncertainties: tuple[Mapping[str, Any], ...]
    policy_key: str
    policy_version: str
    assessed_by: str
    employment_type: str
    employment_evidence_status: str
    required_languages: tuple[str, ...]
    language_evidence_status: str
    weekly_hours_min: float | None
    weekly_hours_max: float | None
    weekly_hours_evidence_status: str
    salary_min_gross_eur: int | None
    salary_max_gross_eur: int | None
    salary_evidence_status: str
    title_seniority: str
    requirements_seniority: str
    capability_fit_status: str
    seniority_evidence_status: str

    def canonical_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["explanations"] = list(self.explanations)
        payload["uncertainties"] = list(self.uncertainties)
        payload["required_languages"] = list(self.required_languages)
        return payload


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _sequence_of_strings(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a string array")
    return tuple(item.strip() for item in value if item.strip())


def _normalize_employment_metadata(value: str) -> str:
    return " ".join(value.casefold().replace("-", " ").split())


def _has_full_time_option(values: tuple[str, ...]) -> bool:
    normalized = tuple(_normalize_employment_metadata(value) for value in values)
    return any(
        "full time" in value
        or "full or part time" in value
        or "vollzeit" in value
        for value in normalized
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _parse_observed_at(value: object) -> str:
    _require(isinstance(value, str) and bool(value.strip()), "observed_at_utc is missing")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("observed_at_utc must be ISO-8601") from exc
    _require(parsed.tzinfo is not None, "observed_at_utc must be timezone-aware")
    return value.strip()


def bind_eon_job(
    *,
    row: Mapping[str, Any],
    expected_raw_job_id: int,
    expected_silver_job_id: int,
) -> EonAssessmentBinding:
    raw_data = _mapping(row.get("raw_data"), "raw_data")
    raw_job_id = int(row["raw_job_id"])
    silver_job_id = int(row["silver_job_id"])
    source_name = str(row["source_name"])
    external_job_id = str(row["external_job_id"])
    title = str(row["title"])
    canonical_source_type = str(row["canonical_source_type"])

    _require(raw_job_id == expected_raw_job_id, "raw job ID mismatch")
    _require(silver_job_id == expected_silver_job_id, "Silver job ID mismatch")
    _require(source_name == PILOT_SOURCE_NAME, "E.ON source mismatch")
    _require(external_job_id == EXPECTED_EXTERNAL_JOB_ID, "E.ON external job ID mismatch")
    _require(title == EXPECTED_TITLE, "E.ON title mismatch")
    _require(
        canonical_source_type == EXPECTED_CANONICAL_SOURCE_TYPE,
        "E.ON canonical source type mismatch",
    )
    _require(is_authorized_pilot_raw_data(raw_data), "raw job is not an authorized E.ON pilot dataset")

    acquisition = _mapping(raw_data.get("acquisition_boundary"), "acquisition_boundary")
    detail = _mapping(raw_data.get("detail_evidence"), "detail_evidence")
    job = _mapping(raw_data.get("job"), "job")

    _require(acquisition.get("provider_requests") == 0, "pilot raw data used provider requests")
    _require(
        acquisition.get("explicitly_authorized_pipeline_dataset") is True,
        "pilot raw data is not explicitly authorized for pipeline use",
    )
    _require(
        acquisition.get("production_activation_allowed") is not True,
        "pilot raw data unexpectedly grants production activation",
    )
    _require(detail.get("status_code") == 200, "exact E.ON detail observation was not HTTP 200")
    _require(detail.get("target_employer_verified") is True, "E.ON employer was not verified")
    _parse_observed_at(raw_data.get("observed_at_utc"))
    _require(job.get("title") == EXPECTED_TITLE, "raw E.ON job title mismatch")

    return EonAssessmentBinding(
        raw_job_id=raw_job_id,
        silver_job_id=silver_job_id,
        source_name=source_name,
        external_job_id=external_job_id,
        title=title,
        canonical_source_type=canonical_source_type,
        raw_data=raw_data,
    )


def _validate_policies(
    ranking_policy: Mapping[str, Any],
    hard_filter_policy: Mapping[str, Any],
) -> tuple[str, str]:
    _require(ranking_policy.get("policy_key") == "default", "ranking policy key mismatch")
    _require(ranking_policy.get("status") == "approved", "ranking policy is not approved")
    _require(hard_filter_policy.get("policy_key") == "default", "hard-filter policy key mismatch")
    _require(hard_filter_policy.get("status") == "approved", "hard-filter policy is not approved")
    _require(
        hard_filter_policy.get("unknown_required_evidence_action")
        == "manual_review_required",
        "hard-filter policy does not fail closed on missing evidence",
    )
    ranking_version = str(ranking_policy.get("policy_version") or "").strip()
    hard_filter_version = str(hard_filter_policy.get("policy_version") or "").strip()
    _require(bool(ranking_version), "ranking policy version is missing")
    _require(ranking_version == hard_filter_version, "Product V1 policy versions differ")
    return "default", ranking_version


def build_partial_assessment(
    *,
    binding: EonAssessmentBinding,
    ranking_policy: Mapping[str, Any],
    hard_filter_policy: Mapping[str, Any],
    assessed_by: str = DEFAULT_ASSESSED_BY,
) -> PartialProductAssessment:
    assessor = assessed_by.strip()
    _require(bool(assessor), "assessed_by must not be blank")
    policy_key, policy_version = _validate_policies(ranking_policy, hard_filter_policy)

    raw_data = binding.raw_data
    job = _mapping(raw_data.get("job"), "job")
    detail = _mapping(raw_data.get("detail_evidence"), "detail_evidence")
    observed_at = _parse_observed_at(raw_data.get("observed_at_utc"))
    employment_metadata = _sequence_of_strings(
        job.get("employment_metadata"),
        "job.employment_metadata",
    )
    normalized_metadata = {
        _normalize_employment_metadata(value) for value in employment_metadata
    }
    _require("permanent" in normalized_metadata, "Permanent employment is not explicitly evidenced")
    _require(
        _has_full_time_option(employment_metadata),
        "Full-time-compatible metadata is not explicitly evidenced",
    )

    title = str(job.get("title") or "")
    _require(title == EXPECTED_TITLE, "job title does not support the bounded seniority evidence")
    _require("(senior)" in title.casefold(), "Senior title marker is missing")

    explanations: tuple[Mapping[str, Any], ...] = (
        {
            "factor": "origin_validation",
            "status": "validated",
            "evidence": "authorized exact E.ON SuccessFactors ATS pilot dataset",
        },
        {
            "factor": "activity",
            "status": "active",
            "evidence": "fresh exact-job SuccessFactors detail observation returned HTTP 200",
            "observed_at_utc": observed_at,
            "status_code": int(detail["status_code"]),
        },
        {
            "factor": "employment",
            "status": "permanent_full_time_option",
            "evidence": list(employment_metadata),
        },
        {
            "factor": "title_seniority",
            "status": "senior",
            "evidence": title,
        },
    )
    uncertainties: tuple[Mapping[str, Any], ...] = (
        {"factor": "required_languages", "status": "unknown", "action": "manual_review_required"},
        {"factor": "weekly_hours", "status": "unknown", "action": "manual_review_required"},
        {"factor": "salary", "status": "unknown", "action": "soft_signal_only"},
        {"factor": "work_model", "status": "unknown", "action": "review_required"},
        {"factor": "requirements_seniority", "status": "unknown", "action": "manual_review_required"},
        {"factor": "candidate_capability_fit", "status": "unknown", "action": "manual_review_required"},
        {"factor": "ranking_scores", "status": "not_assessed", "action": "separate_evidence_bound_slice"},
    )

    return PartialProductAssessment(
        silver_job_id=binding.silver_job_id,
        origin_validation_status="validated",
        activity_status="active",
        hard_filter_status="unknown",
        profile_direction_score=None,
        data_focus_score=None,
        reliability_focus_score=None,
        evidence_quality_score=None,
        overall_quality_score=None,
        work_model="unknown",
        commute_minutes=None,
        public_transport_quality="unknown",
        ranking_factors={
            "schema_version": "eon_partial_product_v1_assessment.v1",
            "assessment_key": ASSESSMENT_KEY,
            "source_name": binding.source_name,
            "external_job_id": binding.external_job_id,
            "raw_job_id": binding.raw_job_id,
            "provider_requests": 0,
            "scores_intentionally_omitted": True,
            "scope": "exact_eon_pilot_job_only",
        },
        explanations=explanations,
        uncertainties=uncertainties,
        policy_key=policy_key,
        policy_version=policy_version,
        assessed_by=assessor,
        employment_type="permanent",
        employment_evidence_status="observed",
        required_languages=(),
        language_evidence_status="unknown",
        weekly_hours_min=None,
        weekly_hours_max=None,
        weekly_hours_evidence_status="unknown",
        salary_min_gross_eur=None,
        salary_max_gross_eur=None,
        salary_evidence_status="unknown",
        title_seniority="senior",
        requirements_seniority="unknown",
        capability_fit_status="unknown",
        seniority_evidence_status="unknown",
    )
