"""Project bounded Bronze vacancy evidence into durable Silver requirement truth.

This module is the F4A-R3 Bronze2E bridge. It consumes only already persisted,
provider-free Bronze/observation evidence and emits a bounded, source-neutral
requirement-evidence payload. It never reads Candidate Facts and grants no fit,
ranking, Top-5 or application authority.

Structured connector evidence wins only when it is semantically equivalent to the
requested field. Bounded description evidence reuses the same generic F4A
composition used by Product so weak shell signals, partial-mobile wording and
structured/text conflicts remain fail-closed across the Bronze2E path.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from src.search_intelligence.product_v1_requirement_evidence import (
    ProductV1RequirementEvidence,
    extract_product_v1_requirement_evidence,
)


SILVER_REQUIREMENT_EVIDENCE_SCHEMA = "silver_job_requirement_evidence.v1"
GENERIC_DETAIL_EVIDENCE_SCHEMA = "generic_job_detail_evidence_v1"


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _string_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _text(item)
        key = text.casefold()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
    return result


def _field(status: str, **values: object) -> dict[str, object]:
    return {"status": status, **values}


def _composed_evidence(
    *,
    description: object,
    title: object,
    source_url: str,
) -> ProductV1RequirementEvidence | None:
    description_text = _text(description)
    title_text = _text(title)
    if not description_text or not title_text or not _text(source_url):
        return None
    try:
        return extract_product_v1_requirement_evidence(
            html="",
            text=description_text,
            title=title_text,
            page_title=title_text,
            source_url=source_url,
        )
    except ValueError:
        return None


def _reference_payloads(
    evidence: ProductV1RequirementEvidence | None,
    field_name: str,
) -> list[dict[str, object]]:
    if evidence is None:
        return []
    return [
        reference.canonical_payload()
        for reference in evidence.assessment.references
        if reference.field == field_name
    ]


def _semantic_reference_payloads(
    evidence: ProductV1RequirementEvidence | None,
    field_name: str,
) -> list[dict[str, object]]:
    if evidence is None:
        return []
    return [
        {
            "field": reference.field,
            "source_url": reference.source_url,
            "evidence": reference.evidence,
            "value": reference.value,
            "span_start": reference.span_start,
            "span_end": reference.span_end,
        }
        for reference in evidence.semantic_references
        if reference.field == field_name
    ]


def build_silver_requirement_evidence(
    raw_job: Mapping[str, Any],
) -> dict[str, object]:
    """Build one bounded Silver requirement payload from canonical Bronze evidence."""

    raw_data = _mapping(raw_job.get("raw_data"))
    job = _mapping(raw_data.get("job"))
    metadata = _mapping(job.get("metadata"))
    detail = _mapping(raw_data.get("detail_evidence"))

    source_url = _text(
        job.get("source_url")
        or raw_job.get("source_url")
        or detail.get("canonical_origin_url")
    )
    title = _text(job.get("title") or raw_job.get("title"))
    description = detail.get("description_excerpt") or job.get("description")
    composed = _composed_evidence(
        description=description,
        title=title,
        source_url=source_url,
    )
    assessment = composed.assessment if composed is not None else None

    parser_family = _text(detail.get("parser_family")) or "unclassified"
    methods = _string_list(detail.get("methods"))
    source_evidence_schema = _text(detail.get("schema")) or None

    structured_skills = _string_list(detail.get("skills")) or _string_list(job.get("skills"))
    bounded_skills = list(composed.job_skills) if composed is not None else []
    if structured_skills:
        job_skills = structured_skills
        skills_status = "observed_structured"
        skills_source = "bronze_structured"
    elif bounded_skills:
        job_skills = bounded_skills
        skills_status = "observed_bounded_text"
        skills_source = "bronze_description_excerpt"
    else:
        job_skills = []
        skills_status = "source_absent_or_unresolved"
        skills_source = None

    structured_employment = _string_list(detail.get("employment_types")) or _string_list(
        metadata.get("employment_types")
    )

    remote = detail.get("remote")
    workplace_type = _text(metadata.get("workplace_type")).casefold()
    structured_work_model = (
        "remote" if remote is True or workplace_type == "remote" else "unknown"
    )
    bounded_work_model = composed.work_model if composed is not None else "unknown"
    conflicts = set(composed.conflicted_fields if composed is not None else ())
    if (
        structured_work_model != "unknown"
        and bounded_work_model != "unknown"
        and structured_work_model != bounded_work_model
    ):
        conflicts.add("work_model")
        work_model = "unknown"
        work_model_status = "conflict"
        work_model_source = "bronze_structured+bronze_description_excerpt"
    elif structured_work_model != "unknown":
        work_model = structured_work_model
        work_model_status = "observed_structured"
        work_model_source = "bronze_structured"
    elif bounded_work_model != "unknown":
        work_model = bounded_work_model
        work_model_status = "observed_bounded_text"
        work_model_source = "bronze_description_excerpt"
    else:
        work_model = "unknown"
        work_model_status = "source_absent_or_unresolved"
        work_model_source = None

    if assessment is not None and assessment.employment_type != "unknown":
        employment_type = assessment.employment_type
        employment_status = "observed_bounded_text"
    else:
        employment_type = "unknown"
        employment_status = "source_absent_or_unresolved"

    languages = list(assessment.required_languages) if assessment is not None else []
    weekly_min = assessment.weekly_hours_min if assessment is not None else None
    weekly_max = assessment.weekly_hours_max if assessment is not None else None
    requirements_seniority = (
        assessment.requirements_seniority if assessment is not None else "unknown"
    )

    fields: dict[str, object] = {
        "employment_type": _field(
            "conflict" if "employment_type" in conflicts else employment_status,
            value=("unknown" if "employment_type" in conflicts else employment_type),
            source_employment_types=structured_employment,
            evidence=_reference_payloads(composed, "employment_type"),
        ),
        "required_languages": _field(
            "observed_bounded_text" if languages else "source_absent_or_unresolved",
            values=languages,
            evidence=_reference_payloads(composed, "required_languages"),
        ),
        "weekly_hours": _field(
            (
                "conflict"
                if "weekly_hours" in conflicts
                else "observed_bounded_text"
                if weekly_min is not None or weekly_max is not None
                else "source_absent_or_unresolved"
            ),
            minimum=None if "weekly_hours" in conflicts else weekly_min,
            maximum=None if "weekly_hours" in conflicts else weekly_max,
            evidence=_reference_payloads(composed, "weekly_hours"),
        ),
        "work_model": _field(
            work_model_status,
            value=work_model,
            evidence_source=work_model_source,
            evidence=(
                _reference_payloads(composed, "work_model")
                + _semantic_reference_payloads(composed, "remote")
            ),
        ),
        "requirements_seniority": _field(
            (
                "conflict"
                if "requirements_seniority" in conflicts
                else "observed_bounded_text"
                if requirements_seniority != "unknown"
                else "source_absent_or_unresolved"
            ),
            value=(
                "unknown"
                if "requirements_seniority" in conflicts
                else requirements_seniority
            ),
            evidence=_reference_payloads(composed, "requirements_seniority"),
        ),
        "job_skills": _field(
            skills_status,
            values=job_skills,
            evidence_source=skills_source,
            evidence=_semantic_reference_payloads(composed, "skills"),
        ),
    }

    unresolved_fields = [
        name
        for name, value in fields.items()
        if isinstance(value, Mapping)
        and str(value.get("status") or "") in {"source_absent_or_unresolved", "conflict"}
    ]

    return {
        "schema": SILVER_REQUIREMENT_EVIDENCE_SCHEMA,
        "source_evidence_schema": source_evidence_schema,
        "parser_family": parser_family,
        "methods": methods,
        "source_url": source_url or None,
        "description_source": detail.get("description_source"),
        "structured_jobposting_found": detail.get("structured_jobposting_found") is True,
        "fields": fields,
        "conflicted_fields": sorted(conflicts),
        "unresolved_fields": sorted(unresolved_fields),
        "raw_html_persisted": False,
        "authority": {
            "job_source_evidence_only": True,
            "candidate_fact_authority": False,
            "capability_fit_authority": False,
            "hard_filter_authority": False,
            "ranking_authority": False,
            "top5_authority": False,
            "application_authority": False,
        },
    }


def requirement_evidence_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def synchronize_silver_requirement_evidence(
    cur: Any,
    *,
    silver_job_id: int,
    raw_job: Mapping[str, Any],
) -> None:
    """Upsert one Silver-side evidence row inside the caller's Silver transaction."""

    payload = build_silver_requirement_evidence(raw_job)
    evidence_hash = requirement_evidence_hash(payload)
    parser_family = _text(payload.get("parser_family")) or "unclassified"
    source_schema = _text(payload.get("source_evidence_schema")) or None
    raw_job_id = int(raw_job.get("id") or raw_job.get("raw_job_id") or 0)
    if raw_job_id <= 0:
        raise ValueError("raw_job id is required for Silver requirement evidence")

    cur.execute(
        """
        INSERT INTO silver_job_requirement_evidence (
            silver_job_id,
            raw_job_id,
            evidence_schema,
            source_evidence_schema,
            parser_family,
            evidence_hash,
            evidence_payload
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (silver_job_id)
        DO UPDATE SET
            raw_job_id = EXCLUDED.raw_job_id,
            evidence_schema = EXCLUDED.evidence_schema,
            source_evidence_schema = EXCLUDED.source_evidence_schema,
            parser_family = EXCLUDED.parser_family,
            evidence_hash = EXCLUDED.evidence_hash,
            evidence_payload = EXCLUDED.evidence_payload,
            updated_at = NOW()
        WHERE silver_job_requirement_evidence.evidence_hash IS DISTINCT FROM EXCLUDED.evidence_hash
           OR silver_job_requirement_evidence.raw_job_id IS DISTINCT FROM EXCLUDED.raw_job_id
        """,
        (
            silver_job_id,
            raw_job_id,
            SILVER_REQUIREMENT_EVIDENCE_SCHEMA,
            source_schema,
            parser_family,
            evidence_hash,
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
        ),
    )


__all__ = [
    "GENERIC_DETAIL_EVIDENCE_SCHEMA",
    "SILVER_REQUIREMENT_EVIDENCE_SCHEMA",
    "build_silver_requirement_evidence",
    "requirement_evidence_hash",
    "synchronize_silver_requirement_evidence",
]
