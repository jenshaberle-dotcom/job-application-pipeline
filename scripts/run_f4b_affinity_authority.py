"""Plan/apply exact-bound F4B C1 Affinity authority for current Product jobs.

C1 reuses the deterministic PD-052 components as Affinity ("Will ich diesen
Job?") independently of Candidate Fit and hard-filter completion. Only exact
persisted Employer-Origin revisions may be written. Newer same-Origin revisions
stay provisional and are skipped. This command never writes Fit, hard filters,
rank/Top-5, Combined score, applications or Candidate Facts.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from scripts.run_f4b_affinity_reconciliation import (
    CANONICAL_PD052_WEIGHTS,
    AffinityReconciliationStop,
    build_affinity_candidate,
)
from scripts.run_product_v1_ranking_score_review import validate_policy
from src.config import get_database_config
from src.search_intelligence.product_v1_downstream_preview import (
    DownstreamPreviewStop,
    fetch_public_https_detail_text,
)

REPORT_SCHEMA = "job_application_pipeline.f4b_affinity_authority.v1"
APPROVAL_TOKEN = "F4B-A1-C1-AFFINITY-2026-09-16"
EXPECTED_THRESHOLD = Decimal("70")
EXPECTED_POLICY_VERSION = "product-v1-2026-09-16-affinity-v1"
LOCK_PREFIX = "F4B:C1:affinity"


class AffinityAuthorityStop(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AffinityAuthorityStop(message)


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


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _load_policy(conn: psycopg.Connection[Any]):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT status, policy_version, ranking_weights,
                   minimum_quality_score, top_job_limit
            FROM product_v1_ranking_policy
            WHERE policy_key = 'default'
            """
        )
        row = cur.fetchone()
    _require(row is not None, "default ranking policy missing")
    policy = validate_policy(row)
    _require(policy.minimum_quality_score == EXPECTED_THRESHOLD, "PD-051 threshold is not 70")
    _require(policy.policy_version == EXPECTED_POLICY_VERSION, "F4B A1/C1 policy version not active")
    _require(dict(policy.weights) == CANONICAL_PD052_WEIGHTS, "PD-052 weights drifted")
    return policy


