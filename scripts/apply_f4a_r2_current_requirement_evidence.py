"""Apply the exact F4A-R2 operator-review requirement plan to Product truth.

The apply path deliberately reuses the same read-only operator cohort and
job-evidence proposal logic qualified by the F4A-R2 preflight. It writes only
``job_product_assessments`` plus the existing revision ledger. Candidate Facts,
capability-fit, ranking, Top-5 and application authority are neither read nor
created. Raw Origin HTML remains memory-only.

Apply is explicit-token gated and transactionally revalidates current vacancy
membership, source URL/source identity and assessment revision state before each
write. Existing score/capability authority is invalidated to unknown whenever
job-side requirement evidence changes. Exact Origin 404 remains job-evidence
``unknown`` only; it never closes a vacancy.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from scripts import run_f4a_r2_current_requirement_origin_diagnostic as diagnostic
from scripts import run_f4a_r2_current_requirement_plan as plan
from scripts import run_f4a_requirement_evidence_refresh as refresh
from src.config import get_database_config


APPROVAL_TOKEN = "F4A-R2-CURRENT-REQUIREMENT-APPLY-001"
APPLY_LOCK = "F4A-R2-CURRENT-REQUIREMENT-APPLY-001"
JSON_FIELDS = frozenset(
    {"ranking_factors", "explanations", "uncertainties", "required_languages"}
)


class F4AR2ApplyStop(RuntimeError):
    """Fail closed when the qualified current-plan contract drifts before Apply."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise F4AR2ApplyStop(message)


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


def _db_payload(payload: Mapping[str, object]) -> dict[str, object]:
    result = dict(payload)
    for field in JSON_FIELDS:
        result[field] = Jsonb(payload[field])
    return result


def _load_exact_current_binding(
    conn: psycopg.Connection[Any], silver_job_id: int
) -> dict[str, object]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id AS silver_job_id, source_name, source_url, lifecycle_status
            FROM gold_current_job_opportunities
            WHERE id = %s
            """,
            (silver_job_id,),
        )
        row = cur.fetchone()
    _require(row is not None, f"job left current vacancy truth before Apply: {silver_job_id}")
    return dict(row)


def _lock_existing_assessment(
    conn: psycopg.Connection[Any], silver_job_id: int
) -> dict[str, object] | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT updated_at AS assessment_updated_at "
            "FROM job_product_assessments WHERE silver_job_id = %s FOR UPDATE",
            (silver_job_id,),
        )
        row = cur.fetchone()
    return dict(row) if row is not None else None


def _lock_silver(conn: psycopg.Connection[Any], silver_job_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM silver_jobs WHERE id = %s FOR UPDATE", (silver_job_id,))
        _require(cur.fetchone() is not None, f"Silver row disappeared before Apply: {silver_job_id}")


def _revision_exists(
    conn: psycopg.Connection[Any], *, silver_job_id: int, revision_key: str
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM job_product_assessment_revisions "
            "WHERE silver_job_id = %s AND revision_key = %s",
            (silver_job_id, revision_key),
        )
        return cur.fetchone() is not None


def _write_revision(
    conn: psycopg.Connection[Any], *, proposal: Mapping[str, object], applied_by: str
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO job_product_assessment_revisions (
                silver_job_id, revision_key, previous_payload, next_payload,
                source_evidence, applied_by
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                proposal["silver_job_id"],
                proposal["revision_key"],
                Jsonb(dict(proposal["previous_payload"])),
                Jsonb(dict(proposal["next_payload"])),
                Jsonb(dict(proposal["source_evidence"])),
                applied_by,
            ),
        )


def _insert_assessment(
    conn: psycopg.Connection[Any], payload: Mapping[str, object]
) -> None:
    columns = ", ".join(refresh.ASSESSMENT_COLUMNS)
    placeholders = ", ".join(f"%({column})s" for column in refresh.ASSESSMENT_COLUMNS)
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO job_product_assessments ({columns}) VALUES ({placeholders})",
            _db_payload(payload),
        )
        _require(cur.rowcount == 1, "assessment insert did not write exactly one row")


def _update_assessment(
    conn: psycopg.Connection[Any], payload: Mapping[str, object]
) -> None:
    mutable = [column for column in refresh.ASSESSMENT_COLUMNS if column != "silver_job_id"]
    assignments = ",\n                ".join(f"{column} = %({column})s" for column in mutable)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE job_product_assessments
            SET {assignments},
                ranking_updated_at = NULL,
                updated_at = now()
            WHERE silver_job_id = %(silver_job_id)s
            """,
            _db_payload(payload),
        )
        _require(cur.rowcount == 1, "assessment update did not write exactly one row")


