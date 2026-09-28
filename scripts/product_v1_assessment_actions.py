"""Explicit local Product assessment action for the Control Center.

The action reuses the generic Product V1 assessment-cohort CLI. It does not own
runner selection, scheduling, ranking formulas or direct Top-5 writes. The
Control Center may request one bounded operator-triggered 10->5 evaluation; the
existing Candidate Fit, hard-filter and ranking authorities remain authoritative.

The internal cohort approval token never crosses the HTTP boundary. The child
report is validated fail-closed before it is exposed as action evidence.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Lock
from typing import Mapping


ASSESSMENT_ACTION_PATH = "/api/v1/product-v1/assessment-cohort"
ASSESSMENT_ACTION_NAME = "refresh_candidate_fit_and_top5"
ASSESSMENT_CONFIRMATION = "evaluate_current_jobs"
ACTION_SCHEMA_VERSION = "product_v1.control_center.assessment_action.v1"
COHORT_SCHEMA = "job_application_pipeline.product_v1_assessment_cohort.v1"
ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / ".runtime" / "product"
REPORT_PATH = REPORT_ROOT / "control_center_assessment_cohort.json"
_ACTION_LOCK = Lock()


class AssessmentActionStop(RuntimeError):
    """Fail closed before or after an invalid local assessment action."""


def parse_assessment_action_payload(payload: object) -> None:
    if not isinstance(payload, Mapping):
        raise AssessmentActionStop("assessment action payload must be a JSON object")
    keys = {str(key) for key in payload}
    required = {"action", "confirmation"}
    if keys != required:
        unexpected = sorted(keys - required)
        missing = sorted(required - keys)
        detail: list[str] = []
        if unexpected:
            detail.append(f"unexpected fields: {', '.join(unexpected)}")
        if missing:
            detail.append(f"missing fields: {', '.join(missing)}")
        raise AssessmentActionStop("; ".join(detail) or "invalid assessment action fields")
    if payload.get("action") != ASSESSMENT_ACTION_NAME:
        raise AssessmentActionStop("assessment action is invalid")
    if payload.get("confirmation") != ASSESSMENT_CONFIRMATION:
        raise AssessmentActionStop("exact assessment confirmation is required")


def _validated_report(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise AssessmentActionStop("assessment report root must be an object")
    if raw.get("schema") != COHORT_SCHEMA:
        raise AssessmentActionStop("assessment report schema mismatch")
    if raw.get("mode") != "apply":
        raise AssessmentActionStop("assessment report must prove apply mode")
    targets = raw.get("targets")
    if not isinstance(targets, Mapping) or {
        "evaluated_jobs": targets.get("evaluated_jobs"),
        "top5_jobs": targets.get("top5_jobs"),
        "candidate_cap": targets.get("candidate_cap"),
    } != {
        "evaluated_jobs": 10,
        "top5_jobs": 5,
        "candidate_cap": 15,
    }:
        raise AssessmentActionStop("assessment report target contract mismatch")

    boundaries = raw.get("boundaries")
    if not isinstance(boundaries, Mapping):
        raise AssessmentActionStop("assessment report has no boundary evidence")

    expected = {
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
        "combined_score_authority_created": False,
    }
    drift = {
        key: {"expected": expected_value, "actual": boundaries.get(key)}
        for key, expected_value in expected.items()
        if boundaries.get(key) != expected_value
    }
    if drift:
        raise AssessmentActionStop(
            "assessment authority boundary drift: "
            + json.dumps(drift, sort_keys=True, default=str)
        )

    final = raw.get("final")
    selection = raw.get("selection")
    if not isinstance(final, Mapping) or not isinstance(selection, Mapping):
        raise AssessmentActionStop("assessment report is missing final/selection evidence")
    return raw


FIT_FACTOR_NAMES = frozenset(
    {
        "geography_work_model_commute",
        "skills_capabilities",
        "seniority",
        "hard_requirements",
    }
)


FIT_BLOCKER_REASONS = frozenset(
    {
        "approved_candidate_geography_preference_missing_or_ambiguous",
        "job_geography_work_model_or_commute_evidence_missing",
        "exact_current_candidate_fact_capability_review_missing",
        "exact_current_candidate_fact_capability_review_invalid",
        "current_capability_evidence_required_for_seniority",
        "seniority_requirement_evidence_missing",
        "hard_requirement_evidence_missing",
    }
)


def _fit_blocker_counts(final: Mapping[str, object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    selected = final.get("selected")
    if not isinstance(selected, list):
        return counts
    for row in selected:
        if not isinstance(row, Mapping):
            continue
        missing = row.get("profile_fit_missing_factors")
        if not isinstance(missing, (list, tuple)):
            continue
        for raw in missing:
            factor = str(raw or "").strip()
            if factor not in FIT_FACTOR_NAMES:
                continue
            counts[factor] = counts.get(factor, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _fit_blocker_reason_counts(final: Mapping[str, object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    selected = final.get("selected")
    if not isinstance(selected, list):
        return counts
    for row in selected:
        if not isinstance(row, Mapping):
            continue
        missing = row.get("profile_fit_missing_factors")
        factors = row.get("profile_fit_factors")
        if not isinstance(missing, (list, tuple)) or not isinstance(factors, Mapping):
            continue
        for raw_factor in missing:
            factor = str(raw_factor or "").strip()
            if factor not in FIT_FACTOR_NAMES:
                continue
            detail = factors.get(factor)
            if not isinstance(detail, Mapping):
                continue
            reason = str(detail.get("reason") or "").strip()
            if reason not in FIT_BLOCKER_REASONS:
                continue
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _run_cohort(*, output: Path) -> subprocess.CompletedProcess[str]:
    # Lazy import avoids turning the read path into an eager dependency on the
    # assessment stack. The token is server-side authority and is never accepted
    # from an HTTP request.
    from scripts.run_product_v1_assessment_cohort import APPROVAL_TOKEN

    command = [
        sys.executable,
        "-m",
        "scripts.run_product_v1_assessment_cohort",
        "--evaluated-target",
        "10",
        "--top5-target",
        "5",
        "--candidate-cap",
        "15",
        "--reviewed-by",
        "control-center:operator",
        "--apply",
        "--approval-token",
        APPROVAL_TOKEN,
        "--output",
        str(output),
    ]
    return subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=2700,
    )


def apply_assessment_action() -> dict[str, object]:
    """Run one bounded local Product assessment and return validated evidence."""

    if not _ACTION_LOCK.acquire(blocking=False):
        return {
            "schema_version": ACTION_SCHEMA_VERSION,
            "action": ASSESSMENT_ACTION_NAME,
            "status": "already_running",
            "target_met": False,
            "provider_requests": 0,
            "direct_rank_writes": 0,
            "direct_top5_writes": 0,
        }

    staged: Path | None = None
    try:
        REPORT_ROOT.mkdir(parents=True, exist_ok=True)
        fd, raw_staged = tempfile.mkstemp(
            dir=REPORT_ROOT,
            prefix=".control-center-assessment.",
            suffix=".pending.json",
        )
        os.close(fd)
        staged = Path(raw_staged)

        try:
            completed = _run_cohort(output=staged)
        except subprocess.TimeoutExpired as exc:
            raise AssessmentActionStop("assessment cohort exceeded the 45-minute bound") from exc

        if not staged.is_file() or staged.stat().st_size == 0:
            diagnostic = (completed.stderr or completed.stdout or "").strip()[-1200:]
            raise AssessmentActionStop(
                "assessment cohort produced no report"
                + (f": {diagnostic}" if diagnostic else "")
            )
        try:
            report = _validated_report(json.loads(staged.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AssessmentActionStop("assessment cohort produced invalid JSON") from exc

        final = report["final"]
        selection = report["selection"]
        if not isinstance(final, Mapping) or not isinstance(selection, Mapping):
            raise AssessmentActionStop("assessment report lost final/selection evidence")

        target_met = report.get("target_met") is True
        if (completed.returncode == 0) != target_met:
            raise AssessmentActionStop(
                "assessment child exit code disagrees with target_met evidence"
            )

        authority_exit = int(report.get("authority_pipeline_exit_code") or 0)
        if target_met:
            required_counts = {
                "profile_fit_complete_count": 10,
                "profile_fit_passed_count": 5,
                "rankable_job_count": 5,
                "top_job_count": 5,
            }
            for key, minimum in required_counts.items():
                value = int(final.get(key) or 0)
                if key == "top_job_count":
                    if value != minimum:
                        raise AssessmentActionStop("target_met contradicts Top-5 count")
                elif value < minimum:
                    raise AssessmentActionStop(
                        f"target_met contradicts required {key}: {value}<{minimum}"
                    )
            if final.get("top5_authority_violations"):
                raise AssessmentActionStop(
                    "target_met contradicts Top-5 authority violations"
                )

        # Publish only validated evidence. Incomplete reports are useful operator
        # diagnostics and do not grant Top-5 authority by themselves.
        os.replace(staged, REPORT_PATH)
        staged = None

        status = "complete" if target_met else "incomplete"
        if authority_exit != 0:
            status = "blocked"

        return {
            "schema_version": ACTION_SCHEMA_VERSION,
            "action": ASSESSMENT_ACTION_NAME,
            "status": status,
            "target_met": target_met,
            "child_exit_code": int(completed.returncode),
            "authority_pipeline_exit_code": authority_exit,
            "summary": {
                "selected_count": int(selection.get("selected_count") or 0),
                "profile_fit_complete_count": int(final.get("profile_fit_complete_count") or 0),
                "profile_fit_passed_count": int(final.get("profile_fit_passed_count") or 0),
                "rankable_job_count": int(final.get("rankable_job_count") or 0),
                "top_job_count": int(final.get("top_job_count") or 0),
            },
            "selected_readiness_counts": dict(final.get("selected_readiness_counts") or {}),
            "fit_blocker_counts": _fit_blocker_counts(final),
            "fit_blocker_reason_counts": _fit_blocker_reason_counts(final),
            "top5_authority_violations": list(final.get("top5_authority_violations") or []),
            "provider_requests": 0,
            "direct_rank_writes": 0,
            "direct_top5_writes": 0,
            "candidate_fit_numeric_score_created": False,
            "combined_score_created": False,
            "mutation_scope": "existing_candidate_fit_hard_filter_and_ranking_authorities",
        }
    except OSError as exc:
        raise AssessmentActionStop("assessment local runtime/storage failure") from exc
    finally:
        if staged is not None:
            try:
                staged.unlink()
            except FileNotFoundError:
                pass
        _ACTION_LOCK.release()


__all__ = [
    "ACTION_SCHEMA_VERSION",
    "ASSESSMENT_ACTION_NAME",
    "ASSESSMENT_ACTION_PATH",
    "ASSESSMENT_CONFIRMATION",
    "AssessmentActionStop",
    "apply_assessment_action",
    "parse_assessment_action_payload",
]
