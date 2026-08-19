from scripts.run_product_v1_control_center import _merge_observed_opportunities
from src.search_intelligence.product_v1_service import build_product_v1_payload


def test_observed_opportunity_projection_does_not_change_canonical_job_truth() -> None:
    base = build_product_v1_payload(
        wave_states=[],
        job_readiness=[],
        top_jobs=[],
        ranking_policy={"status": "approved"},
        application_readiness=[],
        application_sources=[],
        migration_ready=True,
        hard_filter_policy={"status": "approved"},
    )
    projected = _merge_observed_opportunities(
        base,
        [
            {
                "opportunity_id": 123,
                "company_name": "Example GmbH",
                "title": "ML Reliability Engineer",
                "location": "Deutschland (Remote)",
                "opportunity_stage": "vacancy_verification_pending",
                "ranking_authority": False,
                "application_authority": False,
            }
        ],
    )

    assert projected["summary"]["observed_opportunity_count"] == 1
    assert projected["summary"]["pending_market_opportunity_count"] == 1
    assert projected["summary"]["current_active_job_count"] == 0
    assert projected["summary"]["rankable_job_count"] == 0
    assert projected["top_jobs"] == []
    assert projected["observed_opportunities"][0]["title"] == "ML Reliability Engineer"
    assert projected["boundaries"]["observed_opportunity_is_not_ranking_authority"] is True


def test_service_can_carry_observed_opportunities_without_promoting_them() -> None:
    payload = build_product_v1_payload(
        wave_states=[],
        job_readiness=[],
        top_jobs=[],
        ranking_policy={"status": "approved"},
        application_readiness=[],
        application_sources=[],
        migration_ready=True,
        hard_filter_policy={"status": "approved"},
        observed_opportunities=[
            {
                "opportunity_id": 1,
                "opportunity_stage": "vacancy_verified_active",
                "ranking_authority": False,
                "application_authority": False,
            }
        ],
    )
    assert payload["summary"]["observed_opportunity_count"] == 1
    assert payload["summary"]["verified_market_opportunity_count"] == 1
    assert payload["summary"]["current_active_job_count"] == 0
    assert payload["top_jobs"] == []
