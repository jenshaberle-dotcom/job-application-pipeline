from __future__ import annotations

import pytest

from scripts.run_freeze2_s0_source_truth_baseline import build_summary


def _connector(*, database_writes: object = False) -> dict[str, object]:
    return {
        "boundary": {
            "database_writes": database_writes,
            "candidate_url_writes": False,
            "connector_materialization": False,
            "connector_registration": False,
            "source_activation": False,
            "bronze_write": False,
            "silver_write": False,
            "product_write": False,
            "application_action": False,
            "provider_requests": 0,
            "llm_requests": 0,
            "tavily_requests": 0,
        },
        "comparison": {
            "v6_summary": {
                "candidate_count": 12,
                "recipe_ready_count": 7,
                "recipe_ready_rate": 0.5833,
                "first_failure_counts": {
                    "origin": 2,
                    "inventory": 2,
                    "detail": 1,
                },
            },
            "public_feed_attempted_count": 2,
            "public_feed_promoted_count": 1,
        },
    }


def _metadata() -> dict[str, object]:
    return {
        "candidate_count": 4,
        "operator_candidate_count": 4,
        "reachable_count": 4,
        "origin_unavailable_count": 0,
        "reachable_without_extractor_gap_ratio": 0.75,
        "rows_with_extractor_gap": 1,
        "rows_with_silver_to_operator_projection_loss": 0,
        "violating_row_count": 0,
        "field_status_counts": {
            "employment_type": {
                "observed_structured": 3,
                "source_absent": 1,
            }
        },
        "context_observed_counts": {"posting_language": 4},
        "extractor_gap_source_family_counts": {
            "generic_origin": {"job_skills": 1}
        },
        "coverage_gate_pass": False,
        "rows": [
            {"source_family": "generic_origin"},
            {"source_family": "generic_origin"},
            {"source_family": "personio"},
            {"source_family": "hdi"},
        ],
        "boundaries": {
            "database_writes": 0,
            "provider_calls": 0,
            "candidate_fact_reads": 0,
            "ranking_authority": 0,
            "top5_authority": 0,
            "application_authority": 0,
            "raw_html_persisted": 0,
        },
    }


def _skills() -> dict[str, object]:
    return {
        "candidate_count": 4,
        "audited_count": 4,
        "origin_unavailable_count": 0,
        "blocked_count": 0,
        "requirement_section_extracted_job_count": 3,
        "skill_observed_job_count": 2,
        "skill_recall_risk_count": 1,
        "external_observer_enabled": False,
        "by_source_name": {
            "generic_origin:a": {"job_count": 2, "skill_observed_job_count": 1},
            "personio:b": {"job_count": 1, "skill_observed_job_count": 1},
        },
        "boundaries": {
            "database_writes": 0,
            "bronze_writes": 0,
            "silver_writes": 0,
            "candidate_fact_reads": 0,
            "fit_authority": 0,
            "ranking_authority": 0,
            "top5_authority": 0,
            "application_authority": 0,
            "external_observer_product_authority": 0,
            "raw_html_persisted": 0,
        },
    }


def _overview() -> dict[str, object]:
    return {
        "summary": {
            "source_count": 5,
            "employer_origin_count": 4,
            "employer_origin_active_count": 3,
            "registered_count": 4,
            "active_count": 4,
        },
        "sources": [
            {
                "source_name": "generic_origin:a",
                "source_role": "employer_origin",
                "activation": {"active": True},
            },
            {
                "source_name": "generic_origin:b",
                "source_role": "employer_origin",
                "activation": {"active": True},
            },
            {
                "source_name": "personio:c",
                "source_role": "employer_origin",
                "activation": {"active": True},
            },
            {
                "source_name": "successfactors:d",
                "source_role": "employer_origin",
                "activation": {"active": False},
            },
            {
                "source_name": "stepstone",
                "source_role": "sensor",
                "activation": {"active": True},
            },
        ],
    }


def test_build_summary_keeps_diagnostic_recipe_ready_separate_from_product_coverage() -> None:
    report = build_summary(
        overview=_overview(),
        connector=_connector(),
        metadata=_metadata(),
        skills=_skills(),
    )

    assert report["schema"] == "job_application_pipeline.freeze2_s0_source_truth_baseline.v1"
    assert report["mode"] == "read_only"
    assert report["authority"]["diagnostic_recipe_ready_is_product_coverage"] is False
    assert report["authority"]["historical_36_of_65_is_current_authority"] is False

    connector = report["connector_builder_diagnostic"]
    assert connector["candidate_count"] == 12
    assert connector["diagnostic_recipe_ready_count"] == 7
    assert connector["first_failure_counts"] == {
        "origin": 2,
        "inventory": 2,
        "detail": 1,
    }

    concentration = report["source_overview"]["family_concentration"]
    assert concentration["active_employer_origin_by_family"] == {
        "generic_origin": 2,
        "personio": 1,
    }
    assert concentration["product_review_jobs_by_family"] == {
        "generic_origin": 2,
        "hdi": 1,
        "personio": 1,
    }


def test_build_summary_preserves_metadata_and_skill_quality_pressure() -> None:
    report = build_summary(
        overview=_overview(),
        connector=_connector(),
        metadata=_metadata(),
        skills=_skills(),
    )

    metadata = report["metadata_integrity"]
    assert metadata["reachable_count"] == 4
    assert metadata["rows_with_extractor_gap"] == 1
    assert metadata["rows_with_projection_loss"] == 0
    assert metadata["coverage_gate_pass"] is False

    skills = report["skill_requirement_reliability"]
    assert skills["requirement_section_extracted_job_count"] == 3
    assert skills["skill_observed_job_count"] == 2
    assert skills["skill_recall_risk_count"] == 1

    assert report["boundaries"] == {
        "database_writes": 0,
        "source_activation": 0,
        "connector_registration": 0,
        "bronze_writes": 0,
        "silver_writes": 0,
        "product_writes": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "fit_authority": 0,
        "ranking_authority": 0,
        "application_authority": 0,
    }


def test_build_summary_fails_closed_if_child_audit_reports_write_effect() -> None:
    with pytest.raises(RuntimeError, match="read-only boundary violated"):
        build_summary(
            overview=_overview(),
            connector=_connector(database_writes=True),
            metadata=_metadata(),
            skills=_skills(),
        )
