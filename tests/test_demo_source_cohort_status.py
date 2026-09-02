from __future__ import annotations

from scripts.run_demo_source_cohort_status import DEFAULT_OUTPUT, summarize_status


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "silver_job_id": 101,
        "source_name": "personio:eraneos",
        "company_name": "Eraneos Analytics Germany GmbH",
        "title": "Data Engineer (all genders)",
        "city": "Hamburg",
        "country": "Germany",
        "source_url": "https://eraneos.jobs.personio.de/job/101",
        "canonical_source_type": "employer_origin_ats_backed_career_site",
        "lifecycle_status": "active_confirmed",
        "last_positive_observed_at": "2026-09-02T12:00:00+00:00",
        "last_health_checked_at": None,
        "origin_validation_status": None,
        "activity_status": "active",
        "hard_filter_status": "unknown",
        "profile_direction_score": None,
        "data_focus_score": None,
        "reliability_focus_score": None,
        "evidence_quality_score": None,
        "overall_quality_score": None,
        "product_readiness_status": "assessment_required",
    }
    row.update(overrides)
    return row


def test_status_routes_artifact_inside_gitignored_project_runtime_tree() -> None:
    assert DEFAULT_OUTPUT.parts[-3:] == (
        ".runtime",
        "demo",
        "demo_source_cohort_status.json",
    )


def test_current_profile_job_points_to_assessment_materialization() -> None:
    report = summarize_status([_row()], [])

    assert report["summary"]["current_active_count"] == 1
    assert report["summary"]["profile_relevant_current_count"] == 1
    assert report["summary"]["next_gate"] == "product_v1_assessment_materialization"
    assert report["profile_relevant_current_jobs"][0]["role_signal"]["family"] == "data_engineer"
    assert report["boundaries"]["database_writes"] is False


def test_rankable_cohort_job_without_top5_points_to_policy_result() -> None:
    report = summarize_status(
        [
            _row(
                origin_validation_status="validated",
                hard_filter_status="passed",
                profile_direction_score=85.0,
                data_focus_score=80.0,
                reliability_focus_score=60.0,
                evidence_quality_score=90.0,
                overall_quality_score=80.5,
                product_readiness_status="rankable",
            )
        ],
        [],
    )

    assert report["summary"]["next_gate"] == "top5_policy_result"
