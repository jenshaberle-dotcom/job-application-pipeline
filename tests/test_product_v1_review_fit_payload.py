from src.search_intelligence.product_v1_service import build_product_v1_payload


def _payload(job: dict[str, object]) -> dict[str, object]:
    return build_product_v1_payload(
        wave_states=[],
        job_readiness=[job],
        top_jobs=[],
        ranking_policy={"status": "approved"},
        application_readiness=[],
        application_sources=[
            {"document_type": "base_cv", "status": "approved"},
            {"document_type": "base_application_letter", "status": "approved"},
        ],
        migration_ready=True,
        hard_filter_policy={"status": "approved"},
    )


def test_unranked_job_keeps_review_preview_separate_from_candidate_fit() -> None:
    payload = _payload(
        {
            "silver_job_id": 1,
            "title": "ML Engineer",
            "city": None,
            "country": "Germany",
            "work_model": "remote",
            "commute_minutes": None,
            "lifecycle_status": "active_confirmed",
            "product_readiness_status": "hard_filter_evidence_required",
            "overall_quality_score": None,
        }
    )
    job = payload["job_readiness"][0]

    assert isinstance(job["review_fit_score"], float)
    assert job["candidate_fit_score"] is None
    assert job["candidate_fit_authority_status"] == "insufficient_evidence"
    assert job["display_fit_score"] is None
    assert job["display_fit_scope"] is None
    assert job["overall_quality_score"] is None
    assert job["product_overall_quality_score"] is None
    assert job["affinity_score"] is None
    assert job["combined_score"] is None
    assert payload["boundaries"]["review_fit_preview_is_not_ranking_authority"] is True
    assert payload["boundaries"]["candidate_fit_is_job_skills_vs_cv_skills"] is True


def test_authoritative_affinity_does_not_create_candidate_fit() -> None:
    payload = _payload(
        {
            "silver_job_id": 2,
            "title": "Data Engineer",
            "city": "Hannover",
            "country": "Germany",
            "work_model": "remote",
            "commute_minutes": None,
            "lifecycle_status": "active_confirmed",
            "product_readiness_status": "rankable",
            "overall_quality_score": 70.4,
            "affinity_score": 70.4,
            "affinity_authority": "pd-052",
            "affinity_authority_status": "authoritative",
        }
    )
    job = payload["job_readiness"][0]

    assert job["affinity_score"] == 70.4
    assert job["product_overall_quality_score"] == 70.4
    assert job["affinity_authority"] == "pd-052"
    assert job["affinity_authority_status"] == "authoritative"
    assert isinstance(job["review_fit_score"], float)
    assert job["candidate_fit_score"] is None
    assert job["display_fit_score"] is None
    assert job["overall_quality_score"] is None
    assert job["combined_score"] is None
    assert payload["summary"]["affinity_authoritative_count"] == 1
    assert payload["summary"]["candidate_fit_authoritative_count"] == 0
    assert payload["summary"]["combined_score_count"] == 0
    assert payload["boundaries"]["affinity_is_not_candidate_fit"] is True


def test_authoritative_cv_skill_fit_is_the_candidate_fit_display_score() -> None:
    payload = _payload(
        {
            "silver_job_id": 3,
            "title": "ML Platform Engineer",
            "city": "Hannover",
            "country": "Germany",
            "work_model": "hybrid",
            "commute_minutes": 25,
            "lifecycle_status": "active_confirmed",
            "product_readiness_status": "hard_filter_evidence_required",
            "candidate_fit_score": 75.0,
            "candidate_fit_authority": "candidate-facts-exact-skill-coverage-v1",
            "candidate_fit_authority_status": "authoritative",
            "candidate_fit_scope": "job_skills_vs_cv_skills",
            "candidate_fit_observed_job_skill_count": 8,
            "candidate_fit_exact_match_count": 6,
            "candidate_fit_unmatched_count": 2,
            "candidate_fit_exact_coverage": 0.75,
        }
    )
    job = payload["job_readiness"][0]

    assert job["candidate_fit_score"] == 75.0
    assert job["candidate_fit_authority_status"] == "authoritative"
    assert job["candidate_fit_scope"] == "job_skills_vs_cv_skills"
    assert job["display_fit_score"] == 75.0
    assert job["display_fit_scope"] == "candidate_skill_fit"
    assert job["overall_quality_score"] == 75.0
    assert job["affinity_score"] is None
    assert job["combined_score"] is None
    assert payload["summary"]["candidate_fit_authoritative_count"] == 1
