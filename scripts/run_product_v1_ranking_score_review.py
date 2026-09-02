"""Guarded deterministic Product V1 ranking-score persistence.

The approved Product V1 policy owns weights, threshold and Top-5 semantics. This
runner only derives and persists the four existing component scores from exact
employer-origin vacancy evidence. It is plan-only by default; apply is token gated.

Ranking persistence has a separate revision clock (`ranking_updated_at`) and does
not touch `job_product_assessments.updated_at`, so valid capability-fit and
hard-filter review bindings are not invalidated by ranking-only writes.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.config import get_database_config
from src.search_intelligence.product_v1_assessment_evidence import (
    extract_product_v1_assessment_evidence,
)
from src.search_intelligence.product_v1_downstream_preview import (
    fetch_public_https_detail_text,
)
from src.search_intelligence.product_v1_ranking_evidence import (
    RUBRIC_VERSION,
    build_product_v1_ranking_evidence,
)


REPORT_SCHEMA = "job_application_pipeline.product_v1_ranking_score_review.v1"
APPROVAL_TOKEN = "PRODUCT-V1-RANKING-SCORE-REVIEW-001"
LOCK_PREFIX = "DEMO-001:product_v1_ranking_score_review"
EXPECTED_WEIGHT_KEYS = frozenset(
    {"profile_direction", "reliability_focus", "data_focus", "evidence_quality"}
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class RankingScoreReviewStop(RuntimeError):
    """Fail closed when current product evidence cannot authorize ranking persistence."""


@dataclass(frozen=True)
class RankingPolicy:
    policy_version: str
    weights: Mapping[str, Decimal]
    minimum_quality_score: Decimal
    top_job_limit: int


@dataclass(frozen=True)
class RankingPlanItem:
    silver_job_id: int
    title: str
    source_url: str
    assessment_updated_at: datetime
    assessment_detail_sha256: str
    policy_version: str
    rubric_version: str
    component_scores: Mapping[str, float]
    overall_quality_score: Decimal
    evidence_payload: Mapping[str, object]
    would_change: bool


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        _json_safe(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _fingerprint(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RankingScoreReviewStop(message)


def _same_origin(left: str, right: str) -> bool:
    left_url = urlparse(left)
    right_url = urlparse(right)
    return (
        left_url.scheme.lower() == right_url.scheme.lower() == "https"
        and bool(left_url.hostname)
        and bool(right_url.hostname)
        and left_url.hostname.lower() == right_url.hostname.lower()
        and (left_url.port or 443) == (right_url.port or 443)
    )


def _decimal(value: object, *, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:  # pragma: no cover - defensive DB/config boundary
        raise RankingScoreReviewStop(f"ranking policy {field} is not numeric") from exc
    _require(result.is_finite(), f"ranking policy {field} must be finite")
    return result


def validate_policy(row: Mapping[str, object]) -> RankingPolicy:
    _require(str(row.get("status") or "") == "approved", "ranking policy is not approved")
    policy_version = str(row.get("policy_version") or "").strip()
    _require(bool(policy_version), "ranking policy version is missing")

    raw_weights = row.get("ranking_weights")
    _require(isinstance(raw_weights, Mapping), "ranking policy weights are missing")
    keys = frozenset(str(key) for key in raw_weights)
    _require(keys == EXPECTED_WEIGHT_KEYS, "ranking policy weight keys are invalid")
    weights = {
        key: _decimal(raw_weights[key], field=f"weight {key}") for key in EXPECTED_WEIGHT_KEYS
    }
    _require(all(value > 0 for value in weights.values()), "ranking policy weights must be positive")
    _require(sum(weights.values(), Decimal("0")) > 0, "ranking policy weight sum must be positive")

    minimum = _decimal(row.get("minimum_quality_score"), field="minimum_quality_score")
    _require(Decimal("0") <= minimum <= Decimal("100"), "ranking policy minimum is invalid")
    try:
        top_job_limit = int(row.get("top_job_limit") or 0)
    except (TypeError, ValueError) as exc:
        raise RankingScoreReviewStop("ranking policy Top-5 limit is invalid") from exc
    _require(1 <= top_job_limit <= 25, "ranking policy Top-5 limit is invalid")
    return RankingPolicy(
        policy_version=policy_version,
        weights=weights,
        minimum_quality_score=minimum,
        top_job_limit=top_job_limit,
    )


def calculate_overall_quality_score(
    component_scores: Mapping[str, object],
    policy: RankingPolicy,
) -> Decimal:
    factor_map = {
        "profile_direction": "profile_direction_score",
        "reliability_focus": "reliability_focus_score",
        "data_focus": "data_focus_score",
        "evidence_quality": "evidence_quality_score",
    }
    weighted = Decimal("0")
    total_weight = Decimal("0")
    for factor, score_key in factor_map.items():
        score = _decimal(component_scores.get(score_key), field=score_key)
        _require(Decimal("0") <= score <= Decimal("100"), f"ranking score is out of range: {score_key}")
        weight = policy.weights[factor]
        weighted += score * weight
        total_weight += weight
    _require(total_weight > 0, "ranking policy weight sum must be positive")
    return (weighted / total_weight).quantize(Decimal("0.01"))


def validate_current_authority(row: Mapping[str, object]) -> tuple[datetime, str]:
    _require(str(row.get("origin_validation_status") or "") == "validated", "job origin is not validated")
    _require(str(row.get("activity_status") or "") == "active", "job is not active")
    _require(str(row.get("capability_fit_status") or "") == "passed", "approved capability fit is required")
    _require(str(row.get("hard_filter_status") or "") == "passed", "current hard-filter status must be passed")

    assessment_updated_at = row.get("assessment_updated_at")
    _require(isinstance(assessment_updated_at, datetime), "assessment revision is missing")
    ranking_factors = row.get("ranking_factors")
    _require(isinstance(ranking_factors, Mapping), "assessment ranking_factors are missing")
    detail_sha = str(ranking_factors.get("detail_description_sha256") or "").strip()
    _require(_SHA256_RE.fullmatch(detail_sha) is not None, "assessment detail fingerprint is missing")
    return assessment_updated_at, detail_sha


def build_plan_item(
    *,
    row: Mapping[str, object],
    policy: RankingPolicy,
    final_url: str,
    detail_text: str,
) -> RankingPlanItem:
    assessment_updated_at, expected_detail_sha = validate_current_authority(row)
    source_url = str(row.get("source_url") or "").strip()
    title = str(row.get("title") or "").strip()
    _require(bool(source_url), "Silver source URL is missing")
    _require(bool(title), "Silver job title is missing")
    _require(_same_origin(source_url, final_url), "detail fetch redirected outside the authorized origin")

    assessment_evidence = extract_product_v1_assessment_evidence(
        description=detail_text,
        title=title,
        source_url=final_url,
    )
    _require(
        assessment_evidence.description_sha256 == expected_detail_sha,
        "current detail evidence changed since assessment materialization",
    )
    ranking_evidence = build_product_v1_ranking_evidence(
        title=title,
        description=detail_text,
        origin_validation_status=str(row["origin_validation_status"]),
        activity_status=str(row["activity_status"]),
        assessment_evidence=assessment_evidence,
    )
    component_scores = ranking_evidence.ranking_scores_patch()
    overall = calculate_overall_quality_score(component_scores, policy)
    evidence_payload = {
        **ranking_evidence.canonical_payload(),
        "assessment_detail_sha256": expected_detail_sha,
        "source_url": source_url,
    }

    current_scores = {
        "profile_direction_score": row.get("profile_direction_score"),
        "data_focus_score": row.get("data_focus_score"),
        "reliability_focus_score": row.get("reliability_focus_score"),
        "evidence_quality_score": row.get("evidence_quality_score"),
    }
    active_exact = (
        str(row.get("active_review_policy_version") or "") == policy.policy_version
        and str(row.get("active_review_rubric_version") or "") == RUBRIC_VERSION
        and row.get("active_review_assessment_updated_at") == assessment_updated_at
        and str(row.get("active_review_detail_sha256") or "") == expected_detail_sha
        and _json_safe(row.get("active_review_component_scores")) == _json_safe(component_scores)
        and _decimal(row.get("active_review_overall_quality_score"), field="active overall") == overall
        if row.get("active_review_overall_quality_score") is not None
        else False
    )
    scores_exact = all(
        current_scores[key] is not None
        and _decimal(current_scores[key], field=key) == _decimal(component_scores[key], field=key)
        for key in current_scores
    ) and (
        row.get("overall_quality_score") is not None
        and _decimal(row.get("overall_quality_score"), field="overall_quality_score") == overall
    )
    return RankingPlanItem(
        silver_job_id=int(row["silver_job_id"]),
        title=title,
        source_url=source_url,
        assessment_updated_at=assessment_updated_at,
        assessment_detail_sha256=expected_detail_sha,
        policy_version=policy.policy_version,
        rubric_version=RUBRIC_VERSION,
        component_scores=component_scores,
        overall_quality_score=overall,
        evidence_payload=evidence_payload,
        would_change=not (active_exact and scores_exact),
    )


def ensure_schema(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        for relation in (
            "product_v1_ranking_score_reviews",
            "job_product_assessments",
            "gold_product_v1_hard_filter_evaluation",
            "product_v1_ranking_policy",
        ):
            cur.execute("SELECT to_regclass(%s) AS relation", (f"public.{relation}",))
            row = cur.fetchone()
            _require(row is not None and row["relation"] is not None, f"missing relation: {relation}")


def load_policy(conn: psycopg.Connection[Any]) -> RankingPolicy:
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
    _require(row is not None, "default ranking policy is missing")
    return validate_policy(row)


def load_current_rows(
    conn: psycopg.Connection[Any], silver_job_ids: Sequence[int]
) -> dict[int, Mapping[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                sj.id AS silver_job_id,
                sj.title,
                sj.source_url,
                a.origin_validation_status,
                a.activity_status,
                a.capability_fit_status,
                a.updated_at AS assessment_updated_at,
                a.ranking_factors,
                a.profile_direction_score,
                a.data_focus_score,
                a.reliability_focus_score,
                a.evidence_quality_score,
                a.overall_quality_score,
                h.hard_filter_status,
                review.assessment_updated_at AS active_review_assessment_updated_at,
                review.assessment_detail_sha256 AS active_review_detail_sha256,
                review.policy_version AS active_review_policy_version,
                review.rubric_version AS active_review_rubric_version,
                review.component_scores AS active_review_component_scores,
                review.overall_quality_score AS active_review_overall_quality_score
            FROM silver_jobs sj
            JOIN job_product_assessments a ON a.silver_job_id = sj.id
            JOIN gold_product_v1_hard_filter_evaluation h ON h.silver_job_id = sj.id
            LEFT JOIN product_v1_ranking_score_reviews review
              ON review.silver_job_id = sj.id AND review.status = 'active'
            WHERE sj.id = ANY(%s)
            ORDER BY sj.id
            """,
            (list(silver_job_ids),),
        )
        return {int(row["silver_job_id"]): row for row in cur.fetchall()}


