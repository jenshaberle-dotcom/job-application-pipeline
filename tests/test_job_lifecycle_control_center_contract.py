from pathlib import Path

from src.search_intelligence.product_v1_service import build_product_v1_payload


APP = Path("frontend/control-center/src/App.tsx")
REPOSITORY = Path("src/ingestion/job_health_repository.py")


def test_control_center_payload_exposes_lifecycle_health_counts() -> None:
    jobs = [
        {
            "silver_job_id": 1,
            "lifecycle_status": "active_confirmed",
            "product_readiness_status": "rankable",
        },
        {
            "silver_job_id": 2,
            "lifecycle_status": "stale_needs_refresh",
            "product_readiness_status": "activity_evidence_required",
        },
        {
            "silver_job_id": 3,
            "lifecycle_status": "inactive_confirmed",
            "product_readiness_status": "blocked_inactive",
        },
        {
            "silver_job_id": 4,
            "lifecycle_status": "unverifiable",
            "product_readiness_status": "activity_evidence_required",
        },
    ]
    payload = build_product_v1_payload(
        wave_states=[],
        job_readiness=jobs,
        top_jobs=[jobs[0]],
        ranking_policy={"status": "approved"},
        hard_filter_policy={"status": "approved"},
        application_readiness=[],
        application_sources=[],
        migration_ready=True,
    )

    assert payload["summary"]["current_active_job_count"] == 1
    assert payload["summary"]["stale_job_count"] == 1
    assert payload["summary"]["inactive_confirmed_job_count"] == 1
    assert payload["summary"]["unverifiable_job_count"] == 1
    assert payload["summary"]["rankable_job_count"] == 1
    assert len(payload["top_jobs"]) == 1
    assert payload["boundaries"]["historical_job_presence_is_not_current_activity"]


def test_payload_fails_closed_when_old_readiness_rows_lack_lifecycle_truth() -> None:
    legacy_job = {
        "silver_job_id": 9,
        "product_readiness_status": "rankable",
    }
    payload = build_product_v1_payload(
        wave_states=[],
        job_readiness=[legacy_job],
        top_jobs=[legacy_job],
        ranking_policy={"status": "approved"},
        hard_filter_policy={"status": "approved"},
        application_readiness=[
            {
                "silver_job_id": 9,
                "application_readiness_status": "ready_for_generation",
            }
        ],
        application_sources=[],
        migration_ready=True,
    )

    blocker_codes = {item["code"] for item in payload["operator_blockers"]}
    assert "job_lifecycle_health_required" in blocker_codes
    assert payload["summary"]["rankable_job_count"] == 0
    assert payload["summary"]["application_ready_count"] == 0
    assert payload["top_jobs"] == []
    assert payload["application_readiness"] == []


def test_health_repository_revalidates_raw_identity_before_append() -> None:
    source = REPOSITORY.read_text(encoding="utf-8")

    assert "FROM raw_jobs" in source
    assert "FOR SHARE" in source
    assert "raw job source_name drift detected" in source
    assert "raw job external_job_id drift detected" in source
    assert "INSERT INTO job_health_observations" in source


def test_react_control_center_surfaces_job_health_truth() -> None:
    source = APP.read_text(encoding="utf-8")

    assert "lifecycle_status?: string" in source
    assert "last_positive_observed_at?: string | null" in source
    assert "last_health_checked_at?: string | null" in source
    assert "Current active" in source
    assert "Needs refresh" in source
    assert "Lifecycle-gated Top 5" in source
    assert "Historical Silver presence alone never qualifies a vacancy" in source
