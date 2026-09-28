"""Generic evidence-bound closer for Product V1 hard-filter weekly-hours unknowns.

This module never overrides a deterministic failure. It may create an existing
version-bound Product V1 hard-filter review only when:
- Candidate capability fit is already passed;
- employment, language and seniority hard-filter components already pass;
- weekly hours is the only remaining manual-review component;
- the exact current employer-origin vacancy explicitly states full-time/Vollzeit;
- the current vacancy exposes no conflicting numeric weekly-hours evidence.

The review does not create ranking or Top-5 truth. It only resolves the existing
operator-review gate from explicit current vacancy evidence.
"""
from __future__ import annotations

import re
from typing import Mapping, Sequence
from urllib.parse import urlparse

from scripts import run_product_v1_hard_filter_review as hard_review
from scripts import run_product_v1_ranking_score_review as ranking_review
from scripts.run_product_v1_assessment_materialization import (
    authorized_recurring_employer_origin_sources,
)
from src.ingestion.repository import JobIngestionRepository
from src.search_intelligence.product_v1_assessment_evidence import (
    extract_product_v1_assessment_evidence,
    normalize_job_text,
)
from src.search_intelligence.product_v1_downstream_preview import (
    fetch_public_https_detail_text,
)


_FULL_TIME_RE = re.compile(
    r"\b(?:full[ -]?time|vollzeit(?:stelle|position|beschäftigung|beschaeftigung)?)\b",
    re.IGNORECASE,
)


class ProductHardFilterEvidenceCloseStop(RuntimeError):
    """Fail closed when current evidence cannot authorize a review."""


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


