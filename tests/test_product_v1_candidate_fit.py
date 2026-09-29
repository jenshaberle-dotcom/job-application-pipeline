from src.search_intelligence.product_v1_candidate_fit import (
    CANDIDATE_FIT_SCOPE,
    build_candidate_fit,
)


def _sidecar(status: str = "observed_structured", skills=None):
    return {
        "fields": {
            "job_skills": {
                "status": status,
                "values": skills if skills is not None else ["Python", "SQL", "Terraform"],
            }
        }
    }


def test_candidate_fit_is_exact_job_skill_coverage_against_cv_capabilities() -> None:
    result = build_candidate_fit(
        sidecar_payload=_sidecar(),
        candidate_capability_tags={" python ", "sql", "kubernetes"},
    )

    assert result.authority_status == "authoritative"
    assert result.scope == CANDIDATE_FIT_SCOPE
    assert result.observed_job_skill_count == 3
    assert result.exact_candidate_skill_match_count == 2
    assert result.exact_candidate_skill_unmatched_count == 1
    assert result.exact_candidate_skill_coverage == 0.6667
    assert result.score == 66.7


def test_candidate_fit_does_not_invent_score_without_job_skill_evidence() -> None:
    missing = build_candidate_fit(
        sidecar_payload=_sidecar(status="origin_unavailable", skills=[]),
        candidate_capability_tags={"python", "sql"},
    )

    assert missing.authority_status == "insufficient_evidence"
    assert missing.score is None
    assert missing.exact_candidate_skill_coverage is None


def test_candidate_fit_ignores_non_skill_constraints_by_construction() -> None:
    base = build_candidate_fit(
        sidecar_payload=_sidecar(skills=["Python", "Kubernetes"]),
        candidate_capability_tags={"python"},
    )
    same = build_candidate_fit(
        sidecar_payload={
            **_sidecar(skills=["Python", "Kubernetes"]),
            "geography": "outside",
            "seniority": "principal",
            "weekly_hours": 10,
        },
        candidate_capability_tags={"python"},
    )

    assert base.score == same.score == 50.0
    assert base.scope == same.scope == "job_skills_vs_cv_skills"


def test_candidate_fit_deduplicates_and_normalizes_job_skills() -> None:
    result = build_candidate_fit(
        sidecar_payload=_sidecar(
            skills=[" Python ", "python", "CI/CD", "CI/CD", "Machine   Learning"]
        ),
        candidate_capability_tags={"python", "ci/cd", "machine learning"},
    )

    assert result.observed_job_skill_count == 3
    assert result.exact_candidate_skill_match_count == 3
    assert result.score == 100.0
