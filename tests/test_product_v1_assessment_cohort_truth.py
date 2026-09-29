import json
import sys

import pytest

from scripts import run_product_v1_assessment_cohort as cohort


def job(identity, **changes):
    return {
        "silver_job_id": identity,
        "source_name": "generic_origin:example",
        "lifecycle_status": "active_confirmed",
        "profile_fit_coverage_status": "profile_fit_complete",
        "profile_fit_decision": "passed",
        "product_readiness_status": "rankable",
        "hard_filter_status": "passed",
        "affinity_authority_status": "authoritative",
        **changes,
    }


def truth(monkeypatch, jobs, top, selected_ids):
    calls = []

    def load(**kwargs):
        calls.append(kwargs)
        return {"job_readiness": jobs, "top_jobs": top}

    monkeypatch.setattr(cohort, "load_product_v1_payload", load)
    result = cohort._current_product_truth(selected_ids=selected_ids)
    assert len(calls) == 1
    return result


def test_unselected_sensor_and_stale_jobs_cannot_fill_cohort(monkeypatch):
    jobs = [job(i) for i in range(1, 11)]
    jobs += [job(11, source_name="stepstone:example")]
    jobs += [job(12, lifecycle_status="stale_needs_refresh")]
    result = truth(monkeypatch, jobs, [], {1, 2, 11, 12})
    assert result["profile_fit_complete_count"] == 2
    assert result["profile_fit_passed_count"] == 2
    assert result["rankable_job_count"] == 2


def test_failed_fit_counts_as_evaluated_but_never_as_passed(monkeypatch):
    jobs = [job(i) for i in range(1, 6)] + [
        job(i, profile_fit_decision="failed", product_readiness_status="blocked")
        for i in range(6, 11)
    ]
    top = [dict(row, product_rank=i) for i, row in enumerate(jobs[:5], 1)]
    result = truth(monkeypatch, jobs, top, set(range(1, 11)))
    assert result["profile_fit_complete_count"] == 10
    assert result["profile_fit_passed_count"] == 5
    assert result["rankable_job_count"] == 5
    assert result["top5_authority_violations"] == []


def test_duplicate_cohort_rows_fail_closed(monkeypatch):
    with pytest.raises(cohort.ProductAssessmentCohortStop, match="duplicate selected"):
        truth(monkeypatch, [job(1), job(1)], [], {1})


@pytest.mark.parametrize("defect", ["duplicate_id", "duplicate_rank", "hard_filter", "sensor"])
def test_five_top_rows_are_insufficient_without_valid_authority(monkeypatch, defect):
    top = [job(i, product_rank=i) for i in range(1, 6)]
    if defect == "duplicate_id":
        top[-1]["silver_job_id"] = 1
    elif defect == "duplicate_rank":
        top[-1]["product_rank"] = 1
    elif defect == "hard_filter":
        top[-1]["hard_filter_status"] = "failed"
    else:
        top[-1]["source_name"] = "stepstone:example"
    result = truth(monkeypatch, [], top, set())
    assert result["top5_authority_violations"]


def test_plan_authority_failure_is_reported_and_stops_before_apply(monkeypatch, tmp_path):
    output = tmp_path / "plan.json"
    monkeypatch.setattr(sys, "argv", ["cohort", "--output", str(output)])
    monkeypatch.setattr(
        cohort,
        "_selection",
        lambda cap, **_kwargs: ([job(i) for i in range(1, 11)], {}),
    )
    monkeypatch.setattr(cohort, "_run_existing_authorities", lambda **kwargs: 7)
    monkeypatch.setattr(cohort, "load_product_v1_payload", lambda **kwargs: {
        "job_readiness": [job(i) for i in range(1, 11)],
        "top_jobs": [job(i, product_rank=i) for i in range(1, 6)],
    })
    with pytest.raises(SystemExit, match="AUTHORITY_FAILED:7"):
        cohort.main()
    report = json.loads(output.read_text())
    assert report["authority_pipeline_exit_code"] == 7
    assert report["target_met"] is False
