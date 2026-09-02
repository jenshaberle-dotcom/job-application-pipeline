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


def test_unranked_job_gets_review_fit_without_product_score_authority() -> None:
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

    assert job["overall_quality_score"] == job["review_fit_score"]
    assert job["product_overall_quality_score"] is None
    assert job["display_fit_scope"] == "review_preview"
    assert payload["boundaries"]["review_fit_preview_is_not_ranking_authority"] is True


def test_authoritative_product_score_wins_display_fit() -> None:
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
        }
    )
    job = payload["job_readiness"][0]

    assert job["overall_quality_score"] == 70.4
    assert job["product_overall_quality_score"] == 70.4
    assert job["display_fit_scope"] == "authoritative_product_score"