def _load_rows(conn: psycopg.Connection[Any]) -> list[dict[str, object]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT readiness.silver_job_id, readiness.company_name,
                   readiness.title, readiness.source_name, readiness.source_url,
                   assessment.origin_validation_status,
                   CASE readiness.lifecycle_status
                       WHEN 'active_confirmed' THEN 'active'
                       ELSE 'unknown'
                   END AS activity_status,
                   assessment.updated_at AS assessment_updated_at,
                   assessment.ranking_factors,
                   assessment.profile_direction_score,
                   assessment.reliability_focus_score,
                   assessment.data_focus_score,
                   assessment.evidence_quality_score,
                   assessment.overall_quality_score,
                   review.assessment_updated_at AS review_assessment_updated_at,
                   review.assessment_detail_sha256 AS review_detail_sha256,
                   review.policy_version AS review_policy_version,
                   review.rubric_version AS review_rubric_version,
                   review.component_scores AS review_component_scores,
                   review.overall_quality_score AS review_affinity_score
            FROM gold_product_v1_job_readiness readiness
            JOIN job_product_assessments assessment
              ON assessment.silver_job_id = readiness.silver_job_id
            LEFT JOIN product_v1_ranking_score_reviews review
              ON review.silver_job_id = readiness.silver_job_id
             AND review.status = 'active'
            WHERE readiness.lifecycle_status = 'active_confirmed'
              AND assessment.origin_validation_status = 'validated'
            ORDER BY readiness.silver_job_id
            """
        )
        return [dict(row) for row in cur.fetchall()]


def _same_scores(row: Mapping[str, object], candidate: Mapping[str, object]) -> bool:
    components = candidate["components"]
    assert isinstance(components, Mapping)
    pairs = (
        ("profile_direction_score", "profile_direction_score"),
        ("reliability_focus_score", "reliability_focus_score"),
        ("data_focus_score", "data_focus_score"),
        ("evidence_quality_score", "evidence_quality_score"),
    )
    try:
        if any(Decimal(str(row.get(left))) != Decimal(str(components[right])) for left, right in pairs):
            return False
        return Decimal(str(row.get("overall_quality_score"))) == Decimal(
            str(candidate["legacy_affinity_proxy_score"])
        )
    except Exception:
        return False


def _review_exact(row: Mapping[str, object], candidate: Mapping[str, object], policy_version: str) -> bool:
    if row.get("review_affinity_score") is None:
        return False
    components = candidate["components"]
    return all(
        (
            row.get("review_assessment_updated_at") == row.get("assessment_updated_at"),
            str(row.get("review_detail_sha256") or "") == str(candidate["persisted_detail_sha256"] or ""),
            str(row.get("review_policy_version") or "") == policy_version,
            _json_safe(row.get("review_component_scores")) == _json_safe(components),
            Decimal(str(row.get("review_affinity_score")))
            == Decimal(str(candidate["legacy_affinity_proxy_score"])),
        )
    )


def _plan(conn: psycopg.Connection[Any]) -> tuple[object, list[dict[str, object]], list[dict[str, object]]]:
    policy = _load_policy(conn)
    rows = _load_rows(conn)
    exact: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    for row in rows:
        try:
            final_url, _page_title, detail_text = fetch_public_https_detail_text(str(row["source_url"]))
            candidate = build_affinity_candidate(
                row=row,
                policy=policy,
                final_url=final_url,
                detail_text=detail_text,
            )
            if candidate["revision_binding"] != "exact_persisted_revision":
                skipped.append(
                    {
                        "silver_job_id": row["silver_job_id"],
                        "reason": str(candidate["revision_binding"]),
                    }
                )
                continue
            candidate["assessment_updated_at"] = row["assessment_updated_at"]
            candidate["would_change"] = not (
                _same_scores(row, candidate)
                and _review_exact(row, candidate, policy.policy_version)
            )
            exact.append(candidate)
        except (AffinityReconciliationStop, DownstreamPreviewStop, ValueError) as exc:
            skipped.append({"silver_job_id": row["silver_job_id"], "reason": str(exc)})
    return policy, exact, skipped


def _apply_one(
    conn: psycopg.Connection[Any], *, candidate: Mapping[str, object], policy_version: str, reviewed_by: str
) -> bool:
    if not bool(candidate["would_change"]):
        return False
    silver_job_id = int(candidate["silver_job_id"])
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"{LOCK_PREFIX}:{silver_job_id}",))
        cur.execute(
            """
            SELECT assessment.updated_at AS assessment_updated_at,
                   assessment.ranking_factors,
                   assessment.origin_validation_status,
                   policy.status AS policy_status,
                   policy.policy_version,
                   policy.minimum_quality_score,
                   policy.ranking_weights
            FROM job_product_assessments assessment
            CROSS JOIN product_v1_ranking_policy policy
            WHERE assessment.silver_job_id = %s
              AND policy.policy_key = 'default'
            FOR UPDATE OF assessment
            """,
            (silver_job_id,),
        )
        current = cur.fetchone()
        _require(current is not None, f"assessment disappeared:{silver_job_id}")
        _require(current["assessment_updated_at"] == candidate["assessment_updated_at"], f"assessment changed after plan:{silver_job_id}")
        ranking_factors = current["ranking_factors"]
        _require(isinstance(ranking_factors, Mapping), f"ranking factors missing:{silver_job_id}")
        _require(
            str(ranking_factors.get("detail_description_sha256") or "")
            == str(candidate["persisted_detail_sha256"]),
            f"detail binding changed after plan:{silver_job_id}",
        )
        _require(str(current["origin_validation_status"]) == "validated", f"origin changed after plan:{silver_job_id}")
        _require(str(current["policy_status"]) == "approved", "policy no longer approved")
        _require(str(current["policy_version"]) == policy_version, "policy changed after plan")
        _require(Decimal(str(current["minimum_quality_score"])) == EXPECTED_THRESHOLD, "threshold changed after plan")

        components = candidate["components"]
        assert isinstance(components, Mapping)
        evidence_payload = {
            "schema": REPORT_SCHEMA,
            "affinity_authority": "pd-052",
            "affinity_authority_status": "authoritative",
            "ranking_authority": False,
            "fit_authority": False,
            "combined_score_authority": False,
            "source_url": candidate["source_url"],
            "assessment_detail_sha256": candidate["persisted_detail_sha256"],
            "revision_binding": "exact_persisted_revision",
            "signal_names": candidate["signal_names"],
            "uncertainties": candidate["uncertainties"],
        }
        cur.execute(
            "UPDATE product_v1_ranking_score_reviews SET status='superseded', updated_at=now() WHERE silver_job_id=%s AND status='active'",
            (silver_job_id,),
        )
        cur.execute(
            """
            INSERT INTO product_v1_ranking_score_reviews (
                silver_job_id, assessment_updated_at, assessment_detail_sha256,
                policy_version, rubric_version, component_scores,
                overall_quality_score, evidence_payload, status, reviewed_by
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'active',%s)
            """,
            (
                silver_job_id,
                candidate["assessment_updated_at"],
                candidate["persisted_detail_sha256"],
                policy_version,
                candidate["rubric_version"],
                Jsonb(dict(components)),
                candidate["legacy_affinity_proxy_score"],
                Jsonb(evidence_payload),
                reviewed_by,
            ),
        )
        cur.execute(
            """
            UPDATE job_product_assessments
            SET profile_direction_score=%s,
                reliability_focus_score=%s,
                data_focus_score=%s,
                evidence_quality_score=%s,
                overall_quality_score=%s,
                policy_key='default',
                policy_version=%s,
                ranking_factors=coalesce(ranking_factors, '{}'::jsonb)
                    || jsonb_build_object(
                        'affinity_authority',
                        jsonb_build_object(
                            'authority','pd-052',
                            'status','authoritative',
                            'assessment_detail_sha256',%s,
                            'policy_version',%s
                        )
                    ),
                ranking_updated_at=now()
            WHERE silver_job_id=%s
            """,
            (
                components["profile_direction_score"],
                components["reliability_focus_score"],
                components["data_focus_score"],
                components["evidence_quality_score"],
                candidate["legacy_affinity_proxy_score"],
                policy_version,
                candidate["persisted_detail_sha256"],
                policy_version,
                silver_job_id,
            ),
        )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--reviewed-by", default="jens")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.apply:
        _require(args.approval_token == APPROVAL_TOKEN, "invalid F4B C1 approval token")
    reviewed_by = str(args.reviewed_by or "").strip()
    _require(bool(reviewed_by), "reviewed_by must not be blank")

    with connect() as conn:
        policy, exact, skipped = _plan(conn)
        changed = 0
        if args.apply:
            for candidate in exact:
                changed += int(
                    _apply_one(
                        conn,
                        candidate=candidate,
                        policy_version=policy.policy_version,
                        reviewed_by=reviewed_by,
                    )
                )
            conn.commit()
        else:
            conn.rollback()

    report = {
        "schema": REPORT_SCHEMA,
        "mode": "apply" if args.apply else "plan",
        "policy_version": policy.policy_version,
        "minimum_quality_score": float(policy.minimum_quality_score),
        "current_job_count": len(exact) + len(skipped),
        "exact_persisted_revision_count": len(exact),
        "would_change_count": sum(1 for item in exact if item["would_change"]),
        "changed_count": changed if args.apply else 0,
        "skipped_count": len(skipped),
        "skipped": skipped,
        "items": exact,
        "boundaries": {
            "candidate_fit_writes": False,
            "hard_filter_writes": False,
            "combined_score_writes": False,
            "top5_direct_writes": False,
            "candidate_fact_reads": False,
            "candidate_fact_writes": False,
            "provider_or_llm_requests": 0,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(_json_safe(report), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "mode": report["mode"],
        "current_job_count": report["current_job_count"],
        "exact_persisted_revision_count": report["exact_persisted_revision_count"],
        "would_change_count": report["would_change_count"],
        "changed_count": report["changed_count"],
        "skipped_count": report["skipped_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
