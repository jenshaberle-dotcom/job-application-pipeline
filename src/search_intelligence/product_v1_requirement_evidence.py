"""Generic structured/contextual requirement evidence for Product V1 F4A.

This module composes the existing flat Product V1 assessment extractor with the
existing deterministic detail-semantics layer. It adds only job-side evidence:
structured/contextual skills and a conservative work-model resolution. Candidate
Facts, capability-fit decisions, ranking, Top-5 and application authority are out
of scope.

Important authority rules:
- requirements seniority is never inferred from the title or generic seniority
  semantics;
- a contextual work-model signal may fill a flat ``unknown`` only when it maps
  unambiguously to a supported canonical value;
- contradictory flat/contextual work-model evidence resolves to ``unknown``;
- skills remain evidence only and never become candidate capability truth;
- every semantic value remains bound to a visible-text evidence reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.search_intelligence.detail_semantics_deterministic import (
    SemanticEvidenceReference,
    deterministic_detail_semantics,
    extract_job_postings,
)
from src.search_intelligence.product_v1_assessment_evidence import (
    ProductV1AssessmentEvidence,
    extract_product_v1_assessment_evidence,
)


REQUIREMENT_EVIDENCE_SCHEMA = "product_v1.requirement_evidence.v1"
_REQUESTED_SEMANTIC_FIELDS = ("skills", "remote")


def _canonical_work_model(value: object) -> str:
    text = " ".join(str(value or "").strip().casefold().split())
    if not text:
        return "unknown"
    if "hybrid" in text:
        return "hybrid"
    if any(
        marker in text
        for marker in (
            "remote",
            "homeoffice",
            "home office",
            "mobiles arbeiten",
            "mobile work",
            "work from home",
            "telearbeit",
        )
    ):
        return "remote"
    if text in {"onsite", "on-site", "on site", "vor ort"}:
        return "onsite"
    return "unknown"


def _reference_payload(reference: SemanticEvidenceReference) -> dict[str, object]:
    return {
        "field": reference.field,
        "source_url": reference.source_url,
        "evidence": reference.evidence,
        "value": reference.value,
        "span_start": reference.span_start,
        "span_end": reference.span_end,
    }


@dataclass(frozen=True)
class ProductV1RequirementEvidence:
    """One fail-closed composition of flat and structured vacancy evidence."""

    assessment: ProductV1AssessmentEvidence
    work_model: str
    work_model_resolution: str
    semantic_work_model: str
    job_skills: tuple[str, ...]
    semantic_references: tuple[SemanticEvidenceReference, ...]
    jsonld_jobposting_count: int
    conflicted_fields: tuple[str, ...]

    @property
    def unresolved_fields(self) -> tuple[str, ...]:
        unresolved = set(self.assessment.unresolved_fields)
        if self.work_model != "unknown":
            unresolved.discard("work_model")
        else:
            unresolved.add("work_model")
        return tuple(sorted(unresolved))

    def assessment_patch(self) -> dict[str, Any]:
        patch = dict(self.assessment.assessment_patch())
        patch["work_model"] = self.work_model
        return patch

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema": REQUIREMENT_EVIDENCE_SCHEMA,
            "assessment": self.assessment.canonical_payload(),
            "resolved_assessment_patch": self.assessment_patch(),
            "work_model_resolution": self.work_model_resolution,
            "semantic_work_model": self.semantic_work_model,
            "job_skills": list(self.job_skills),
            "semantic_references": [
                _reference_payload(reference) for reference in self.semantic_references
            ],
            "jsonld_jobposting_count": self.jsonld_jobposting_count,
            "conflicted_fields": list(self.conflicted_fields),
            "unresolved_fields": list(self.unresolved_fields),
            "authority": {
                "job_source_evidence_only": True,
                "candidate_fact_authority": False,
                "capability_fit_authority": False,
                "requirements_seniority_from_title": False,
                "hard_filter_authority": False,
                "ranking_authority": False,
                "top5_authority": False,
                "application_authority": False,
            },
        }


def extract_product_v1_requirement_evidence(
    *,
    html: str,
    text: str,
    title: str,
    page_title: str,
    source_url: str,
    target_location: str = "",
) -> ProductV1RequirementEvidence:
    """Compose current authoritative detail evidence without adding fit authority."""

    assessment = extract_product_v1_assessment_evidence(
        description=text,
        title=title,
        source_url=source_url,
    )
    semantics, references = deterministic_detail_semantics(
        html=html,
        text=text,
        page_title=page_title,
        detail_url=source_url,
        target_location=target_location,
        requested_fields=_REQUESTED_SEMANTIC_FIELDS,
    )

    raw_skills = semantics.get("skills")
    skills = tuple(str(item) for item in raw_skills) if isinstance(raw_skills, tuple) else ()
    semantic_work_model = _canonical_work_model(semantics.get("remote"))
    flat_work_model = assessment.work_model
    conflicts = set(assessment.conflicted_fields)

    if flat_work_model == "unknown" and semantic_work_model != "unknown":
        work_model = semantic_work_model
        resolution = "contextual_fill"
    elif (
        flat_work_model != "unknown"
        and semantic_work_model != "unknown"
        and flat_work_model != semantic_work_model
    ):
        work_model = "unknown"
        resolution = "conflict_unknown"
        conflicts.add("work_model")
    elif flat_work_model != "unknown":
        work_model = flat_work_model
        resolution = "flat_observed"
    else:
        work_model = "unknown"
        resolution = "unknown"

    return ProductV1RequirementEvidence(
        assessment=assessment,
        work_model=work_model,
        work_model_resolution=resolution,
        semantic_work_model=semantic_work_model,
        job_skills=skills,
        semantic_references=tuple(references),
        jsonld_jobposting_count=len(extract_job_postings(html)),
        conflicted_fields=tuple(sorted(conflicts)),
    )


__all__ = [
    "ProductV1RequirementEvidence",
    "REQUIREMENT_EVIDENCE_SCHEMA",
    "extract_product_v1_requirement_evidence",
]
