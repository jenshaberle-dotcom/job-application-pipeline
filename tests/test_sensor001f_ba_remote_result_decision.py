from __future__ import annotations

from src.search_intelligence.sensor001f_ba_remote_result_decision import build_sensor001f_result_decision


def test_blocks_decision_when_sensor001e_failed_before_sample() -> None:
    report = build_sensor001f_result_decision(
        {
            "overall_status": "execution_failed_before_sample",
            "database_error": {"type": "UnboundLocalError", "message": "psycopg scope bug"},
        }
    ).as_dict()

    assert report["overall_status"] == "decision_blocked_by_sensor001e_execution_failure"
    assert report["recommended_decision"] == "repair_sensor001e_and_rerun_before_decision"
    assert report["safety_boundary"]["database_writes"] is False
    assert report["safety_boundary"]["external_requests"] is False
    assert "total_loaded_by_term" in report["missing_metrics"]


def test_blocks_decision_when_approval_only_report_has_no_sample() -> None:
    report = build_sensor001f_result_decision({"overall_status": "approval_required"}).as_dict()

    assert report["overall_status"] == "decision_blocked_until_sensor001e_execution"
    assert report["recommended_decision"] == "do_not_decide_before_bounded_sample_result"


def test_recommends_controlled_activation_only_from_complete_positive_metrics() -> None:
    report = build_sensor001f_result_decision(
        {
            "overall_status": "sample_executed",
            "metrics": {
                "total_loaded_by_term": {"Data Engineer": 10, "Analytics Engineer": 8},
                "inserted_count_by_term": {"Data Engineer": 7, "Analytics Engineer": 6},
                "duplicate_count_by_term": {"Data Engineer": 3, "Analytics Engineer": 2},
                "distinct_company_count": 9,
                "new_company_count": 5,
                "known_company_overlap_count": 1,
                "remote_signal_count": 7,
                "local_or_hannover_overlap_count": 2,
                "profile_relevant_title_count": 12,
                "irrelevant_title_count": 1,
                "error_count": 0,
            },
        }
    ).as_dict()

    assert report["overall_status"] == "decision_ready"
    assert report["recommended_decision"] == "activate_controlled_profile"
    assert report["missing_metrics"] == ()


def test_recommends_repeat_when_executed_sample_has_errors() -> None:
    report = build_sensor001f_result_decision(
        {
            "overall_status": "sample_executed_with_errors",
            "metrics": {
                "total_loaded_by_term": {"Data Engineer": 0},
                "inserted_count_by_term": {"Data Engineer": 0},
                "duplicate_count_by_term": {"Data Engineer": 0},
                "distinct_company_count": 0,
                "new_company_count": 0,
                "known_company_overlap_count": 0,
                "remote_signal_count": 0,
                "local_or_hannover_overlap_count": 0,
                "profile_relevant_title_count": 0,
                "irrelevant_title_count": 0,
                "error_count": 1,
            },
        }
    ).as_dict()

    assert report["overall_status"] == "decision_requires_sample_repair"
    assert report["recommended_decision"] == "repeat_bounded_sample_with_repaired_terms"