def _policy_weekly_window() -> tuple[float, float]:
    with hard_review.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT weekly_hours_min, weekly_hours_max
                FROM product_v1_hard_filter_policy
                WHERE policy_key = 'default'
                  AND status = 'approved'
                """
            )
            row = cur.fetchone()
        conn.rollback()
    if row is None:
        raise ProductHardFilterEvidenceCloseStop("approved hard-filter policy is missing")
    minimum = float(row["weekly_hours_min"])
    maximum = float(row["weekly_hours_max"])
    if minimum <= 0 or maximum < minimum:
        raise ProductHardFilterEvidenceCloseStop("approved weekly-hours policy is invalid")
    return minimum, maximum


def build_evidence_reviews(
    silver_job_ids: Sequence[int],
) -> tuple[tuple[hard_review.ReviewRequest, ...], list[dict[str, object]]]:
    ids = tuple(dict.fromkeys(int(value) for value in silver_job_ids if int(value) > 0))
    if not ids:
        return (), []

    with hard_review.connect() as conn:
        hard_review.ensure_schema(conn)
        hard_rows = hard_review.load_current_rows(conn, ids)
        conn.rollback()
    with ranking_review.connect() as conn:
        ranking_rows = ranking_review.load_current_rows(conn, ids)
        conn.rollback()

    policy_min, policy_max = _policy_weekly_window()
    authorized_sources = set(
        authorized_recurring_employer_origin_sources(JobIngestionRepository())
    )
    reviews: list[hard_review.ReviewRequest] = []
    diagnostics: list[dict[str, object]] = []

    for job_id in ids:
        row = hard_rows.get(job_id)
        rank_row = ranking_rows.get(job_id)
        if row is None or rank_row is None:
            diagnostics.append({"silver_job_id": job_id, "status": "blocked", "reason": "current_product_row_missing"})
            continue

        source_name = str(row.get("source_name") or "")
        if source_name not in authorized_sources:
            diagnostics.append({
                "silver_job_id": job_id,
                "status": "blocked",
                "reason": "employer_origin_authority_missing",
            })
            continue

        deterministic = str(row.get("deterministic_hard_filter_status") or "unknown")
        effective = str(row.get("hard_filter_status") or "unknown")
        capability = str(row.get("capability_fit_status") or "unknown")
        unknown = hard_review._unknown_components(row)

        if deterministic in {"passed", "failed"} or effective in {"passed", "failed"}:
            diagnostics.append({
                "silver_job_id": job_id,
                "status": "not_required",
                "reason": f"hard_filter_{effective if effective in {'passed', 'failed'} else deterministic}",
            })
            continue
        if capability != "passed":
            diagnostics.append({"silver_job_id": job_id, "status": "blocked", "reason": "capability_fit_not_passed"})
            continue
        if unknown != ("weekly_hours",):
            diagnostics.append({
                "silver_job_id": job_id,
                "status": "blocked",
                "reason": "unsupported_remaining_unknown_components",
                "unknown_components": list(unknown),
            })
            continue

        source_url = str(rank_row.get("source_url") or "").strip()
        if not source_url:
            diagnostics.append({"silver_job_id": job_id, "status": "blocked", "reason": "source_url_missing"})
            continue
        final_url, _page_title, detail_text = fetch_public_https_detail_text(source_url)
        if not _same_origin(source_url, final_url):
            diagnostics.append({
                "silver_job_id": job_id,
                "status": "blocked",
                "reason": "cross_origin_detail_redirect",
            })
            continue
        text = normalize_job_text(detail_text)
        if _FULL_TIME_RE.search(text) is None:
            diagnostics.append({"silver_job_id": job_id, "status": "blocked", "reason": "explicit_full_time_evidence_missing"})
            continue

        evidence = extract_product_v1_assessment_evidence(
            description=detail_text,
            title=str(rank_row.get("title") or row.get("title") or ""),
            source_url=final_url,
        )
        if evidence.weekly_hours_min is not None or evidence.weekly_hours_max is not None:
            diagnostics.append({
                "silver_job_id": job_id,
                "status": "blocked",
                "reason": "numeric_weekly_hours_requires_assessment_refresh",
            })
            continue
        if "weekly_hours" in evidence.conflicted_fields:
            diagnostics.append({
                "silver_job_id": job_id,
                "status": "blocked",
                "reason": "conflicting_weekly_hours_evidence",
            })
            continue

        rationale = (
            "Operator-triggered current vacancy review: exact employer-origin detail "
            f"{final_url} explicitly states full-time/Vollzeit; employment, language, "
            "seniority and Candidate capability gates already pass; no conflicting "
            "numeric weekly-hours evidence is present; approved weekly-hours policy "
            f"window is {policy_min:g}-{policy_max:g}."
        )
        reviews.append(
            hard_review.ReviewRequest(
                silver_job_id=job_id,
                decision="passed",
                rationale=rationale,
            )
        )
        diagnostics.append({
            "silver_job_id": job_id,
            "status": "reviewable",
            "reason": "explicit_full_time_only_remaining_hours_unknown",
        })

    return tuple(reviews), diagnostics


def close_hard_filter_unknowns(
    silver_job_ids: Sequence[int],
    *,
    reviewed_by: str,
    apply: bool,
) -> dict[str, object]:
    reviews, diagnostics = build_evidence_reviews(silver_job_ids)
    if not reviews:
        return {
            "review_count": 0,
            "inserted": 0,
            "unchanged": 0,
            "verification": [],
            "diagnostics": diagnostics,
        }

    with hard_review.connect() as conn:
        hard_review.ensure_schema(conn)
        rows = hard_review.load_current_rows(
            conn, [review.silver_job_id for review in reviews]
        )
        plan = hard_review.build_plan(reviews=reviews, current_rows=rows)
        conn.rollback()
        if int(plan["blocked_count"]) != 0:
            raise ProductHardFilterEvidenceCloseStop(
                f"hard-filter evidence review plan blocked: {plan['blocked']}"
            )

        inserted = 0
        unchanged = 0
        verification: tuple[dict[str, object], ...] = ()
        if apply:
            inserted, unchanged = hard_review.apply_plan(
                conn,
                plan=plan,
                reviewed_by=reviewed_by,
            )
            verification = hard_review.verify_applied(
                conn,
                [
                    item
                    for item in plan["proposals"]
                    if isinstance(item, Mapping)
                ],
            )

    return {
        "review_count": len(reviews),
        "inserted": inserted,
        "unchanged": unchanged,
        "verification": [dict(row) for row in verification],
        "diagnostics": diagnostics,
    }


__all__ = [
    "ProductHardFilterEvidenceCloseStop",
    "build_evidence_reviews",
    "close_hard_filter_unknowns",
]
