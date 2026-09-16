"""Read-only F4B current-cohort baseline; never grants ranking authority."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import Mapping

COMPONENTS = {
    "profile_direction": "profile_direction_score",
    "data_focus": "data_focus_score",
    "reliability_focus": "reliability_focus_score",
    "evidence_quality": "evidence_quality_score",
}
FACTORS = (
    "geography_work_model_commute",
    "skills_capabilities",
    "seniority",
    "hard_requirements",
)
FIT_STATES = {"passed", "failed", "unknown"}


class ReconciliationStop(RuntimeError):
    pass


def _number(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() and 0 <= result <= 100 else None


def _affinity_proxy(row: Mapping[str, object], policy: Mapping[str, object]) -> float | None:
    if policy.get("status") != "approved":
        return None
    weights = policy.get("ranking_weights")
    if not isinstance(weights, Mapping) or set(weights) != set(COMPONENTS):
        return None
    values = {name: _number(row.get(key)) for name, key in COMPONENTS.items()}
    parsed_weights = {name: _number(weights.get(name)) for name in COMPONENTS}
    if any(value is None for value in values.values()) or any(value is None for value in parsed_weights.values()):
        return None
    denominator = sum(parsed_weights.values())
    if denominator <= 0:
        return None
    return float(round(sum(values[name] * parsed_weights[name] for name in COMPONENTS) / denominator, 2))


def _first_blocker(row: Mapping[str, object]) -> str:
    if row.get("lifecycle_status") != "active_confirmed":
        return "lifecycle_not_current"
    if row.get("origin_validation_status") != "validated":
        return "origin_not_validated"
    if row.get("hard_filter_status") == "failed":
        reasons = row.get("hard_filter_reasons")
        if isinstance(reasons, Mapping):
            for key in ("employment", "languages", "weekly_hours", "seniority_and_capability_fit"):
                if reasons.get(key) == "failed":
                    return f"hard_filter_failed:{key}"
        return "hard_filter_failed:reason_unavailable"
    if row.get("hard_filter_status") != "passed":
        return "hard_filter_evidence_required"
    if row.get("profile_fit_decision") == "failed":
        failed = row.get("profile_fit_failed_factors")
        return f"profile_fit_failed:{failed[0]}" if isinstance(failed, list) and failed else "profile_fit_failed:factor_unavailable"
    if row.get("profile_fit_decision") != "passed":
        missing = row.get("profile_fit_missing_factors")
        return f"profile_fit_unknown:{missing[0]}" if isinstance(missing, list) and missing else "profile_fit_unknown:factor_unavailable"
    if row.get("product_readiness_status") != "rankable":
        return f"product_readiness:{row.get('product_readiness_status') or 'missing'}"
    return "numeric_fit_contract_not_approved"


def reconcile(payload: Mapping[str, object], *, source_sha: str) -> dict[str, object]:
    jobs = payload.get("job_readiness")
    top = payload.get("top_jobs")
    policy = payload.get("ranking_policy")
    if not isinstance(jobs, list) or not isinstance(top, list) or not isinstance(policy, Mapping):
        raise ReconciliationStop("PRODUCT_PAYLOAD_SHAPE_INVALID")
    current = [row for row in jobs if isinstance(row, Mapping) and row.get("lifecycle_status") == "active_confirmed"]
    if not current:
        raise ReconciliationStop("NO_CURRENT_JOBS")
    top_ids = {row.get("silver_job_id") for row in top if isinstance(row, Mapping)}
    ids = [row.get("silver_job_id") for row in current]
    if any(not isinstance(value, int) or value <= 0 for value in ids) or len(set(ids)) != len(ids):
        raise ReconciliationStop("CURRENT_IDENTITY_INVALID_OR_DUPLICATE")
    rows = []
    for row in sorted(current, key=lambda item: item["silver_job_id"]):
        factors = row.get("profile_fit_factors")
        if not isinstance(factors, Mapping) or set(factors) != set(FACTORS):
            raise ReconciliationStop(f"FIT_FACTORS_INVALID:{row['silver_job_id']}")
        states = {}
        for name in FACTORS:
            factor = factors[name]
            if not isinstance(factor, Mapping) or factor.get("status") not in FIT_STATES:
                raise ReconciliationStop(f"FIT_FACTOR_STATE_INVALID:{row['silver_job_id']}:{name}")
            states[name] = {"status": factor["status"], "reason": str(factor.get("reason") or "missing")}
        if row.get("profile_fit_decision") not in FIT_STATES:
            raise ReconciliationStop(f"FIT_DECISION_INVALID:{row['silver_job_id']}")
        affinity = _affinity_proxy(row, policy)
        rows.append({
            "silver_job_id": row["silver_job_id"],
            "company_name": str(row.get("company_name") or ""),
            "title": str(row.get("title") or ""),
            "source_name": str(row.get("source_name") or ""),
            "source_url": str(row.get("source_url") or ""),
            "lifecycle_status": row.get("lifecycle_status"),
            "origin_validation_status": row.get("origin_validation_status"),
            "affinity_proxy_score": affinity,
            "affinity_component_scores": {name: float(value) if (value := _number(row.get(key))) is not None else None for name, key in COMPONENTS.items()},
            "profile_fit_coverage_status": row.get("profile_fit_coverage_status"),
            "profile_fit_decision": row.get("profile_fit_decision"),
            "profile_fit_factors": states,
            "profile_fit_failed_factors": list(row.get("profile_fit_failed_factors") or []),
            "profile_fit_missing_factors": list(row.get("profile_fit_missing_factors") or []),
            "hard_filter_status": row.get("hard_filter_status"),
            "hard_filter_reasons": {key: value for key, value in (row.get("hard_filter_reasons") or {}).items() if key in {"employment", "languages", "weekly_hours", "seniority_and_capability_fit"}},
            "product_readiness_status": row.get("product_readiness_status"),
            "current_top5_member": row["silver_job_id"] in top_ids,
            "candidate_numeric_fit_score": None,
            "fit_evidence_coverage": sum(value["status"] != "unknown" for value in states.values()) / len(FACTORS),
            "fit_score_confidence": "not_defined",
            "candidate_combined_arithmetic_60_40": None,
            "candidate_combined_geometric_60_40": None,
            "first_blocker": _first_blocker(row),
        })
    blockers = Counter(row["first_blocker"] for row in rows)
    threshold = _number(policy.get("minimum_quality_score"))
    return {
        "schema": "jap.f4b.readonly_current_cohort.v1",
        "source_sha": source_sha,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "authority": "calibration_only_no_ranking_mutation",
        "policy_version": policy.get("policy_version"),
        "runtime_minimum_quality_score": float(threshold) if threshold is not None else None,
        "contract_minimum_quality_score": 70,
        "runtime_threshold_contract_match": threshold == 70,
        "summary": {
            "current_count": len(rows),
            "fit_decisions": dict(Counter(row["profile_fit_decision"] for row in rows)),
            "readiness": dict(Counter(row["product_readiness_status"] for row in rows)),
            "first_blockers": dict(blockers),
            "current_top5_count": sum(row["current_top5_member"] for row in rows),
            "affinity_proxy_scored_count": sum(row["affinity_proxy_score"] is not None for row in rows),
            "numeric_fit_scored_count": 0,
            "combined_candidate_scored_count": 0,
        },
        "hannover_re_issue_884": [
            {"silver_job_id": row["silver_job_id"], "fit_decision": row["profile_fit_decision"], "failed_factors": row["profile_fit_failed_factors"], "first_blocker": row["first_blocker"], "classification": "hard_gate_negative_origin_detail_validation_pending" if row["profile_fit_decision"] == "failed" else "insufficient_evidence"}
            for row in rows if row["source_name"] == "generic_origin:hannover_ruck"
        ],
        "rows": rows,
        "boundaries": {"provider_calls": 0, "candidate_fact_private_fields_exported": False, "ranking_authority_changed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    from scripts.product_v1_control_center_base import load_product_v1_payload
    report = reconcile(load_product_v1_payload(include_source_connector_overview=False), source_sha=args.source_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key in {"source_sha", "summary", "runtime_threshold_contract_match"}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
