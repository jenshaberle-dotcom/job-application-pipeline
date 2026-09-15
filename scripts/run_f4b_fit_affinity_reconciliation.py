"""Read-only F4B Fit + Affinity reconciliation for the current Product cohort.

This diagnostic consumes the same DB-backed Product V1 payload as the Control
Center. It creates no ranking, Top-5, Candidate Fact, application or provider
authority. Candidate combined scores are calibration-only and are emitted only
when currentness, Origin authority, hard gates, complete Fit evidence and the
current PD-052 Product score are all present.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from typing import Mapping

from scripts.product_v1_control_center_base import load_product_v1_payload
from scripts.product_v1_job_presentation_runtime import enrich_product_payload_for_operator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".runtime" / "f4b" / "fit_affinity_reconciliation.json"
FIT_FACTORS = (
    "geography_work_model_commute",
    "skills_capabilities",
    "seniority",
    "hard_requirements",
)
KNOWN_FACTOR_STATUSES = frozenset({"passed", "failed"})


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if math.isfinite(number) and 0.0 <= number <= 100.0:
            return number
    return None


def _identity_token(value: object) -> str:
    return "".join(character for character in str(value or "").casefold() if character.isalnum())


def _factor_snapshot(job: Mapping[str, object]) -> dict[str, dict[str, str]]:
    raw = job.get("profile_fit_factors")
    factors = raw if isinstance(raw, Mapping) else {}
    result: dict[str, dict[str, str]] = {}
    for name in FIT_FACTORS:
        item = factors.get(name)
        if isinstance(item, Mapping):
            status = str(item.get("status") or "unknown").strip().casefold()
            reason = str(item.get("reason") or "missing_reason").strip()
        else:
            status = "unknown"
            reason = "factor_not_projected"
        if status not in {"passed", "failed", "unknown"}:
            status = "unknown"
        result[name] = {"status": status, "reason": reason}
    return result


def _fit_diagnostic(job: Mapping[str, object]) -> dict[str, object]:
    factors = _factor_snapshot(job)
    statuses = [item["status"] for item in factors.values()]
    known = sum(status in KNOWN_FACTOR_STATUSES for status in statuses)
    passed = statuses.count("passed")
    failed = statuses.count("failed")
    coverage = round(100.0 * known / len(FIT_FACTORS), 1)
    # Equal-factor score is deliberately diagnostic only. It becomes numeric only
    # when every required F4A factor is known. Unknown never receives midpoint credit.
    numeric = round(100.0 * passed / len(FIT_FACTORS), 1) if known == len(FIT_FACTORS) else None
    missing = [name for name, item in factors.items() if item["status"] == "unknown"]
    failed_names = [name for name, item in factors.items() if item["status"] == "failed"]
    return {
        "coverage_pct": coverage,
        "known_factor_count": known,
        "passed_factor_count": passed,
        "failed_factor_count": failed,
        "diagnostic_equal_factor_score": numeric,
        "decision": str(job.get("profile_fit_decision") or "unknown"),
        "coverage_status": str(job.get("profile_fit_coverage_status") or "unknown"),
        "missing_factors": missing,
        "failed_factors": failed_names,
        "factors": factors,
        "numeric_score_authority": False,
    }


def _affinity(job: Mapping[str, object]) -> dict[str, object]:
    pd052 = _number(job.get("product_overall_quality_score"))
    review_preview = _number(job.get("review_fit_score"))
    display = _number(job.get("display_fit_score"))
    if display is None:
        display = _number(job.get("overall_quality_score"))
    return {
        "pd052_product_score": pd052,
        "review_preview_score": review_preview,
        "display_score": display,
        "display_scope": str(job.get("display_fit_scope") or "unknown"),
        "components": {
            "profile_direction": _number(job.get("profile_direction_score")),
            "reliability_focus": _number(job.get("reliability_focus_score")),
            "data_focus": _number(job.get("data_focus_score")),
            "evidence_quality": _number(job.get("evidence_quality_score")),
        },
        "ranking_authority": pd052 is not None,
    }


def _string_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if str(item).strip()]


def _sidecar_requirement_snapshot(job: Mapping[str, object]) -> dict[str, object]:
    source = str(job.get("requirement_evidence_source") or "none")
    employment_type = str(job.get("employment_type") or "unknown")
    languages = _string_list(job.get("required_languages"))
    weekly_min = job.get("weekly_hours_min")
    weekly_max = job.get("weekly_hours_max")
    seniority = str(job.get("requirements_seniority") or "unknown")
    job_skills = _string_list(job.get("job_skills"))
    work_model = str(job.get("work_model") or "unknown")
    capability_reason = str(
        _factor_snapshot(job)["skills_capabilities"].get("reason") or ""
    )
    geography_reason = str(
        _factor_snapshot(job)["geography_work_model_commute"].get("reason") or ""
    )
    return {
        "source": source,
        "is_primary_silver_sidecar": source == "silver_job_requirement_evidence",
        "employment_type": employment_type,
        "employment_evidence_status": str(job.get("employment_evidence_status") or "unknown"),
        "employment_value_present": employment_type not in {"", "unknown", "none"},
        "required_languages": languages,
        "language_evidence_status": str(job.get("language_evidence_status") or "unknown"),
        "language_values_present": bool(languages),
        "weekly_hours_min": weekly_min,
        "weekly_hours_max": weekly_max,
        "weekly_hours_evidence_status": str(job.get("weekly_hours_evidence_status") or "unknown"),
        "weekly_hours_numeric_present": isinstance(weekly_min, (int, float))
        or isinstance(weekly_max, (int, float)),
        "requirements_seniority": seniority,
        "seniority_evidence_status": str(job.get("seniority_evidence_status") or "unknown"),
        "seniority_value_present": seniority not in {"", "unknown", "none"},
        "job_skills": job_skills,
        "job_skills_present": bool(job_skills),
        "work_model": work_model,
        "work_model_present": work_model not in {"", "unknown", "none"},
        "conflicted_fields": _string_list(job.get("requirement_conflicted_fields")),
        "unresolved_fields": _string_list(job.get("requirement_unresolved_fields")),
        "capability_review_missing": capability_reason
        == "exact_current_candidate_fact_capability_review_missing",
        "geography_preference_missing": geography_reason
        == "approved_candidate_geography_preference_missing_or_ambiguous",
        "hard_filter_authority": False,
    }


def _first_exclusion(
    job: Mapping[str, object],
    *,
    fit: Mapping[str, object],
    affinity: Mapping[str, object],
) -> tuple[str | None, str | None]:
    lifecycle = str(job.get("lifecycle_status") or "unknown")
    if lifecycle != "active_confirmed":
        return f"lifecycle_not_current:{lifecycle}", "valid_exclusion"

    origin = str(job.get("origin_validation_status") or "unknown")
    if origin == "rejected":
        return "origin_rejected", "valid_exclusion"
    if origin != "validated":
        return f"origin_evidence_required:{origin}", "evidence_gap"

    activity = str(job.get("activity_status") or "unknown")
    if activity == "inactive":
        return "activity_inactive", "valid_exclusion"
    if activity != "active":
        return f"activity_evidence_required:{activity}", "evidence_gap"

    hard_filter = str(job.get("hard_filter_status") or "unknown")
    if hard_filter == "failed":
        return "hard_filter_failed", "valid_exclusion"
    if hard_filter != "passed":
        return f"hard_filter_evidence_required:{hard_filter}", "evidence_gap"

    decision = str(fit.get("decision") or "unknown")
    failed_factors = list(fit.get("failed_factors") or [])
    missing_factors = list(fit.get("missing_factors") or [])
    if decision == "failed" or failed_factors:
        suffix = ",".join(str(value) for value in failed_factors) or "unspecified"
        return f"fit_conflict:{suffix}", "valid_exclusion"
    if decision != "passed" or missing_factors:
        suffix = ",".join(str(value) for value in missing_factors) or decision
        return f"fit_evidence_required:{suffix}", "evidence_gap"

    if fit.get("diagnostic_equal_factor_score") is None:
        return "fit_numeric_evidence_required", "evidence_gap"
    if affinity.get("pd052_product_score") is None:
        return "affinity_pd052_score_required", "evidence_gap"
    return None, None


def _combined_candidates(
    *,
    fit_score: float | None,
    affinity_score: float | None,
    eligible: bool,
) -> dict[str, object]:
    if not eligible or fit_score is None or affinity_score is None:
        return {
            "eligible": False,
            "arithmetic_60_fit_40_affinity": None,
            "geometric_60_fit_40_affinity": None,
            "authority": False,
        }
    arithmetic = round(0.60 * fit_score + 0.40 * affinity_score, 2)
    geometric = (
        0.0
        if fit_score <= 0.0 or affinity_score <= 0.0
        else round(
            100.0
            * ((fit_score / 100.0) ** 0.60)
            * ((affinity_score / 100.0) ** 0.40),
            2,
        )
    )
    return {
        "eligible": True,
        "arithmetic_60_fit_40_affinity": arithmetic,
        "geometric_60_fit_40_affinity": geometric,
        "authority": False,
    }


def reconcile_payload(
    payload: Mapping[str, object],
    *,
    highlight_company: str = "Hannover Re",
) -> dict[str, object]:
    raw_jobs = payload.get("job_readiness")
    raw_top = payload.get("top_jobs")
    if not isinstance(raw_jobs, list) or not isinstance(raw_top, list):
        raise ValueError("Product payload lacks job_readiness/top_jobs lists")

    top_ids = {
        int(item.get("silver_job_id") or 0)
        for item in raw_top
        if isinstance(item, Mapping) and int(item.get("silver_job_id") or 0) > 0
    }
    current = [
        item
        for item in raw_jobs
        if isinstance(item, Mapping)
        and str(item.get("lifecycle_status") or "") == "active_confirmed"
    ]
    rows: list[dict[str, object]] = []
    exclusion_counts: Counter[str] = Counter()
    evidence_gap_counts: Counter[str] = Counter()
    valid_exclusion_counts: Counter[str] = Counter()

    for job in current:
        fit = _fit_diagnostic(job)
        affinity = _affinity(job)
        sidecar = _sidecar_requirement_snapshot(job)
        exclusion, exclusion_kind = _first_exclusion(job, fit=fit, affinity=affinity)
        if exclusion:
            exclusion_counts[exclusion] += 1
            if exclusion_kind == "evidence_gap":
                evidence_gap_counts[exclusion] += 1
            elif exclusion_kind == "valid_exclusion":
                valid_exclusion_counts[exclusion] += 1
        fit_score = fit.get("diagnostic_equal_factor_score")
        affinity_score = affinity.get("pd052_product_score")
        combined = _combined_candidates(
            fit_score=float(fit_score) if isinstance(fit_score, (int, float)) else None,
            affinity_score=(
                float(affinity_score)
                if isinstance(affinity_score, (int, float))
                else None
            ),
            eligible=exclusion is None,
        )
        silver_job_id = int(job.get("silver_job_id") or 0)
        rows.append(
            {
                "silver_job_id": silver_job_id,
                "company_name": str(job.get("company_name") or ""),
                "title": str(job.get("title") or ""),
                "source_name": str(job.get("source_name") or ""),
                "source_url": job.get("source_url"),
                "lifecycle_status": str(job.get("lifecycle_status") or "unknown"),
                "origin_validation_status": str(
                    job.get("origin_validation_status") or "unknown"
                ),
                "activity_status": str(job.get("activity_status") or "unknown"),
                "hard_filter_status": str(job.get("hard_filter_status") or "unknown"),
                "hard_filter_reasons": (
                    dict(job.get("hard_filter_reasons") or {})
                    if isinstance(job.get("hard_filter_reasons"), Mapping)
                    else {}
                ),
                "product_readiness_status": str(
                    job.get("product_readiness_status") or "unknown"
                ),
                "current_top5_member": silver_job_id in top_ids,
                "affinity": affinity,
                "fit": fit,
                "sidecar_requirement_evidence": sidecar,
                "combined_calibration": combined,
                "first_exclusion_reason": exclusion,
                "exclusion_kind": exclusion_kind,
            }
        )

    combined_rows = [row for row in rows if row["combined_calibration"]["eligible"]]
    combined_fit_scores = sorted(
        {
            float(row["fit"]["diagnostic_equal_factor_score"])
            for row in combined_rows
            if row["fit"]["diagnostic_equal_factor_score"] is not None
        }
    )
    fit_full = sum(float(row["fit"]["coverage_pct"]) == 100.0 for row in rows)
    fit_passed = sum(str(row["fit"]["decision"]) == "passed" for row in rows)
    fit_failed = sum(str(row["fit"]["decision"]) == "failed" for row in rows)
    fit_unknown = len(rows) - fit_passed - fit_failed
    pd052_count = sum(row["affinity"]["pd052_product_score"] is not None for row in rows)

    if evidence_gap_counts:
        dominant_gap, dominant_count = sorted(
            evidence_gap_counts.items(), key=lambda item: (-item[1], item[0])
        )[0]
        population_blocker = f"evidence_gap:{dominant_gap}:{dominant_count}"
    elif len(combined_rows) >= 2 and len(combined_fit_scores) <= 1:
        population_blocker = "fit_signal_not_granular_enough_for_combined_ranking"
    elif not combined_rows:
        population_blocker = "no_combined_eligible_rows"
    else:
        population_blocker = "none_read_only_reconciliation_ready"

    highlight = _identity_token(highlight_company)
    highlighted_rows = [
        {
            "silver_job_id": row["silver_job_id"],
            "company_name": row["company_name"],
            "title": row["title"],
            "hard_filter_status": row["hard_filter_status"],
            "hard_filter_reasons": row["hard_filter_reasons"],
            "fit_decision": row["fit"]["decision"],
            "fit_failed_factors": row["fit"]["failed_factors"],
            "fit_missing_factors": row["fit"]["missing_factors"],
            "first_exclusion_reason": row["first_exclusion_reason"],
            "diagnostic_classification": (
                "truthful_conclusive_negative_candidate"
                if row["hard_filter_status"] == "failed"
                and row["fit"]["decision"] == "failed"
                else "fit_conflict_requires_evidence_inspection"
                if row["fit"]["decision"] == "failed"
                else "insufficient_evidence"
                if row["fit"]["decision"] == "unknown"
                else "no_current_conflict"
            ),
        }
        for row in rows
        if highlight and highlight in _identity_token(row["company_name"])
    ]

    sidecar_rows = [
        row for row in rows if row["sidecar_requirement_evidence"]["is_primary_silver_sidecar"]
    ]
    employment_statuses = Counter(
        str(row["sidecar_requirement_evidence"]["employment_evidence_status"])
        for row in sidecar_rows
    )
    language_statuses = Counter(
        str(row["sidecar_requirement_evidence"]["language_evidence_status"])
        for row in sidecar_rows
    )
    weekly_statuses = Counter(
        str(row["sidecar_requirement_evidence"]["weekly_hours_evidence_status"])
        for row in sidecar_rows
    )
    seniority_statuses = Counter(
        str(row["sidecar_requirement_evidence"]["seniority_evidence_status"])
        for row in sidecar_rows
    )

    return {
        "schema": "job_application_pipeline.f4b_fit_affinity_reconciliation.v2",
        "summary": {
            "observed_product_job_count": len(raw_jobs),
            "current_job_count": len(rows),
            "origin_validated_active_count": sum(
                row["origin_validation_status"] == "validated"
                and row["activity_status"] == "active"
                for row in rows
            ),
            "hard_filter_passed_count": sum(
                row["hard_filter_status"] == "passed" for row in rows
            ),
            "fit_full_factor_coverage_count": fit_full,
            "fit_passed_count": fit_passed,
            "fit_failed_count": fit_failed,
            "fit_unknown_count": fit_unknown,
            "pd052_affinity_authority_count": pd052_count,
            "combined_calibration_eligible_count": len(combined_rows),
            "combined_fit_score_distinct_values": combined_fit_scores,
            "current_top5_count": len(top_ids),
            "population_blocker": population_blocker,
            "exclusion_counts": dict(sorted(exclusion_counts.items())),
            "evidence_gap_counts": dict(sorted(evidence_gap_counts.items())),
            "valid_exclusion_counts": dict(sorted(valid_exclusion_counts.items())),
            "silver_sidecar_primary_count": len(sidecar_rows),
            "silver_sidecar_employment_value_count": sum(
                bool(row["sidecar_requirement_evidence"]["employment_value_present"])
                for row in sidecar_rows
            ),
            "silver_sidecar_language_values_count": sum(
                bool(row["sidecar_requirement_evidence"]["language_values_present"])
                for row in sidecar_rows
            ),
            "silver_sidecar_weekly_hours_numeric_count": sum(
                bool(row["sidecar_requirement_evidence"]["weekly_hours_numeric_present"])
                for row in sidecar_rows
            ),
            "silver_sidecar_seniority_value_count": sum(
                bool(row["sidecar_requirement_evidence"]["seniority_value_present"])
                for row in sidecar_rows
            ),
            "silver_sidecar_job_skills_count": sum(
                bool(row["sidecar_requirement_evidence"]["job_skills_present"])
                for row in sidecar_rows
            ),
            "silver_sidecar_work_model_count": sum(
                bool(row["sidecar_requirement_evidence"]["work_model_present"])
                for row in sidecar_rows
            ),
            "silver_sidecar_employment_statuses": dict(sorted(employment_statuses.items())),
            "silver_sidecar_language_statuses": dict(sorted(language_statuses.items())),
            "silver_sidecar_weekly_hours_statuses": dict(sorted(weekly_statuses.items())),
            "silver_sidecar_seniority_statuses": dict(sorted(seniority_statuses.items())),
            "candidate_capability_review_missing_count": sum(
                bool(row["sidecar_requirement_evidence"]["capability_review_missing"])
                for row in rows
            ),
            "candidate_geography_preference_missing_count": sum(
                bool(row["sidecar_requirement_evidence"]["geography_preference_missing"])
                for row in rows
            ),
        },
        "issue_884_highlight": {
            "company_query": highlight_company,
            "rows": highlighted_rows,
            "production_exception_created": False,
        },
        "rows": rows,
        "boundaries": {
            "database_reads": True,
            "database_writes": False,
            "provider_requests": 0,
            "network_requests": 0,
            "operator_presentation_sidecar_read_only": True,
            "sidecar_diagnostic_creates_no_hard_filter_authority": True,
            "fit_numeric_score_is_diagnostic_only": True,
            "combined_scores_are_calibration_only": True,
            "pd052_production_authority_unchanged": True,
            "ranking_authority_created": False,
            "top5_authority_created": False,
            "application_authority_created": False,
            "employer_specific_production_exception_created": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--highlight-company", default="Hannover Re")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    base_payload = load_product_v1_payload(include_source_connector_overview=False)
    payload = enrich_product_payload_for_operator(base_payload)
    report = reconcile_payload(payload, highlight_company=args.highlight_company)
    summary = report["summary"]
    if int(summary["current_job_count"]) <= 0:
        raise SystemExit("F4B_NO_CURRENT_PRODUCT_JOBS")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("=== F4B FIT + AFFINITY READ-ONLY RECONCILIATION ===")
    for key in (
        "observed_product_job_count",
        "current_job_count",
        "origin_validated_active_count",
        "hard_filter_passed_count",
        "fit_full_factor_coverage_count",
        "fit_passed_count",
        "fit_failed_count",
        "fit_unknown_count",
        "pd052_affinity_authority_count",
        "combined_calibration_eligible_count",
        "current_top5_count",
        "silver_sidecar_primary_count",
        "silver_sidecar_employment_value_count",
        "silver_sidecar_language_values_count",
        "silver_sidecar_weekly_hours_numeric_count",
        "silver_sidecar_seniority_value_count",
        "silver_sidecar_job_skills_count",
        "candidate_capability_review_missing_count",
        "candidate_geography_preference_missing_count",
    ):
        print(f"{key.upper()}={summary[key]}")
    print(f"POPULATION_BLOCKER={summary['population_blocker']}")
    print("DATABASE_WRITES=0")
    print("PROVIDER_REQUESTS=0")
    print("NETWORK_REQUESTS=0")
    print(f"artifact={args.output.resolve()}")
    print("F4B_READ_ONLY_RECONCILIATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