def _build_fresh_plan() -> dict[str, object]:
    """Rebuild the already-qualified exact operator-review plan at Apply time."""

    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        rows = diagnostic._operator_review_rows(conn)
        authorized_sources = diagnostic._current_product_sources(conn)
        ranking_version, hard_filter_version = plan._load_policy_versions(conn)
        conn.rollback()
    _require(bool(rows), "operator review scope is empty")

    canonical_proposal = plan._proposal
    try:
        plan._proposal = diagnostic._proposal_with_explicit_unavailable
        report = plan.build_plan(
            rows,
            authorized_sources=authorized_sources,
            ranking_policy_version=ranking_version,
            hard_filter_policy_version=hard_filter_version,
        )
    finally:
        plan._proposal = canonical_proposal
    _require(int(report.get("blocked_count") or 0) == 0, "blocked current rows forbid Apply")
    _require(
        int(report.get("proposal_count") or 0) == int(report.get("candidate_count") or -1),
        "current cohort is not fully reconciled",
    )
    return report


def apply_report(report: Mapping[str, object], *, applied_by: str) -> dict[str, int]:
    raw = report.get("proposals")
    _require(isinstance(raw, list), "plan proposals missing")
    proposals = [item for item in raw if isinstance(item, Mapping)]
    inserted = updated = already_current = 0

    conn = psycopg.connect(**get_database_config(), row_factory=dict_row)
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT to_regclass('public.job_product_assessment_revisions') AS relation"
                )
                relation = cur.fetchone()
                _require(
                    relation is not None and relation["relation"] is not None,
                    "revision table missing",
                )
                cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (APPLY_LOCK,))

            for proposal in proposals:
                silver_job_id = int(proposal["silver_job_id"])
                binding = _load_exact_current_binding(conn, silver_job_id)
                _require(
                    str(binding.get("lifecycle_status") or "") == "active_confirmed",
                    f"job is no longer active-current: {silver_job_id}",
                )
                _require(
                    str(binding.get("source_name") or "")
                    == str(proposal.get("source_name") or ""),
                    f"source identity changed before Apply: {silver_job_id}",
                )
                _require(
                    str(binding.get("source_url") or "")
                    == str(proposal.get("source_url") or ""),
                    f"source URL changed before Apply: {silver_job_id}",
                )

                revision_key = str(proposal["revision_key"])
                if _revision_exists(
                    conn, silver_job_id=silver_job_id, revision_key=revision_key
                ):
                    already_current += 1
                    continue

                mode = str(proposal.get("mode") or "")
                next_payload = proposal.get("next_payload")
                _require(isinstance(next_payload, Mapping), "next assessment payload missing")
                if mode == "update":
                    current = _lock_existing_assessment(conn, silver_job_id)
                    _require(current is not None, f"assessment disappeared before Apply: {silver_job_id}")
                    _require(
                        _json_safe(current.get("assessment_updated_at"))
                        == proposal.get("assessment_updated_at"),
                        f"assessment changed before Apply: {silver_job_id}",
                    )
                    _write_revision(conn, proposal=proposal, applied_by=applied_by)
                    _update_assessment(conn, next_payload)
                    updated += 1
                    continue

                _require(mode == "insert", f"unsupported proposal mode: {mode}")
                _lock_silver(conn, silver_job_id)
                _require(
                    _lock_existing_assessment(conn, silver_job_id) is None,
                    f"assessment appeared before Apply: {silver_job_id}",
                )
                _insert_assessment(conn, next_payload)
                _write_revision(conn, proposal=proposal, applied_by=applied_by)
                inserted += 1
    finally:
        conn.close()

    return {
        "inserted": inserted,
        "updated": updated,
        "already_current": already_current,
    }


