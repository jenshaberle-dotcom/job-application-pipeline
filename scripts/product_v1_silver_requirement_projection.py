"""Read-only Product presentation projection for Silver Bronze2E requirement evidence.

The Silver sidecar is job-source evidence only. This adapter deliberately flattens
its bounded field payload into the existing operator presentation shape without
creating Candidate Fact, capability-fit, hard-filter, ranking, Top-5 or application
authority.
"""

from __future__ import annotations

from typing import Mapping


SILVER_REQUIREMENT_EVIDENCE_SCHEMA = "silver_job_requirement_evidence.v1"


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if str(item).strip()]


def project_silver_requirement_evidence(
    payload: object,
) -> dict[str, object] | None:
    """Flatten one canonical Silver requirement sidecar for operator display."""

    if not isinstance(payload, Mapping):
        return None
    if payload.get("schema") != SILVER_REQUIREMENT_EVIDENCE_SCHEMA:
        return None

    authority = _mapping(payload.get("authority"))
    if authority.get("job_source_evidence_only") is not True:
        return None
    forbidden_authorities = (
        "candidate_fact_authority",
        "capability_fit_authority",
        "hard_filter_authority",
        "ranking_authority",
        "top5_authority",
        "application_authority",
    )
    if any(authority.get(name) is not False for name in forbidden_authorities):
        return None

    fields = _mapping(payload.get("fields"))
    employment = _mapping(fields.get("employment_type"))
    languages = _mapping(fields.get("required_languages"))
    weekly = _mapping(fields.get("weekly_hours"))
    work_model = _mapping(fields.get("work_model"))
    seniority = _mapping(fields.get("requirements_seniority"))
    skills = _mapping(fields.get("job_skills"))

    parser_family = str(payload.get("parser_family") or "unclassified")
    return {
        "requirement_evidence_status": (
            "origin_unavailable" if parser_family == "origin_unavailable" else "assessed"
        ),
        "requirement_evidence_source": "silver_job_requirement_evidence",
        "requirement_evidence_schema": SILVER_REQUIREMENT_EVIDENCE_SCHEMA,
        "employment_type": str(employment.get("value") or "unknown"),
        "employment_evidence_status": str(
            employment.get("status") or "source_absent_or_unresolved"
        ),
        "required_languages": _string_list(languages.get("values")),
        "language_evidence_status": str(
            languages.get("status") or "source_absent_or_unresolved"
        ),
        "weekly_hours_min": weekly.get("minimum"),
        "weekly_hours_max": weekly.get("maximum"),
        "weekly_hours_evidence_status": str(
            weekly.get("status") or "source_absent_or_unresolved"
        ),
        "work_model": str(work_model.get("value") or "unknown"),
        "work_model_resolution": str(
            work_model.get("status") or "source_absent_or_unresolved"
        ),
        "requirements_seniority": str(seniority.get("value") or "unknown"),
        "seniority_evidence_status": str(
            seniority.get("status") or "source_absent_or_unresolved"
        ),
        "job_skills": _string_list(skills.get("values")),
        "requirement_conflicted_fields": _string_list(payload.get("conflicted_fields")),
        "requirement_unresolved_fields": _string_list(payload.get("unresolved_fields")),
        "requirement_origin_unavailable_reason": payload.get("origin_unavailable_reason"),
    }


__all__ = [
    "SILVER_REQUIREMENT_EVIDENCE_SCHEMA",
    "project_silver_requirement_evidence",
]
