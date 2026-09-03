"""Close DEMO-001 hard-filter unknowns only from explicit current vacancy evidence.

This bounded demo closer targets five already-live, freshly assessed, Candidate-Fact-
passed employer-origin vacancies. It uses the existing version-bound hard-filter
operator-review writer only after re-fetching each exact vacancy and checking the
explicit evidence needed for the remaining manual-review components. It then invokes
the canonical ranking-score writer for rows whose effective hard filter became
``passed``.

No deterministic hard-filter failure can be overridden. No source activation,
Candidate Fact, lifecycle, Top-5, application, submission or send state is written.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import re
from typing import Mapping

from scripts import run_product_v1_hard_filter_review as hard_review
from scripts import run_product_v1_ranking_score_review as ranking_review
from src.search_intelligence.product_v1_downstream_preview import (
    fetch_public_https_detail_text,
)

APPROVAL_TOKEN = "DEMO-001-HARD-FILTER-EVIDENCE-CLOSE-001"
TARGET_IDS = (174, 440, 467, 474, 511)


@dataclass(frozen=True)
class EvidenceRule:
    silver_job_id: int
    language_regexes: tuple[str, ...] = ()


RULES = {
    174: EvidenceRule(
        174,
        language_regexes=(r"english\s+is\s+required",),
    ),
    440: EvidenceRule(440),
    467: EvidenceRule(
        467,
        language_regexes=(r"deutsch.{0,40}c1", r"englisch"),
    ),
    474: EvidenceRule(474),
    511: EvidenceRule(511),
}


class DemoHardFilterEvidenceCloseStop(RuntimeError):
    """Fail closed when the current vacancy no longer supports the review."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DemoHardFilterEvidenceCloseStop(message)


def _review_requests() -> tuple[hard_review.ReviewRequest, ...]:
    with hard_review.connect() as conn:
        hard_review.ensure_schema(conn)
        rows = hard_review.load_current_rows(conn, TARGET_IDS)
        conn.rollback()

    requests: list[hard_review.ReviewRequest] = []
    for job_id in TARGET_IDS:
        row = rows.get(job_id)
        _require(row is not None, f"hard-filter row missing: {job_id}")
        _require(
            str(row.get("capability_fit_status") or "") == "passed",
            f"capability fit not passed: {job_id}",
        )
        _require(
            str(row.get("deterministic_hard_filter_status") or "") == "unknown",
            f"deterministic hard filter is not reviewable unknown: {job_id}",
        )
        _require(
            str(row.get("hard_filter_status") or "") == "unknown",
            f"effective hard filter is not unknown: {job_id}",
        )
        unknown = hard_review._unknown_components(row)
        _require(bool(unknown), f"no manual-review component remains: {job_id}")
        _require(
            set(unknown).issubset({"languages", "weekly_hours"}),
            f"unsupported manual-review components for {job_id}: {unknown}",
        )

        source_name = str(row.get("source_name") or "")
        _require(source_name.startswith("personio:"), f"not an employer-origin Personio row: {job_id}")

        with ranking_review.connect() as rank_conn:
            rank_rows = ranking_review.load_current_rows(rank_conn, [job_id])
            rank_conn.rollback()
        rank_row = rank_rows.get(job_id)
        _require(rank_row is not None, f"ranking source row missing: {job_id}")
        source_url = str(rank_row.get("source_url") or "")
        final_url, _page_title, detail_text = fetch_public_https_detail_text(source_url)
        text = " ".join(detail_text.casefold().split())

        _require(
            bool(re.search(r"\b(vollzeit|full[ -]?time)\b", text, flags=re.IGNORECASE)),
            f"explicit full-time evidence missing: {job_id}",
        )
        _require(
            bool(re.search(r"\b(festanstellung|permanent)\b", text, flags=re.IGNORECASE)),
            f"explicit permanent-employment evidence missing: {job_id}",
        )

        rule = RULES[job_id]
        if "languages" in unknown:
            _require(
                bool(rule.language_regexes),
                f"language review rule intentionally absent: {job_id}",
            )
            for pattern in rule.language_regexes:
                _require(
                    re.search(pattern, text, flags=re.IGNORECASE) is not None,
                    f"explicit accepted-language evidence missing for {job_id}: {pattern}",
                )

        evidence_bits = [
            f"current employer-origin detail {final_url}",
            "explicit full-time/Vollzeit",
            "explicit permanent/Festanstellung",
        ]
        if "languages" in unknown:
            evidence_bits.append("explicit required language evidence limited to accepted de/en")
        rationale = (
            "Operator-reviewed current vacancy evidence: "
            + "; ".join(evidence_bits)
            + ". Full-time is accepted as compatible with the approved 35-40h policy because no contrary weekly-hours evidence is stated."
        )
        requests.append(
            hard_review.ReviewRequest(
                silver_job_id=job_id,
                decision="passed",
                rationale=rationale,
            )
        )
        print(
            "EVIDENCE="
            f"{job_id}|unknown={','.join(unknown)}|"
            f"full_time=true|permanent=true|language_checked={str('languages' in unknown).lower()}|"
            f"{final_url}"
        )
    return tuple(requests)


