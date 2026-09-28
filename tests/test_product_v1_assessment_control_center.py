from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import subprocess

import pytest

from scripts import product_v1_assessment_actions as actions
from scripts import run_product_v1_control_center as server


def _report(*, target_met: bool = True, combined_score: bool = False) -> dict[str, object]:
    return {
        "schema": actions.COHORT_SCHEMA,
        "mode": "apply",
        "targets": {
            "evaluated_jobs": 10,
            "top5_jobs": 5,
            "candidate_cap": 15,
        },
        "selection": {
            "selected_count": 10,
            "enough_candidates": True,
        },
        "authority_pipeline_exit_code": 0,
        "final": {
            "profile_fit_complete_count": 10,
            "profile_fit_passed_count": 6,
            "rankable_job_count": 5,
            "top_job_count": 5 if target_met else 4,
            "selected_readiness_counts": {"rankable": 5},
            "top5_authority_violations": [],
        },
        "target_met": target_met,
        "boundaries": {
            "job_ids_hard_coded": False,
            "companies_hard_coded": False,
            "direct_top5_writes": False,
            "direct_rank_writes": False,
            "hard_filter_operator_auto_pass": False,
            "provider_or_llm_requests": 0,
            "selection_requires_current_employer_origin": True,
            "selection_requires_exact_live_vacancy": True,
            "selection_requires_approved_candidate_fact_match": True,
            "candidate_fit_and_affinity_remain_separate": True,
            "numeric_candidate_fit_authority_created": False,
            "combined_score_authority_created": combined_score,
        },
    }


def test_assessment_payload_is_exact_and_never_accepts_authority_tokens() -> None:
    actions.parse_assessment_action_payload(
        {
            "action": actions.ASSESSMENT_ACTION_NAME,
            "confirmation": actions.ASSESSMENT_CONFIRMATION,
        }
    )

    with pytest.raises(actions.AssessmentActionStop, match="unexpected fields: approval_token"):
        actions.parse_assessment_action_payload(
            {
                "action": actions.ASSESSMENT_ACTION_NAME,
                "confirmation": actions.ASSESSMENT_CONFIRMATION,
                "approval_token": "forbidden",
            }
        )
    with pytest.raises(actions.AssessmentActionStop, match="exact assessment confirmation"):
        actions.parse_assessment_action_payload(
            {
                "action": actions.ASSESSMENT_ACTION_NAME,
                "confirmation": "yes",
            }
        )


def test_local_assessment_reuses_existing_authorities_and_publishes_bounded_result(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(actions, "REPORT_ROOT", tmp_path)
    monkeypatch.setattr(actions, "REPORT_PATH", tmp_path / "current.json")

    def run(*, output: Path) -> subprocess.CompletedProcess[str]:
        output.write_text(json.dumps(_report()) + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            args=["assessment"],
            returncode=0,
            stdout="TARGET_MET=true",
            stderr="",
        )

    monkeypatch.setattr(actions, "_run_cohort", run)

    result = actions.apply_assessment_action()

    assert result["status"] == "complete"
    assert result["target_met"] is True
    assert result["provider_requests"] == 0
    assert result["direct_rank_writes"] == 0
    assert result["direct_top5_writes"] == 0
    assert result["candidate_fit_numeric_score_created"] is False
    assert result["combined_score_created"] is False
    assert result["summary"] == {
        "selected_count": 10,
        "profile_fit_complete_count": 10,
        "profile_fit_passed_count": 6,
        "rankable_job_count": 5,
        "top_job_count": 5,
    }
    assert actions.REPORT_PATH.is_file()


def test_incomplete_bounded_assessment_is_published_as_diagnostics(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(actions, "REPORT_ROOT", tmp_path)
    monkeypatch.setattr(actions, "REPORT_PATH", tmp_path / "current.json")

    def run(*, output: Path) -> subprocess.CompletedProcess[str]:
        output.write_text(
            json.dumps(_report(target_met=False)) + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            args=["assessment"],
            returncode=1,
            stdout="TARGET_MET=false",
            stderr="",
        )

    monkeypatch.setattr(actions, "_run_cohort", run)

    result = actions.apply_assessment_action()

    assert result["status"] == "incomplete"
    assert result["target_met"] is False
    assert result["summary"]["top_job_count"] == 4
    assert actions.REPORT_PATH.is_file()


def test_local_assessment_fails_closed_on_combined_score_or_boundary_drift(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(actions, "REPORT_ROOT", tmp_path)
    monkeypatch.setattr(actions, "REPORT_PATH", tmp_path / "current.json")

    def run(*, output: Path) -> subprocess.CompletedProcess[str]:
        output.write_text(
            json.dumps(_report(combined_score=True)) + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args=["assessment"], returncode=0)

    monkeypatch.setattr(actions, "_run_cohort", run)

    with pytest.raises(actions.AssessmentActionStop, match="authority boundary drift"):
        actions.apply_assessment_action()

    assert not actions.REPORT_PATH.exists()


def _handler(path: str, payload: object):
    handler = object.__new__(server.ProductV1Handler)
    handler.path = path
    body = json.dumps(payload).encode("utf-8")
    handler.headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
    }
    handler.rfile = BytesIO(body)
    responses: list[tuple[dict[str, object], object]] = []

    def send_json(payload: dict[str, object], *, status=200) -> None:
        responses.append((payload, status))

    handler._send_json = send_json  # type: ignore[method-assign]
    return handler, responses


def test_control_center_route_invokes_exact_assessment_action_once(monkeypatch) -> None:
    calls: list[int] = []

    def apply() -> dict[str, object]:
        calls.append(1)
        return {
            "status": "complete",
            "target_met": True,
            "provider_requests": 0,
            "direct_rank_writes": 0,
            "direct_top5_writes": 0,
        }

    monkeypatch.setattr(server, "apply_assessment_action", apply)
    handler, responses = _handler(
        actions.ASSESSMENT_ACTION_PATH,
        {
            "action": actions.ASSESSMENT_ACTION_NAME,
            "confirmation": actions.ASSESSMENT_CONFIRMATION,
        },
    )

    handler.do_POST()

    assert calls == [1]
    assert responses[0][0]["status"] == "complete"
    assert int(responses[0][1]) == 200


def test_control_center_rejects_forged_assessment_authority_before_action(
    monkeypatch,
) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        server,
        "apply_assessment_action",
        lambda: calls.append(1),
    )
    handler, responses = _handler(
        actions.ASSESSMENT_ACTION_PATH,
        {
            "action": actions.ASSESSMENT_ACTION_NAME,
            "confirmation": actions.ASSESSMENT_CONFIRMATION,
            "approval_token": "forbidden",
        },
    )

    handler.do_POST()

    assert calls == []
    assert responses[0][0]["status"] == "blocked"
    assert "approval_token" in str(responses[0][0]["reason"])
    assert int(responses[0][1]) == 400