def apply_item(
    conn: psycopg.Connection[Any],
    *,
    item: RankingPlanItem,
    reviewed_by: str,
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (f"{LOCK_PREFIX}:{item.silver_job_id}",),
        )
        cur.execute(
            """
            SELECT
                a.origin_validation_status,
                a.activity_status,
                a.capability_fit_status,
                a.updated_at AS assessment_updated_at,
                a.ranking_factors,
                h.hard_filter_status,
                p.status AS policy_status,
                p.policy_version,
                p.ranking_weights,
                p.minimum_quality_score,
                p.top_job_limit
            FROM job_product_assessments a
            JOIN gold_product_v1_hard_filter_evaluation h
              ON h.silver_job_id = a.silver_job_id
            CROSS JOIN product_v1_ranking_policy p
            WHERE a.silver_job_id = %s
              AND p.policy_key = 'default'
            FOR UPDATE OF a
            """,
            (item.silver_job_id,),
        )
        current = cur.fetchone()
        _require(current is not None, f"current assessment disappeared: {item.silver_job_id}")
        current_assessment_at, current_detail_sha = validate_current_authority(current)
        current_policy = validate_policy(
            {
                "status": current["policy_status"],
                "policy_version": current["policy_version"],
                "ranking_weights": current["ranking_weights"],
                "minimum_quality_score": current["minimum_quality_score"],
                "top_job_limit": current["top_job_limit"],
            }
        )
        _require(current_assessment_at == item.assessment_updated_at, f"assessment changed after plan: {item.silver_job_id}")
        _require(current_detail_sha == item.assessment_detail_sha256, f"assessment detail changed after plan: {item.silver_job_id}")
        _require(current_policy.policy_version == item.policy_version, f"ranking policy changed after plan: {item.silver_job_id}")
        recalculated = calculate_overall_quality_score(item.component_scores, current_policy)
        _require(recalculated == item.overall_quality_score, f"ranking calculation changed after plan: {item.silver_job_id}")

        if not item.would_change:
            return False

        cur.execute(
            """
            UPDATE product_v1_ranking_score_reviews
            SET status = 'superseded', updated_at = now()
            WHERE silver_job_id = %s AND status = 'active'
            """,
            (item.silver_job_id,),
        )
        cur.execute(
            """
            INSERT INTO product_v1_ranking_score_reviews (
                silver_job_id, assessment_updated_at, assessment_detail_sha256,
                policy_version, rubric_version, component_scores,
                overall_quality_score, evidence_payload, status, reviewed_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s)
            """,
            (
                item.silver_job_id,
                item.assessment_updated_at,
                item.assessment_detail_sha256,
                item.policy_version,
                item.rubric_version,
                Jsonb(dict(item.component_scores)),
                item.overall_quality_score,
                Jsonb(dict(item.evidence_payload)),
                reviewed_by,
            ),
        )
        ranking_metadata = {
            "schema": REPORT_SCHEMA,
            "rubric_version": item.rubric_version,
            "policy_version": item.policy_version,
            "assessment_detail_sha256": item.assessment_detail_sha256,
            "evidence_payload_sha256": _fingerprint(item.evidence_payload),
        }
        cur.execute(
            """
            UPDATE job_product_assessments
            SET profile_direction_score = %s,
                data_focus_score = %s,
                reliability_focus_score = %s,
                evidence_quality_score = %s,
                overall_quality_score = %s,
                policy_key = 'default',
                policy_version = %s,
                ranking_factors = coalesce(ranking_factors, '{}'::jsonb)
                    || jsonb_build_object('ranking_score_review', %s::jsonb),
                ranking_updated_at = now()
            WHERE silver_job_id = %s
            """,
            (
                item.component_scores["profile_direction_score"],
                item.component_scores["data_focus_score"],
                item.component_scores["reliability_focus_score"],
                item.component_scores["evidence_quality_score"],
                item.overall_quality_score,
                item.policy_version,
                json.dumps(ranking_metadata, sort_keys=True),
                item.silver_job_id,
            ),
        )
    return True


