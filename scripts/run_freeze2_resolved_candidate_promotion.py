"""Freeze-II resolved candidate-promotion dry-run/apply adapter.

Dry-run is artifact-only. Apply is explicit, requires an expected cohort digest,
rechecks current DB duplicates, and creates only discovery-state candidate rows.
candidate_url intentionally remains NULL so existing origin persistence authority
is not bypassed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.config import get_database_config
from src.search_intelligence.freeze2_resolved_candidate_promotion import (
    build_resolved_promotion_plan,
    cohort_digest,
    report_payload,
)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected JSON object: {path}")
    return payload


def _connect() -> Any:
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _existing_company_keys(conn: Any, company_keys: tuple[str, ...]) -> set[str]:
    if not company_keys:
        return set()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT lower(company_key) AS company_key
            FROM employer_origin_source_candidates
            WHERE lower(company_key) = ANY(%s)
            """,
            (list(company_keys),),
        )
        return {str(row["company_key"]) for row in cur.fetchall()}


def _create_candidates(
    conn: Any,
    *,
    plan: Any,
    origin_by_key: dict[str, Any],
    approved_by: str,
    review_run_id: str,
    origin_run_id: str,
) -> list[dict[str, object]]:
    created: list[dict[str, object]] = []
    with conn.cursor() as cur:
        for item in plan.items:
            if not item.create_allowed:
                continue
            origin = origin_by_key[item.company_key]
            cur.execute(
                """
                INSERT INTO employer_origin_source_candidates (
                    company_key,
                    company_name,
                    candidate_url,
                    source_name_candidate,
                    source_family_candidate,
                    source_target_candidate,
                    source_type_candidate,
                    status,
                    risk_level,
                    notes,
                    updated_at
                ) VALUES (%s, %s, NULL, %s, %s, NULL, %s, 'discovery', %s, %s, now())
                RETURNING id
                """,
                (
                    item.company_key,
                    item.company_name,
                    item.source_name_candidate,
                    item.source_family_candidate,
                    item.source_type_candidate,
                    item.risk_level,
                    (
                        "Created by Freeze-II artifact-backed resolved candidate promotion; "
                        f"approved_by={approved_by}; review_run_id={review_run_id}; "
                        f"origin_run_id={origin_run_id}; pre_candidate_origin_url="
                        f"{origin.selected_url}; candidate_url intentionally NULL pending "
                        "existing validated Origin Source Discovery persistence authority."
                    ),
                ),
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError(
                    f"candidate insert returned no id for {item.company_key}"
                )
            created.append(
                {
                    "company_key": item.company_key,
                    "candidate_id": int(row["id"]),
                    "pre_candidate_origin_url": origin.selected_url,
                }
            )
    conn.commit()
    return created


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-json", type=Path, required=True)
    parser.add_argument("--origin-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-run-id", required=True)
    parser.add_argument("--origin-run-id", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-cohort-digest")
    parser.add_argument("--approved-by")
    args = parser.parse_args()

    review_payload = _load(args.review_json)
    origin_payload = _load(args.origin_json)

    initial_plan, initial_origins = build_resolved_promotion_plan(
        review_payload=review_payload,
        origin_payload=origin_payload,
    )
    immutable_digest = cohort_digest(initial_plan, initial_origins)

    existing_keys: set[str] = set()
    created: list[dict[str, object]] = []
    applied = False

    if args.apply:
        if not args.expected_cohort_digest:
            raise SystemExit("--apply requires --expected-cohort-digest")
        if args.expected_cohort_digest != immutable_digest:
            raise SystemExit(
                "ABORT: cohort digest mismatch; rerun dry-run and obtain fresh approval"
            )
        if not str(args.approved_by or "").strip():
            raise SystemExit("--apply requires --approved-by")

        with _connect() as conn:
            requested = tuple(initial_plan.requested_company_keys)
            existing_keys = _existing_company_keys(conn, requested)
            apply_plan, apply_origins = build_resolved_promotion_plan(
                review_payload=review_payload,
                origin_payload=origin_payload,
                existing_company_keys=existing_keys,
            )
            origin_by_key = {item.company_key: item for item in apply_origins}
            created = _create_candidates(
                conn,
                plan=apply_plan,
                origin_by_key=origin_by_key,
                approved_by=str(args.approved_by),
                review_run_id=str(args.review_run_id),
                origin_run_id=str(args.origin_run_id),
            )
            final_payload = report_payload(
                review_payload=review_payload,
                origin_payload=origin_payload,
                existing_company_keys=existing_keys,
            )
            applied = True
    else:
        final_payload = report_payload(
            review_payload=review_payload,
            origin_payload=origin_payload,
        )

    final_payload["review_run_id"] = str(args.review_run_id)
    final_payload["origin_run_id"] = str(args.origin_run_id)
    final_payload["immutable_cohort_digest"] = immutable_digest
    final_payload["apply"] = applied
    final_payload["existing_company_keys_at_apply"] = sorted(existing_keys)
    final_payload["created_candidates"] = created
    final_payload["boundary"]["database_writes"] = bool(applied and created)
    final_payload["boundary"]["candidate_creation"] = bool(applied and created)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(final_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = final_payload["summary"]
    print("============================================")
    print("FREEZE-II RESOLVED CANDIDATE PROMOTION")
    print("============================================")
    print(f"COHORT_DIGEST={immutable_digest}")
    print(f"RESOLVED_ORIGIN_COUNT={summary['resolved_origin_count']}")
    print(f"REQUESTED_COMPANY_COUNT={summary['requested_company_count']}")
    print(f"PLANNED_CREATE_COUNT={summary['planned_create_count']}")
    print(f"BLOCKED_OR_SKIPPED_COUNT={summary['blocked_or_skipped_count']}")
    print(f"APPLY={applied}")
    print(f"CREATED_CANDIDATE_COUNT={len(created)}")
    for item in final_payload["items"]:
        origin = item.get("resolved_origin") or {}
        print(
            "PLAN="
            f"{item['company_key']}|{item['action']}|"
            f"create_allowed={item['create_allowed']}|"
            f"origin={origin.get('selected_url') or '-'}"
        )
    print(f"artifact={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
