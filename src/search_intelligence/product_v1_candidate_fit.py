"""Deterministic Candidate Fit from job skills versus approved CV capability facts.

Candidate Fit answers one narrow product question:

    How much of the job's observed skill requirement set is evidenced by the
    candidate's approved CV-derived capability facts?

It is intentionally independent from Affinity, geography, work model, seniority,
hard requirements, ranking and Top-5. Those remain separate authorities/gates.

The score uses the same exact normalized overlap already proven by the F4B
operator-gate packet:

    exact matched candidate capability tags / observed job skills * 100

No weighting is invented when the vacancy does not explicitly distinguish
must-have from optional skills.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Sequence


CANDIDATE_FIT_AUTHORITY = "candidate-facts-exact-skill-coverage-v1"
CANDIDATE_FIT_SCOPE = "job_skills_vs_cv_skills"

_NON_AUTHORITATIVE_EVIDENCE = frozenset(
    {
        "",
        "missing",
        "invalid",
        "unknown",
        "origin_unavailable",
        "extractor_gap",
        "unavailable",
    }
)


def normalize_skill_label(value: object) -> str:
    text = str(value or "").strip().casefold()
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    return text


def observed_job_skills(sidecar_payload: object) -> tuple[str, tuple[str, ...]]:
    if not isinstance(sidecar_payload, Mapping):
        return "missing", ()
    fields = sidecar_payload.get("fields")
    if not isinstance(fields, Mapping):
        return "invalid", ()
    skills = fields.get("job_skills")
    if not isinstance(skills, Mapping):
        return "missing", ()
    status = str(skills.get("status") or "missing").strip()
    values = skills.get("values")
    if not isinstance(values, list):
        return status, ()
    normalized = tuple(
        sorted(
            {
                normalize_skill_label(value)
                for value in values
                if normalize_skill_label(value)
            }
        )
    )
    return status, normalized


@dataclass(frozen=True)
class CandidateFitResult:
    score: float | None
    authority_status: str
    job_skill_evidence_status: str
    observed_job_skill_count: int
    exact_candidate_skill_match_count: int
    exact_candidate_skill_unmatched_count: int
    exact_candidate_skill_coverage: float | None
    overlap_class: str
    scope: str = CANDIDATE_FIT_SCOPE
    authority: str = CANDIDATE_FIT_AUTHORITY

    def payload(self) -> dict[str, object]:
        return {
            "candidate_fit_score": self.score,
            "candidate_fit_authority": self.authority,
            "candidate_fit_authority_status": self.authority_status,
            "candidate_fit_scope": self.scope,
            "candidate_fit_job_skill_evidence_status": self.job_skill_evidence_status,
            "candidate_fit_observed_job_skill_count": self.observed_job_skill_count,
            "candidate_fit_exact_match_count": self.exact_candidate_skill_match_count,
            "candidate_fit_unmatched_count": self.exact_candidate_skill_unmatched_count,
            "candidate_fit_exact_coverage": self.exact_candidate_skill_coverage,
            "candidate_fit_overlap_class": self.overlap_class,
        }


def _coverage_bucket(match_count: int, total: int) -> str:
    if total <= 0:
        return "not_observed"
    if match_count == total:
        return "all_observed_skills_exactly_covered"
    if match_count == 0:
        return "no_observed_skill_exactly_covered"
    return "partial_exact_coverage"


def build_candidate_fit(
    *,
    sidecar_payload: object,
    candidate_capability_tags: Sequence[str] | set[str],
) -> CandidateFitResult:
    status, job_skills = observed_job_skills(sidecar_payload)
    candidate_tags = {
        normalize_skill_label(value)
        for value in candidate_capability_tags
        if normalize_skill_label(value)
    }
    matched = sum(skill in candidate_tags for skill in job_skills)
    total = len(job_skills)
    coverage = round(matched / total, 4) if total else None
    score = round(coverage * 100, 1) if coverage is not None else None
    authoritative = (
        total > 0
        and status.strip().casefold() not in _NON_AUTHORITATIVE_EVIDENCE
    )
    return CandidateFitResult(
        score=score if authoritative else None,
        authority_status="authoritative" if authoritative else "insufficient_evidence",
        job_skill_evidence_status=status,
        observed_job_skill_count=total,
        exact_candidate_skill_match_count=matched,
        exact_candidate_skill_unmatched_count=max(0, total - matched),
        exact_candidate_skill_coverage=coverage if authoritative else None,
        overlap_class=_coverage_bucket(matched, total),
    )


__all__ = [
    "CANDIDATE_FIT_AUTHORITY",
    "CANDIDATE_FIT_SCOPE",
    "CandidateFitResult",
    "build_candidate_fit",
    "normalize_skill_label",
    "observed_job_skills",
]
