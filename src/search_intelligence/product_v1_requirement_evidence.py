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

from dataclasses import dataclass, replace
import re
from typing import Any

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
_WEAK_TRAINEE_SHELL_VALUES = frozenset({"trainee", "traineeprogramm", "traineeprogram"})
_PARTIAL_MOBILE_WORK_RE = re.compile(
    r"\b(?:anteilig(?:e|er|es|en)?\s+)?mobile(?:s|r|n|m)?\s+"
    r"arbeit(?:en)?(?:\s+ist)?\s+(?:möglich|possible)\b",
    re.IGNORECASE,
)


def _canonical_work_model(value: object) -> str:
    text = " ".join(str(value or "").strip().casefold().split())
    if not text:
        return "unknown"
    if "hybrid" in text or _PARTIAL_MOBILE_WORK_RE.search(text):
        return "hybrid"
    if any(
        marker in text
        for marker in (
            "remote",
            "telecommute",
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


def _reject_weak_trainee_shell_signal(
    assessment: ProductV1AssessmentEvidence,
    *,
    title: str,
) -> ProductV1AssessmentEvidence:
    """Do not let unrelated navigation/benefit text turn a vacancy into a trainee job.

    A plain ``Trainee``/``Traineeprogramm`` token is common in employer career-site
    chrome. When the actual vacancy title is not a trainee role and every observed
    employment reference is only that weak token, fail closed to ``unknown``.
    Strong contract wording and real trainee titles remain untouched.
    """

    if assessment.employment_type != "trainee" or "trainee" in title.casefold():
        return assessment
    employment_refs = tuple(
        reference
        for reference in assessment.references
        if reference.field == "employment_type"
    )
    if not employment_refs:
        return assessment
    observed = {
        "".join(str(reference.observed_value or "").casefold().split())
        for reference in employment_refs
    }
    if not observed or not observed.issubset(_WEAK_TRAINEE_SHELL_VALUES):
        return assessment
    return replace(
        assessment,
        employment_type="unknown",
        references=tuple(
            reference
            for reference in assessment.references
            if reference.field != "employment_type"
        ),
    )


def _partial_mobile_work_reference(
    *,
    text: str,
    source_url: str,
) -> SemanticEvidenceReference | None:
    match = _PARTIAL_MOBILE_WORK_RE.search(text)
    if match is None:
        return None
    evidence = match.group(0)
    return SemanticEvidenceReference(
        field="remote",
        source_url=source_url,
        evidence=evidence,
        value=evidence,
        span_start=match.start(),
        span_end=match.end(),
    )


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

    assessment = _reject_weak_trainee_shell_signal(
        extract_product_v1_assessment_evidence(
            description=text,
            title=title,
            source_url=source_url,
        ),
        title=title,
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
    semantic_references = list(references)
    partial_mobile = _partial_mobile_work_reference(text=text, source_url=source_url)
    if partial_mobile is not None:
        semantic_work_model = "hybrid"
        if not any(
            reference.field == partial_mobile.field
            and reference.span_start == partial_mobile.span_start
            and reference.span_end == partial_mobile.span_end
            for reference in semantic_references
        ):
            semantic_references.append(partial_mobile)
    else:
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
        semantic_references=tuple(semantic_references),
        jsonld_jobposting_count=len(extract_job_postings(html)),
        conflicted_fields=tuple(sorted(conflicts)),
    )


__all__ = [
    "ProductV1RequirementEvidence",
    "REQUIREMENT_EVIDENCE_SCHEMA",
    "extract_product_v1_requirement_evidence",
]