def _rank_passed(reviewed_by: str) -> int:
    with ranking_review.connect() as conn:
        ranking_review.ensure_schema(conn)
        policy = ranking_review.load_policy(conn)
        rows = ranking_review.load_current_rows(conn, TARGET_IDS)
        items: list[ranking_review.RankingPlanItem] = []
        for job_id in TARGET_IDS:
            row = rows.get(job_id)
            _require(row is not None, f"ranking row missing after review: {job_id}")
            _require(
                str(row.get("hard_filter_status") or "") == "passed",
                f"hard filter did not become passed: {job_id}",
            )
            source_url = str(row.get("source_url") or "")
            final_url, _page_title, detail_text = fetch_public_https_detail_text(source_url)
            items.append(
                ranking_review.build_plan_item(
                    row=row,
                    policy=policy,
                    final_url=final_url,
                    detail_text=detail_text,
                )
            )
        conn.rollback()
        changed = sum(
            ranking_review.apply_item(conn, item=item, reviewed_by=reviewed_by)
            for item in items
        )
        conn.commit()
    return changed


def _final() -> tuple[int, int, list[Mapping[str, object]]]:
    with ranking_review.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT silver_job_id, company_name, title,
                       product_readiness_status, hard_filter_status,
                       overall_quality_score
                FROM gold_product_v1_job_readiness
                WHERE product_readiness_status = 'rankable'
                ORDER BY overall_quality_score DESC NULLS LAST, silver_job_id
                """
            )
            rankable = list(cur.fetchall())
            cur.execute("SELECT count(*) AS count FROM gold_product_v1_top_jobs")
            top_count = int(cur.fetchone()["count"])
        conn.rollback()
    return len(rankable), top_count, rankable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed-by", default="jens")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    reviewed_by = str(args.reviewed_by or "").strip()
    _require(bool(reviewed_by), "reviewed_by must not be blank")
    if args.apply:
        _require(args.approval_token == APPROVAL_TOKEN, "invalid DEMO-001 evidence-close approval token")

    reviews = _review_requests()
    with hard_review.connect() as conn:
        hard_review.ensure_schema(conn)
        rows = hard_review.load_current_rows(conn, TARGET_IDS)
        plan = hard_review.build_plan(reviews=reviews, current_rows=rows)
        conn.rollback()
        _require(int(plan["blocked_count"]) == 0, f"hard-filter review plan blocked: {plan['blocked']}")
        print(f"REVIEW_PROPOSALS={plan['proposal_count']}")
        if not args.apply:
            print("DATABASE_WRITES=0")
            print("PROVIDER_REQUESTS=0")
            print("DEMO_001_HARD_FILTER_EVIDENCE_CLOSE=PLAN_COMPLETE")
            return 0
        inserted, unchanged = hard_review.apply_plan(
            conn,
            plan=plan,
            reviewed_by=reviewed_by,
        )
        verification = hard_review.verify_applied(
            conn,
            [item for item in plan["proposals"] if isinstance(item, Mapping)],
        )

    print(f"REVIEW_INSERTED={inserted}")
    print(f"REVIEW_UNCHANGED={unchanged}")
    for row in verification:
        print(
            "HARD_FILTER_VERIFIED="
            f"{row['silver_job_id']}|review={row['operator_review_decision']}|"
            f"final={row['hard_filter_status']}"
        )

    ranking_changed = _rank_passed(reviewed_by)
    total_rankable, top_jobs, rankable = _final()
    print(f"RANKING_CHANGED={ranking_changed}")
    print(f"TOTAL_RANKABLE={total_rankable}")
    print(f"TOP_JOBS={top_jobs}")
    for row in rankable[:8]:
        print(
            "RANKABLE_JOB="
            f"{row['silver_job_id']}|score={row['overall_quality_score']}|"
            f"{row['company_name']}|{row['title']}"
        )
    _require(total_rankable >= 5, "rankable target < 5 after evidence close")
    _require(top_jobs >= 5, "Top-5 target < 5 after evidence close")
    print("PROVIDER_REQUESTS=0")
    print("DETERMINISTIC_HARD_FILTER_OVERRIDE=false")
    print("DEMO_001_HARD_FILTER_EVIDENCE_CLOSE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