def write_report(report: Mapping[str, object], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(_json_safe(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan or apply evidence-bound Product V1 ranking scores.")
    parser.add_argument("--silver-job-id", action="append", type=int, required=True)
    parser.add_argument("--reviewed-by", default="jens")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".runtime/demo/product_v1_ranking_score_review.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    silver_job_ids = tuple(dict.fromkeys(args.silver_job_id))
    if not silver_job_ids or any(value <= 0 for value in silver_job_ids):
        raise SystemExit("silver job ids must be positive")
    reviewed_by = args.reviewed_by.strip()
    if not reviewed_by:
        raise SystemExit("reviewed_by must not be blank")
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit("invalid ranking score review approval token")

    with connect() as conn:
        ensure_schema(conn)
        policy = load_policy(conn)
        rows = load_current_rows(conn, silver_job_ids)
        items: list[RankingPlanItem] = []
        for silver_job_id in silver_job_ids:
            row = rows.get(silver_job_id)
            _require(row is not None, f"Product V1 assessment is missing: {silver_job_id}")
            source_url = str(row.get("source_url") or "")
            final_url, detail_text = fetch_public_https_detail_text(source_url)
            items.append(build_plan_item(row=row, policy=policy, final_url=final_url, detail_text=detail_text))

        report: dict[str, object] = {
            "schema": REPORT_SCHEMA,
            "mode": "apply" if args.apply else "plan",
            "policy_version": policy.policy_version,
            "rubric_version": RUBRIC_VERSION,
            "request_count": len(items),
            "items": [
                {
                    "silver_job_id": item.silver_job_id,
                    "title": item.title,
                    "source_url": item.source_url,
                    "assessment_updated_at": item.assessment_updated_at,
                    "assessment_detail_sha256": item.assessment_detail_sha256,
                    "component_scores": item.component_scores,
                    "overall_quality_score": item.overall_quality_score,
                    "would_change": item.would_change,
                }
                for item in items
            ],
            "boundaries": {
                "bounded_origin_detail_reads": len(items),
                "provider_or_llm_requests": 0,
                "candidate_fact_writes": False,
                "capability_fit_writes": False,
                "hard_filter_writes": False,
                "direct_rank_or_top5_writes": False,
                "application_or_submission_actions": False,
                "assessment_revision_updated": False,
            },
        }
        if args.apply:
            changed = 0
            for item in items:
                if apply_item(conn, item=item, reviewed_by=reviewed_by):
                    changed += 1
            conn.commit()
            report["changed_count"] = changed
            report["unchanged_count"] = len(items) - changed
        else:
            conn.rollback()
        write_report(report, args.output)
    print(json.dumps(_json_safe(report), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
