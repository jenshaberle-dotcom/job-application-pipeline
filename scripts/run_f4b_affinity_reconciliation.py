"""Read-only F4B Affinity reconciliation independent of Fit/hard-filter gates.

The legacy PD-052 component rubric is useful evidence for the question "Will ich
this job?", but its historic persistence runner gates calculation behind passed
Capability Fit and hard filters. F4B needs the components before those gates so
Affinity and Candidate<->Job Fit can be calibrated independently.

This runner fetches exact current Employer-Origin detail text and derives the
existing deterministic four component scores without mutating Product state. A
fetched detail revision matching the persisted assessment fingerprint is marked
``exact_persisted_revision``. A newer same-Origin detail revision is retained for
read-only calibration as ``unpersisted_current_revision`` and may never become
ranking/Fit authority merely through this runner. Unreachable or redirected
Origin evidence remains unavailable.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

from scripts.run_product_v1_ranking_score_review import (
    RankingPolicy,
    calculate_overall_quality_score,
    validate_policy,
)
from src.config import get_database_config
from src.search_intelligence.product_v1_assessment_evidence import (
    extract_product_v1_assessment_evidence,
)
from src.search_intelligence.product_v1_downstream_preview import (
    DownstreamPreviewStop,
    fetch_public_https_detail_text,
)
from src.search_intelligence.product_v1_ranking_evidence import (
    RUBRIC_VERSION,
    build_product_v1_ranking_evidence,
)

CANONICAL_PD052_WEIGHTS = {
    "profile_direction": Decimal("0.40"),
    "reliability_focus": Decimal("0.25"),
    "data_focus": Decimal("0.20"),
    "evidence_quality": Decimal("0.15"),
}


class AffinityReconciliationStop(RuntimeError):
    pass


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _same_origin(left: str, right: str) -> bool:
    first = urlparse(left)
    second = urlparse(right)
    return (
        first.scheme.casefold() == second.scheme.casefold() == "https"
        and bool(first.hostname)
        and bool(second.hostname)
        and first.hostname.casefold() == second.hostname.casefold()
        and (first.port or 443) == (second.port or 443)
    )


def _canonical_weights_match(policy: RankingPolicy) -> bool:
    return all(
        policy.weights.get(key) == value
        for key, value in CANONICAL_PD052_WEIGHTS.items()
    ) and set(policy.weights) == set(CANONICAL_PD052_WEIGHTS)


def _revision_binding(
    *, row: Mapping[str, object], current_detail_sha256: str
) -> tuple[str, str | None]:
    ranking_factors = row.get("ranking_factors")
    if not isinstance(ranking_factors, Mapping):
        return "current_origin_without_persisted_fingerprint", None
    expected = str(ranking_factors.get("detail_description_sha256") or "").strip()
    if len(expected) != 64:
        return "current_origin_without_persisted_fingerprint", None
    if current_detail_sha256 == expected:
        return "exact_persisted_revision", expected
    return "unpersisted_current_revision", expected


def build_affinity_candidate(
    *,
    row: Mapping[str, object],
    policy: RankingPolicy,
    final_url: str,
    detail_text: str,
) -> dict[str, object]:
    source_url = str(row.get("source_url") or "").strip()
    title = str(row.get("title") or "").strip()
    if not source_url or not title:
        raise AffinityReconciliationStop("CURRENT_JOB_IDENTITY_INCOMPLETE")
    if str(row.get("origin_validation_status") or "") != "validated":
        raise AffinityReconciliationStop("ORIGIN_NOT_VALIDATED")
    if str(row.get("activity_status") or "") != "active":
        raise AffinityReconciliationStop("JOB_NOT_ACTIVE")
    if not _same_origin(source_url, final_url):
        raise AffinityReconciliationStop("DETAIL_REDIRECT_OUTSIDE_AUTHORIZED_ORIGIN")

    assessment = extract_product_v1_assessment_evidence(
        description=detail_text,
        title=title,
        source_url=final_url,
    )
    revision_binding, persisted_detail_sha = _revision_binding(
        row=row,
        current_detail_sha256=assessment.description_sha256,
    )
    evidence = build_product_v1_ranking_evidence(
        title=title,
        description=detail_text,
        origin_validation_status="validated",
        activity_status="active",
        assessment_evidence=assessment,
    )
    components = evidence.ranking_scores_patch()
    score = calculate_overall_quality_score(components, policy)
    return {
        "silver_job_id": int(row["silver_job_id"]),
        "company_name": str(row.get("company_name") or ""),
        "title": title,
        "source_name": str(row.get("source_name") or ""),
        "source_url": source_url,
        "final_url": final_url,
        "legacy_affinity_proxy_score": float(score),
        "components": components,
        "uncertainties": list(evidence.uncertainties),
        "signal_count": len(evidence.references),
        "signal_names": sorted({reference.signal for reference in evidence.references}),
        "rubric_version": RUBRIC_VERSION,
        "revision_binding": revision_binding,
        "current_detail_sha256": assessment.description_sha256,
        "persisted_detail_sha256": persisted_detail_sha,
        "authority": "read_only_affinity_calibration_only",
    }


def reconcile_rows(
    *,
    rows: list[Mapping[str, object]],
    policy: RankingPolicy,
    fetch_detail=fetch_public_https_detail_text,
) -> dict[str, object]:
    candidates: list[dict[str, object]] = []
    unavailable: list[dict[str, object]] = []
    for row in rows:
        try:
            final_url, _page_title, detail_text = fetch_detail(str(row.get("source_url") or ""))
            candidates.append(
                build_affinity_candidate(
                    row=row,
                    policy=policy,
                    final_url=final_url,
                    detail_text=detail_text,
                )
            )
        except (AffinityReconciliationStop, DownstreamPreviewStop, ValueError) as exc:
            unavailable.append(
                {
                    "silver_job_id": int(row["silver_job_id"]),
                    "company_name": str(row.get("company_name") or ""),
                    "title": str(row.get("title") or ""),
                    "source_name": str(row.get("source_name") or ""),
                    "source_url": str(row.get("source_url") or ""),
                    "reason": str(exc),
                }
            )
    candidates.sort(
        key=lambda item: (-float(item["legacy_affinity_proxy_score"]), int(item["silver_job_id"]))
    )
    reasons = Counter(item["reason"] for item in unavailable)
    bindings = Counter(item["revision_binding"] for item in candidates)
    return {
        "current_job_count": len(rows),
        "affinity_candidate_count": len(candidates),
        "unavailable_count": len(unavailable),
        "unavailable_reasons": dict(sorted(reasons.items())),
        "revision_binding_counts": dict(sorted(bindings.items())),
        "top_affinity_candidates": candidates[:15],
        "candidates": candidates,
        "unavailable": unavailable,
    }


def _load() -> tuple[list[dict[str, object]], RankingPolicy]:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                """
                SELECT status, policy_version, ranking_weights,
                       minimum_quality_score, top_job_limit
                FROM product_v1_ranking_policy
                WHERE policy_key = 'default'
                """
            )
            policy_row = cur.fetchone()
            if policy_row is None:
                raise AffinityReconciliationStop("RANKING_POLICY_MISSING")
            policy = validate_policy(policy_row)
            cur.execute(
                """
                SELECT readiness.silver_job_id,
                       readiness.company_name,
                       readiness.title,
                       readiness.source_name,
                       readiness.source_url,
                       assessment.origin_validation_status,
                       assessment.activity_status,
                       assessment.ranking_factors
                FROM gold_product_v1_job_readiness readiness
                JOIN job_product_assessments assessment
                  ON assessment.silver_job_id = readiness.silver_job_id
                WHERE readiness.lifecycle_status = 'active_confirmed'
                ORDER BY readiness.silver_job_id
                """
            )
            rows = [dict(row) for row in cur.fetchall()]
        conn.rollback()
    return rows, policy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    rows, policy = _load()
    reconciliation = reconcile_rows(rows=rows, policy=policy)
    payload = {
        "schema": "jap.f4b.affinity_reconciliation.v2",
        "source_sha": args.source_sha,
        "authority": "read_only_affinity_calibration_no_ranking_mutation",
        "policy": {
            "policy_version": policy.policy_version,
            "runtime_minimum_quality_score": float(policy.minimum_quality_score),
            "weights": {key: float(value) for key, value in sorted(policy.weights.items())},
            "weights_match_canonical_pd052": _canonical_weights_match(policy),
            "rubric_version": RUBRIC_VERSION,
        },
        **reconciliation,
        "boundaries": {
            "database_writes": False,
            "provider_calls": 0,
            "candidate_fact_reads": 0,
            "current_origin_revision_may_be_unpersisted": True,
            "unpersisted_revision_grants_product_authority": False,
            "fit_authority_changed": False,
            "hard_filter_authority_changed": False,
            "ranking_authority_changed": False,
            "top5_authority_changed": False,
            "application_authority_changed": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "current_job_count": payload["current_job_count"],
                "affinity_candidate_count": payload["affinity_candidate_count"],
                "unavailable_count": payload["unavailable_count"],
                "revision_binding_counts": payload["revision_binding_counts"],
                "weights_match_canonical_pd052": payload["policy"]["weights_match_canonical_pd052"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
