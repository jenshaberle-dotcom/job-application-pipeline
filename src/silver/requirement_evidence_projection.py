"""Project bounded Bronze vacancy evidence into durable Silver requirement truth.

This module is the F4A Bronze2E bridge. It consumes only already persisted,
provider-free Bronze/observation evidence and emits a bounded, source-neutral
requirement-evidence payload. It never reads Candidate Facts and grants no fit,
ranking, Top-5 or application authority.

Structured connector evidence wins only when it is semantically equivalent to the
requested field. Bounded requirement text and supplemental visible employer text
are independently preserved so structured JobPosting data cannot hide facts that
are visibly present elsewhere on the vacancy page. Optional evidence observers may
discover spans, but only JAP-owned deterministic verification can promote them.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from src.search_intelligence.product_v1_requirement_evidence import (
    ProductV1RequirementEvidence,
    extract_product_v1_requirement_evidence,
)
from src.silver.operator_requirement_semantics import (
    ObservedFact,
    collect_observed_facts,
    infer_posting_language,
    normalize_employment_scope,
    observed_facts_by_field,
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


def _fact_payloads(facts: tuple[ObservedFact, ...]) -> list[dict[str, object]]:
    return [fact.canonical_payload() for fact in facts]


def _has_bounded_requirement_surface(detail: Mapping[str, Any]) -> bool:
    return any(
        _text(detail.get(key))
        for key in (
            "requirement_text_excerpt",
            "requirement_text_source",
            "description_excerpt",
            "description_source",
            "main_text_excerpt",
            "visible_text_excerpt",
        )
    )


def _missing_status(
    detail: Mapping[str, Any],
    *,
    structured_signal: bool = False,
) -> str:
    if _text(detail.get("parser_family")) == "origin_unavailable":
        return "origin_unavailable"
    if detail.get("schema") != GENERIC_DETAIL_EVIDENCE_SCHEMA:
        return "extractor_gap"
    if structured_signal or _has_bounded_requirement_surface(detail):
        return "source_absent"
    return "extractor_gap"


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


def _single_fact_mapping(
    facts: tuple[ObservedFact, ...],
) -> tuple[Mapping[str, Any] | None, bool]:
    mappings = [fact.value for fact in facts if isinstance(fact.value, Mapping)]
    unique = {json.dumps(dict(value), sort_keys=True, default=str) for value in mappings}
    if not unique:
        return None, False
    if len(unique) != 1:
        return None, True
    target = next(iter(unique))
    for value in mappings:
        if json.dumps(dict(value), sort_keys=True, default=str) == target:
            return value, False
    return None, False


def _single_fact_scalar(
    facts: tuple[ObservedFact, ...],
) -> tuple[object | None, bool]:
    values = [fact.value for fact in facts if not isinstance(fact.value, Mapping)]
    unique = {repr(value) for value in values}
    if not unique:
        return None, False
    if len(unique) != 1:
        return None, True
    return values[0], False


def build_silver_requirement_evidence(
    raw_job: Mapping[str, Any],
) -> dict[str, object]:
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
    requirement_text = (
        detail.get("requirement_text_excerpt")
        or job.get("requirement_text")
        or detail.get("description_excerpt")
        or job.get("description")
    )
    supplemental_text = (
        detail.get("visible_text_excerpt")
        or detail.get("main_text_excerpt")
        or requirement_text
    )
    requirement_text_source = _text(
        detail.get("requirement_text_source")
        or metadata.get("requirement_text_source")
        or detail.get("description_source")
    ) or None
    composed = _composed_evidence(
        description=requirement_text,
        title=title,
        source_url=source_url,
    )
    supplemental_composed = (
        _composed_evidence(
            description=supplemental_text,
            title=title,
            source_url=source_url,
        )
        if _text(supplemental_text) and _text(supplemental_text) != _text(requirement_text)
        else None
    )
    assessment = composed.assessment if composed is not None else None
    supplemental_assessment = (
        supplemental_composed.assessment if supplemental_composed is not None else None
    )
    observed_facts = collect_observed_facts(supplemental_text)
    facts_by_field = observed_facts_by_field(observed_facts)

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
        skills_source = "bronze_requirement_text"
    else:
        job_skills = []
        skills_status = _missing_status(detail)
        skills_source = None

    structured_employment = _string_list(detail.get("employment_types")) or _string_list(
        metadata.get("employment_types")
    )
    employment_scope = normalize_employment_scope(structured_employment)
    structured_work_hours = _text(detail.get("work_hours") or metadata.get("work_hours")) or None

    experience_requirement = _text(
        detail.get("experience_requirement") or metadata.get("experience_requirement")
    ) or None
    experience_months_raw = detail.get("experience_months", metadata.get("experience_months"))
    experience_months = (
        float(experience_months_raw)
        if isinstance(experience_months_raw, (int, float))
        else None
    )
    experience_min_months = experience_months
    experience_max_months = experience_months
    experience_status = (
        "observed_structured"
        if experience_requirement or experience_months is not None
        else _missing_status(detail)
    )
    experience_observer_facts = tuple(facts_by_field.get("experience", ()))
    if experience_months is None and not experience_requirement:
        experience_observed, experience_conflict = _single_fact_mapping(
            experience_observer_facts
        )
        if experience_conflict:
            experience_status = "conflict"
        elif experience_observed is not None:
            minimum = experience_observed.get("minimum_months")
            maximum = experience_observed.get("maximum_months")
            if isinstance(minimum, (int, float)) and isinstance(maximum, (int, float)):
                experience_min_months = float(minimum)
                experience_max_months = float(maximum)
                experience_months = (
                    float(minimum) if float(minimum) == float(maximum) else None
                )
                experience_requirement = experience_observer_facts[0].evidence
                experience_status = "observed_bounded_text"

    remote = detail.get("remote")
    workplace_type = _text(metadata.get("workplace_type")).casefold()
    structured_work_model = (
        "remote" if remote is True or workplace_type == "remote" else "unknown"
    )
    bounded_work_model = composed.work_model if composed is not None else "unknown"
    observer_work_model, observer_work_model_conflict = _single_fact_scalar(
        tuple(facts_by_field.get("work_model", ()))
    )
    if bounded_work_model == "unknown" and isinstance(observer_work_model, str):
        bounded_work_model = observer_work_model
        bounded_work_model_source = "bronze_visible_text_observer"
    else:
        bounded_work_model_source = "bronze_requirement_text"

    conflicts = set(composed.conflicted_fields if composed is not None else ())
    if observer_work_model_conflict:
        conflicts.add("work_model")
    if (
        structured_work_model != "unknown"
        and bounded_work_model != "unknown"
        and structured_work_model != bounded_work_model
    ):
        conflicts.add("work_model")
        work_model = "unknown"
        work_model_status = "conflict"
        work_model_source = "bronze_structured+bronze_bounded_text"
    elif "work_model" in conflicts:
        work_model = "unknown"
        work_model_status = "conflict"
        work_model_source = "bronze_bounded_text"
    elif structured_work_model != "unknown":
        work_model = structured_work_model
        work_model_status = "observed_structured"
        work_model_source = "bronze_structured"
    elif bounded_work_model != "unknown":
        work_model = bounded_work_model
        work_model_status = "observed_bounded_text"
        work_model_source = bounded_work_model_source
    else:
        work_model = "unknown"
        work_model_status = _missing_status(
            detail,
            structured_signal=remote is not None or bool(workplace_type),
        )
        work_model_source = None

    if assessment is not None and assessment.employment_type != "unknown":
        employment_type = assessment.employment_type
        employment_status = "observed_bounded_text"
    else:
        employment_type = "unknown"
        employment_status = _missing_status(
            detail,
            structured_signal=bool(structured_employment),
        )

    if assessment is not None and assessment.required_languages:
        languages = list(assessment.required_languages)
        language_evidence = _reference_payloads(composed, "required_languages")
    elif supplemental_assessment is not None and supplemental_assessment.required_languages:
        languages = list(supplemental_assessment.required_languages)
        language_evidence = _reference_payloads(
            supplemental_composed, "required_languages"
        )
    else:
        languages = []
        language_evidence = []

    weekly_min = assessment.weekly_hours_min if assessment is not None else None
    weekly_max = assessment.weekly_hours_max if assessment is not None else None
    weekly_evidence = _reference_payloads(composed, "weekly_hours")
    weekly_observer_facts = tuple(facts_by_field.get("weekly_hours", ()))
    observer_weekly, observer_weekly_conflict = _single_fact_mapping(
        weekly_observer_facts
    )
    if weekly_min is None and weekly_max is None and observer_weekly is not None:
        minimum = observer_weekly.get("minimum")
        maximum = observer_weekly.get("maximum")
        if isinstance(minimum, (int, float)) and isinstance(maximum, (int, float)):
            weekly_min = float(minimum)
            weekly_max = float(maximum)
            weekly_evidence = _fact_payloads(weekly_observer_facts)
    if observer_weekly_conflict:
        conflicts.add("weekly_hours")

    requirements_seniority = (
        assessment.requirements_seniority if assessment is not None else "unknown"
    )
    title_seniority = assessment.title_seniority if assessment is not None else "unknown"
    posting_language = infer_posting_language(supplemental_text)

    language_status = "observed_bounded_text" if languages else _missing_status(detail)
    weekly_status = (
        "observed_bounded_text"
        if weekly_min is not None or weekly_max is not None
        else _missing_status(detail)
    )
    seniority_status = (
        "observed_bounded_text"
        if requirements_seniority != "unknown"
        else _missing_status(detail)
    )

    compensation_facts = tuple(facts_by_field.get("compensation", ()))
    compensation, compensation_conflict = _single_fact_mapping(compensation_facts)
    if compensation_conflict:
        compensation_status = "conflict"
        compensation = None
    elif compensation is not None:
        compensation_status = "observed_bounded_text"
    else:
        compensation_status = _missing_status(detail)

    collective_facts = tuple(facts_by_field.get("collective_agreement_context", ()))
    collective_value, collective_conflict = _single_fact_scalar(collective_facts)
    collective_agreement = collective_value is True and not collective_conflict
    collective_status = (
        "conflict"
        if collective_conflict
        else "observed_bounded_text"
        if collective_agreement
        else _missing_status(detail)
    )

    fields: dict[str, object] = {
        "employment_type": _field(
            "conflict" if "employment_type" in conflicts else employment_status,
            value=("unknown" if "employment_type" in conflicts else employment_type),
            source_employment_types=structured_employment,
            evidence=_reference_payloads(composed, "employment_type"),
        ),
        "required_languages": _field(
            language_status,
            values=languages,
            evidence=language_evidence,
        ),
        "weekly_hours": _field(
            "conflict" if "weekly_hours" in conflicts else weekly_status,
            minimum=None if "weekly_hours" in conflicts else weekly_min,
            maximum=None if "weekly_hours" in conflicts else weekly_max,
            evidence=weekly_evidence,
        ),
        "work_model": _field(
            work_model_status,
            value=work_model,
            evidence_source=work_model_source,
            evidence=(
                _reference_payloads(composed, "work_model")
                + _semantic_reference_payloads(composed, "remote")
                + _fact_payloads(tuple(facts_by_field.get("work_model", ())))
            ),
        ),
        "requirements_seniority": _field(
            "conflict" if "requirements_seniority" in conflicts else seniority_status,
            value=("unknown" if "requirements_seniority" in conflicts else requirements_seniority),
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
        and str(value.get("status") or "")
        in {"source_absent", "extractor_gap", "conflict", "origin_unavailable"}
    ]

    return {
        "schema": SILVER_REQUIREMENT_EVIDENCE_SCHEMA,
        "source_evidence_schema": source_evidence_schema,
        "parser_family": parser_family,
        "methods": methods,
        "source_url": source_url or None,
        "description_source": detail.get("description_source"),
        "requirement_text_source": requirement_text_source,
        "structured_jobposting_found": detail.get("structured_jobposting_found") is True,
        "fields": fields,
        "display_context": {
            "employment_scope": employment_scope,
            "employment_scope_status": (
                "observed_structured"
                if employment_scope != "unknown"
                else _missing_status(detail, structured_signal=bool(structured_employment))
            ),
            "structured_work_hours": structured_work_hours,
            "structured_work_hours_status": (
                "observed_structured" if structured_work_hours else _missing_status(detail)
            ),
            "experience_requirement": experience_requirement,
            "experience_months": experience_months,
            "experience_min_months": experience_min_months,
            "experience_max_months": experience_max_months,
            "experience_requirement_status": experience_status,
            "experience_evidence": _fact_payloads(experience_observer_facts),
            "compensation": dict(compensation) if compensation is not None else None,
            "compensation_status": compensation_status,
            "compensation_evidence": _fact_payloads(compensation_facts),
            "collective_agreement": collective_agreement,
            "collective_agreement_status": collective_status,
            "collective_agreement_evidence": _fact_payloads(collective_facts),
            "posting_language": posting_language,
            "posting_language_basis": (
                "bounded_visible_vacancy_text" if posting_language != "unknown" else "unknown"
            ),
            "title_seniority_signal": title_seniority,
            "title_seniority_basis": (
                "job_title" if title_seniority != "unknown" else "unknown"
            ),
            "observer_facts": _fact_payloads(observed_facts),
            "observer_authority": False,
            "hard_filter_authority": False,
            "capability_fit_authority": False,
        },
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
            silver_job_id, raw_job_id, evidence_schema, source_evidence_schema,
            parser_family, evidence_hash, evidence_payload
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