def verify_persisted(report: Mapping[str, object]) -> dict[str, int]:
    proposals = [
        item for item in report.get("proposals", []) if isinstance(item, Mapping)
    ]
    expected = {int(item["silver_job_id"]): item for item in proposals}
    _require(bool(expected), "verification cohort is empty")
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT silver_job_id, policy_version, assessed_by, hard_filter_status,
                       capability_fit_status, profile_direction_score, data_focus_score,
                       reliability_focus_score, evidence_quality_score, overall_quality_score,
                       ranking_factors, explanations, uncertainties
                FROM job_product_assessments
                WHERE silver_job_id = ANY(%s)
                """,
                (list(expected),),
            )
            rows = {int(row["silver_job_id"]): dict(row) for row in cur.fetchall()}
        conn.rollback()
    _require(set(rows) == set(expected), "not every current proposal persisted")

    unavailable = verified_lines = 0
    for silver_job_id, row in rows.items():
        proposal = expected[silver_job_id]
        expected_payload = proposal["next_payload"]
        _require(
            str(row.get("assessed_by") or "") == plan.ASSESSED_BY,
            f"wrong F4A-R2 assessor persisted: {silver_job_id}",
        )
        _require(
            str(row.get("policy_version") or "")
            == str(expected_payload.get("policy_version") or ""),
            f"job-evidence policy mismatch after Apply: {silver_job_id}",
        )
        _require(
            str(row.get("hard_filter_status") or "") == "unknown"
            and str(row.get("capability_fit_status") or "") == "unknown",
            f"stale downstream authority survived Apply: {silver_job_id}",
        )
        for score in (
            "profile_direction_score",
            "data_focus_score",
            "reliability_focus_score",
            "evidence_quality_score",
            "overall_quality_score",
        ):
            _require(row.get(score) is None, f"stale score survived Apply: {silver_job_id}:{score}")
        factors = row.get("ranking_factors")
        _require(isinstance(factors, Mapping), f"ranking_factors missing: {silver_job_id}")
        marker = factors.get("f4a_r2_requirement_evidence")
        _require(isinstance(marker, Mapping), f"F4A-R2 marker missing: {silver_job_id}")
        if str(marker.get("status") or "") == "origin_detail_unavailable":
            unavailable += 1
        if row.get("explanations"):
            verified_lines += 1

    return {
        "persisted": len(rows),
        "with_verified_lines": verified_lines,
        "origin_detail_unavailable": unavailable,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--applied-by", default="f4a-r2-current")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".runtime/demo/f4a_r2_current_requirement_apply.json"),
    )
    args = parser.parse_args(argv)
    _require(args.apply, "this runner requires explicit --apply")
    _require(args.approval_token == APPROVAL_TOKEN, "invalid F4A-R2 apply token")
    _require(bool(args.applied_by.strip()), "applied_by must not be blank")

    report = _build_fresh_plan()
    result = apply_report(report, applied_by=args.applied_by.strip())
    verification = verify_persisted(report)
    output = {
        "schema": "job_application_pipeline.f4a_r2_current_requirement_apply.v1",
        "mode": "apply",
        "candidate_count": report["candidate_count"],
        "proposal_count": report["proposal_count"],
        "blocked_count": report["blocked_count"],
        "apply_result": result,
        "verification": verification,
        "ranking_policy_version": report["ranking_policy_version"],
        "job_evidence_policy_version": report["job_evidence_policy_version"],
        "boundaries": {
            "candidate_fact_reads": False,
            "provider_or_llm_requests": 0,
            "raw_html_persisted": False,
            "capability_fit_authority": False,
            "ranking_authority": False,
            "top5_authority": False,
            "application_authority": False,
            "database_writes": bool(result["inserted"] or result["updated"]),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(_json_safe(output), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("=== F4A-R2 CURRENT REQUIREMENT APPLY ===")
    print(f"CANDIDATE_COUNT={output['candidate_count']}")
    print(f"PROPOSAL_COUNT={output['proposal_count']}")
    print(f"BLOCKED_COUNT={output['blocked_count']}")
    print(f"INSERTED={result['inserted']}")
    print(f"UPDATED={result['updated']}")
    print(f"ALREADY_CURRENT={result['already_current']}")
    print(f"PERSISTED={verification['persisted']}")
    print(f"WITH_VERIFIED_LINES={verification['with_verified_lines']}")
    print(f"ORIGIN_DETAIL_UNAVAILABLE={verification['origin_detail_unavailable']}")
    print("CANDIDATE_FACT_READS=0")
    print("RANKING_AUTHORITY=0")
    print("TOP5_AUTHORITY=0")
    print("APPLICATION_AUTHORITY=0")
    print("RAW_HTML_PERSISTED=0")
    print(f"artifact={args.output.resolve()}")
    print("F4A_R2_CURRENT_REQUIREMENT_APPLY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
