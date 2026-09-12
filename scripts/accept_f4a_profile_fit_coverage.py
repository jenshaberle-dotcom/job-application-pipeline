"""Fail-closed real Product acceptance for F4A Profile Fit coverage.

The script reads the same DB-backed Product payload as the Control Center. It
emits counts and generic reason/status buckets only; no Candidate Fact statement,
provenance reference or raw preference tag is printed.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import sys

if not __package__:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scripts.product_v1_control_center_base import load_product_v1_payload
from src.search_intelligence.product_v1_profile_fit_coverage import (
    INSUFFICIENT_EVIDENCE,
    PROFILE_FIT_COMPLETE,
)


_ALLOWED_STATUSES = {PROFILE_FIT_COMPLETE, INSUFFICIENT_EVIDENCE}
_ALLOWED_DECISIONS = {"passed", "failed", "unknown"}
_REQUIRED_FACTORS = {
    "geography_work_model_commute",
    "skills_capabilities",
    "seniority",
    "hard_requirements",
}
_PRIVATE_KEYS = {"statement", "provenance", "capability_tags", "referenced_fact_keys"}


def _contains_private_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            str(key) in _PRIVATE_KEYS or _contains_private_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_private_key(item) for item in value)
    return False


def main() -> int:
    payload = load_product_v1_payload()
    jobs = payload.get("job_readiness")
    summary = payload.get("summary")
    boundaries = payload.get("boundaries")
    if not isinstance(jobs, list) or not isinstance(summary, dict) or not isinstance(boundaries, dict):
        raise SystemExit("F4A_PRODUCT_PAYLOAD_SHAPE_INVALID")

    current = [
        job
        for job in jobs
        if isinstance(job, dict) and job.get("lifecycle_status") == "active_confirmed"
    ]
    if not current:
        raise SystemExit("F4A_NO_CURRENT_CANONICAL_JOBS")

    statuses = Counter(str(job.get("profile_fit_coverage_status") or "") for job in current)
    decisions = Counter(str(job.get("profile_fit_decision") or "") for job in current)
    unclassified = [
        int(job.get("silver_job_id") or 0)
        for job in current
        if job.get("profile_fit_coverage_status") not in _ALLOWED_STATUSES
    ]
    invalid_decisions = [
        int(job.get("silver_job_id") or 0)
        for job in current
        if job.get("profile_fit_decision") not in _ALLOWED_DECISIONS
    ]
    malformed_factors: list[int] = []
    for job in current:
        factors = job.get("profile_fit_factors")
        if not isinstance(factors, dict) or set(factors) != _REQUIRED_FACTORS:
            malformed_factors.append(int(job.get("silver_job_id") or 0))
            continue
        if any(
            not isinstance(value, dict)
            or value.get("status") not in {"passed", "failed", "unknown"}
            or not isinstance(value.get("reason"), str)
            or not value.get("reason")
            for value in factors.values()
        ):
            malformed_factors.append(int(job.get("silver_job_id") or 0))

    if unclassified:
        raise SystemExit(f"F4A_UNCLASSIFIED_CURRENT_JOBS:{unclassified}")
    if invalid_decisions:
        raise SystemExit(f"F4A_INVALID_DECISIONS:{invalid_decisions}")
    if malformed_factors:
        raise SystemExit(f"F4A_FACTOR_COVERAGE_INVALID:{malformed_factors}")

    complete = statuses[PROFILE_FIT_COMPLETE]
    insufficient = statuses[INSUFFICIENT_EVIDENCE]
    if complete + insufficient != len(current):
        raise SystemExit("F4A_CURRENT_PARTITION_INCOMPLETE")
    if int(summary.get("profile_fit_complete_count") or 0) != complete:
        raise SystemExit("F4A_SUMMARY_COMPLETE_COUNT_MISMATCH")
    if int(summary.get("profile_fit_insufficient_evidence_count") or 0) != insufficient:
        raise SystemExit("F4A_SUMMARY_INSUFFICIENT_COUNT_MISMATCH")
    if int(summary.get("profile_fit_unclassified_count") or 0) != 0:
        raise SystemExit("F4A_SUMMARY_HAS_UNCLASSIFIED_CURRENT_JOBS")
    if int(summary.get("current_active_job_count") or 0) != len(current):
        raise SystemExit("F4A_CURRENT_COUNT_MISMATCH")

    for job in current:
        status = str(job["profile_fit_coverage_status"])
        decision = str(job["profile_fit_decision"])
        failed_factors = job.get("profile_fit_failed_factors")
        missing_factors = job.get("profile_fit_missing_factors")
        if not isinstance(failed_factors, list) or not isinstance(missing_factors, list):
            raise SystemExit("F4A_FACTOR_LIST_SHAPE_INVALID")
        if status == INSUFFICIENT_EVIDENCE and decision != "unknown":
            raise SystemExit("F4A_MISSING_EVIDENCE_BECAME_NEGATIVE_OR_POSITIVE")
        if status == PROFILE_FIT_COMPLETE and decision == "unknown":
            raise SystemExit("F4A_COMPLETE_WITHOUT_DECISION")
        if decision == "failed" and not failed_factors:
            raise SystemExit("F4A_NEGATIVE_WITHOUT_FAILED_FACTOR")
        if decision == "passed" and missing_factors:
            raise SystemExit("F4A_POSITIVE_WITH_MISSING_FACTOR")
        if job.get("profile_fit_ranking_authority") is not False:
            raise SystemExit("F4A_RANKING_AUTHORITY_VIOLATION")
        if job.get("profile_fit_top5_authority") is not False:
            raise SystemExit("F4A_TOP5_AUTHORITY_VIOLATION")
        if job.get("profile_fit_application_authority") is not False:
            raise SystemExit("F4A_APPLICATION_AUTHORITY_VIOLATION")

    if boundaries.get("profile_fit_coverage_is_not_ranking_authority") is not True:
        raise SystemExit("F4A_BOUNDARY_RANKING_MARKER_MISSING")
    if boundaries.get("profile_fit_missing_evidence_is_not_negative_fit") is not True:
        raise SystemExit("F4A_BOUNDARY_MISSING_VS_NEGATIVE_MARKER_MISSING")

    coverage_payload = [
        {
            key: job.get(key)
            for key in (
                "profile_fit_coverage_status",
                "profile_fit_decision",
                "profile_fit_reason",
                "profile_fit_factors",
                "profile_fit_missing_factors",
                "profile_fit_failed_factors",
                "profile_fit_candidate_preference_dimensions",
            )
        }
        for job in current
    ]
    if _contains_private_key(coverage_payload):
        raise SystemExit("F4A_PRIVATE_CANDIDATE_FACT_FIELD_LEAK")
    serialized = json.dumps(coverage_payload, sort_keys=True)
    if "profile-fit.city." in serialized or "profile-fit.commute.max-" in serialized:
        raise SystemExit("F4A_RAW_PREFERENCE_TAG_LEAK")

    factor_missing = Counter(
        factor
        for job in current
        for factor in job.get("profile_fit_missing_factors", [])
    )
    factor_failed = Counter(
        factor
        for job in current
        for factor in job.get("profile_fit_failed_factors", [])
    )

    print("=== F4A REAL PRODUCT PROFILE FIT ACCEPTANCE ===")
    print(f"CURRENT_CANONICAL_JOBS={len(current)}")
    print(f"PROFILE_FIT_COMPLETE={complete}")
    print(f"INSUFFICIENT_EVIDENCE={insufficient}")
    print("PROFILE_FIT_UNCLASSIFIED=0")
    print("DECISIONS=" + ",".join(f"{key}:{value}" for key, value in sorted(decisions.items())))
    print("MISSING_FACTORS=" + ",".join(f"{key}:{value}" for key, value in sorted(factor_missing.items())))
    print("FAILED_FACTORS=" + ",".join(f"{key}:{value}" for key, value in sorted(factor_failed.items())))
    print("CANDIDATE_STATEMENTS_EMITTED=0")
    print("PROVENANCE_REFERENCES_EMITTED=0")
    print("RAW_PREFERENCE_TAGS_EMITTED=0")
    print("RANKING_AUTHORITY_CREATED=0")
    print("TOP5_AUTHORITY_CREATED=0")
    print("APPLICATION_AUTHORITY_CREATED=0")
    print("F4A_REAL_PRODUCT_PROFILE_FIT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
