"""Guarded refresh of an existing Product V1 assessment from current origin detail.

This runner exists for the normal case where a live employer-origin vacancy changes
after initial Product V1 assessment materialization. It is plan-only by default.
Apply is approval-token gated, revision-audited and bounded to existing active,
validated jobs from active recurring employer-origin sources.

A detail refresh deliberately invalidates downstream human decisions by resetting
candidate capability fit, hard-filter state and ranking scores. Existing review rows
are not deleted: their assessment-version bindings become stale when ``updated_at``
changes, preserving audit history while forcing explicit replay of the gates.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from scripts.run_product_v1_assessment_materialization import (
    ASSESSMENT_COLUMNS,
    _evidence_explanations,
    _evidence_uncertainties,
    authorized_recurring_employer_origin_sources,
)
from src.config import get_database_config
from src.ingestion.repository import JobIngestionRepository
from src.search_intelligence.product_v1_assessment_evidence import (
    ProductV1AssessmentEvidence,
    extract_product_v1_assessment_evidence,
)
from src.search_intelligence.product_v1_downstream_preview import (
    fetch_public_https_detail_text,
)

REPORT_SCHEMA = "job_application_pipeline.product_v1_assessment_detail_refresh.v1"
APPROVAL_TOKEN = "PRODUCT-V1-ASSESSMENT-DETAIL-REFRESH-001"
REFRESH_KEY_PREFIX = "PRODUCT-V1-ASSESSMENT-DETAIL-REFRESH-001"
ASSESSED_BY = "deterministic_assessment_detail_refresh_v1"
REVISION_TABLE = "job_product_assessment_revisions"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class AssessmentDetailRefreshStop(RuntimeError):
    """Fail closed when current authority cannot admit an assessment refresh."""


@dataclass(frozen=True)
class RefreshPlan:
    silver_job_id: int
    source_name: str
    title: str
    source_url: str
    final_url: str
    previous_detail_sha256: str
    next_detail_sha256: str
    revision_key: str
    changed_fields: tuple[str, ...]
    previous_payload: Mapping[str, object]
    next_payload: Mapping[str, object]
    source_evidence: Mapping[str, object]
    would_change: bool


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssessmentDetailRefreshStop(message)


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


def _assessment_payload(row: Mapping[str, object]) -> dict[str, object]:
    return {column: _json_safe(row.get(column)) for column in ASSESSMENT_COLUMNS}


def _detail_sha(row: Mapping[str, object]) -> str:
    ranking_factors = row.get("ranking_factors")
    _require(isinstance(ranking_factors, Mapping), "assessment ranking_factors are missing")
    value = str(ranking_factors.get("detail_description_sha256") or "").strip()
    _require(_SHA256_RE.fullmatch(value) is not None, "assessment detail fingerprint is missing")
    return value


def _refresh_ranking_factors(
    current: Mapping[str, object],
    *,
    previous_detail_sha256: str,
    evidence: ProductV1AssessmentEvidence,
    final_url: str,
) -> dict[str, object]:
    ranking_factors = current.get("ranking_factors")
    _require(isinstance(ranking_factors, Mapping), "assessment ranking_factors are missing")
    refreshed = dict(ranking_factors)
    refreshed.update(
        {
            "source_evidence_only": True,
            "detail_description_sha256": evidence.description_sha256,
            "reference_count": len(evidence.references),
            "conflicted_fields": list(evidence.conflicted_fields),
            "detail_refresh": {
                "schema": REPORT_SCHEMA,
                "previous_detail_sha256": previous_detail_sha256,
                "current_detail_sha256": evidence.description_sha256,
                "final_url": final_url,
            },
        }
    )
    return refreshed


def validate_refresh_authority(
    row: Mapping[str, object],
    *,
    authorized_sources: Sequence[str],
) -> None:
    _require(
        str(row.get("source_name") or "") in {str(value) for value in authorized_sources},
        "source lacks active recurring employer-origin profile authority",
    )
    _require(str(row.get("lifecycle_status") or "") == "active_confirmed", "current active lifecycle authority is required")
    _require(str(row.get("origin_validation_status") or "") == "validated", "job origin is not validated")
    _require(str(row.get("activity_status") or "") == "active", "job is not active")
    _require(bool(str(row.get("source_url") or "").strip()), "Silver source URL is missing")
    _require(bool(str(row.get("title") or "").strip()), "Silver job title is missing")
    _detail_sha(row)


def build_refresh_plan(
    *,
    row: Mapping[str, object],
    authorized_sources: Sequence[str],
    final_url: str,
    detail_text: str,
) -> RefreshPlan:
    validate_refresh_authority(row, authorized_sources=authorized_sources)
    source_url = str(row.get("source_url") or "").strip()
    _require(_same_origin(source_url, final_url), "detail fetch redirected outside the authorized origin")
    _require(bool(detail_text.strip()), "current detail evidence is empty")

    previous_sha = _detail_sha(row)
    evidence = extract_product_v1_assessment_evidence(
        description=detail_text,
        title=str(row.get("title") or "").strip(),
        source_url=final_url,
    )
    next_sha = evidence.description_sha256
    patch = evidence.assessment_patch()

    previous_payload = _assessment_payload(row)
    next_payload = dict(previous_payload)
    next_payload.update(
        {
            "hard_filter_status": "unknown",
            "profile_direction_score": None,
            "data_focus_score": None,
            "reliability_focus_score": None,
            "evidence_quality_score": None,
            "overall_quality_score": None,
            "work_model": patch["work_model"],
            "ranking_factors": _refresh_ranking_factors(
                row,
                previous_detail_sha256=previous_sha,
                evidence=evidence,
                final_url=final_url,
            ),
            "explanations": _evidence_explanations(evidence),
            "uncertainties": _evidence_uncertainties(evidence),
            "assessed_by": ASSESSED_BY,
            "employment_type": patch["employment_type"],
            "employment_evidence_status": patch["employment_evidence_status"],
            "required_languages": patch["required_languages"],
            "language_evidence_status": patch["language_evidence_status"],
            "weekly_hours_min": patch["weekly_hours_min"],
            "weekly_hours_max": patch["weekly_hours_max"],
            "weekly_hours_evidence_status": patch["weekly_hours_evidence_status"],
            "title_seniority": patch["title_seniority"],
            "requirements_seniority": patch["requirements_seniority"],
            "capability_fit_status": "unknown",
            "seniority_evidence_status": patch["seniority_evidence_status"],
        }
    )
    changed_fields = tuple(
        key
        for key in ASSESSMENT_COLUMNS
        if _json_safe(previous_payload.get(key)) != _json_safe(next_payload.get(key))
    )
    revision_key = f"{REFRESH_KEY_PREFIX}:{previous_sha[:12]}:{next_sha[:12]}"
    source_evidence = {
        "schema": REPORT_SCHEMA,
        "source_url": source_url,
        "final_url": final_url,
        "previous_detail_sha256": previous_sha,
        "current_detail_sha256": next_sha,
        "assessment_evidence": evidence.canonical_payload(),
    }
    return RefreshPlan(
        silver_job_id=int(row["silver_job_id"]),
        source_name=str(row.get("source_name") or ""),
        title=str(row.get("title") or ""),
        source_url=source_url,
        final_url=final_url,
        previous_detail_sha256=previous_sha,
        next_detail_sha256=next_sha,
        revision_key=revision_key,
        changed_fields=changed_fields,
        previous_payload=previous_payload,
        next_payload=next_payload,
        source_evidence=source_evidence,
        would_change=previous_sha != next_sha,
    )


def ensure_schema(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        for relation in (REVISION_TABLE, "job_product_assessments", "gold_product_v1_job_readiness"):
            cur.execute("SELECT to_regclass(%s) AS relation", (f"public.{relation}",))
            row = cur.fetchone()
            _require(row is not None and row["relation"] is not None, f"missing relation: {relation}")


def load_current_row(
    conn: psycopg.Connection[Any],
    *,
    silver_job_id: int,
    for_update: bool = False,
) -> Mapping[str, Any]:
    lock_clause = "FOR UPDATE OF assessment" if for_update else ""
    assessment_select = ",\n                ".join(
        f"assessment.{column} AS {column}" for column in ASSESSMENT_COLUMNS
    )
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                readiness.silver_job_id,
                readiness.source_name,
                readiness.title,
                readiness.source_url,
                readiness.lifecycle_status,
                {assessment_select}
            FROM gold_product_v1_job_readiness readiness
            JOIN job_product_assessments assessment
              ON assessment.silver_job_id = readiness.silver_job_id
            WHERE readiness.silver_job_id = %s
            {lock_clause}
            """,
            (silver_job_id,),
        )
        row = cur.fetchone()
    _require(row is not None, f"Product V1 assessment is missing: {silver_job_id}")
    return row


def _insert_revision(
    conn: psycopg.Connection[Any],
    *,
    plan: RefreshPlan,
    applied_by: str,
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
                plan.silver_job_id,
                plan.revision_key,
                Jsonb(dict(plan.previous_payload)),
                Jsonb(dict(plan.next_payload)),
                Jsonb(dict(plan.source_evidence)),
                applied_by,
            ),
        )


def _revision_exists(conn: psycopg.Connection[Any], *, plan: RefreshPlan) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM job_product_assessment_revisions WHERE silver_job_id = %s AND revision_key = %s",
            (plan.silver_job_id, plan.revision_key),
        )
        return cur.fetchone() is not None


def _update_assessment(conn: psycopg.Connection[Any], *, plan: RefreshPlan) -> None:
    payload = plan.next_payload
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE job_product_assessments
            SET hard_filter_status = %(hard_filter_status)s,
                profile_direction_score = NULL,
                data_focus_score = NULL,
                reliability_focus_score = NULL,
                evidence_quality_score = NULL,
                overall_quality_score = NULL,
                work_model = %(work_model)s,
                ranking_factors = %(ranking_factors)s,
                explanations = %(explanations)s,
                uncertainties = %(uncertainties)s,
                assessed_by = %(assessed_by)s,
                employment_type = %(employment_type)s,
                employment_evidence_status = %(employment_evidence_status)s,
                required_languages = %(required_languages)s,
                language_evidence_status = %(language_evidence_status)s,
                weekly_hours_min = %(weekly_hours_min)s,
                weekly_hours_max = %(weekly_hours_max)s,
                weekly_hours_evidence_status = %(weekly_hours_evidence_status)s,
                title_seniority = %(title_seniority)s,
                requirements_seniority = %(requirements_seniority)s,
                capability_fit_status = 'unknown',
                seniority_evidence_status = %(seniority_evidence_status)s,
                ranking_updated_at = NULL,
                updated_at = now()
            WHERE silver_job_id = %(silver_job_id)s
            """,
            {
                "silver_job_id": plan.silver_job_id,
                "hard_filter_status": payload["hard_filter_status"],
                "work_model": payload["work_model"],
                "ranking_factors": Jsonb(payload["ranking_factors"]),
                "explanations": Jsonb(payload["explanations"]),
                "uncertainties": Jsonb(payload["uncertainties"]),
                "assessed_by": payload["assessed_by"],
                "employment_type": payload["employment_type"],
                "employment_evidence_status": payload["employment_evidence_status"],
                "required_languages": Jsonb(payload["required_languages"]),
                "language_evidence_status": payload["language_evidence_status"],
                "weekly_hours_min": payload["weekly_hours_min"],
                "weekly_hours_max": payload["weekly_hours_max"],
                "weekly_hours_evidence_status": payload["weekly_hours_evidence_status"],
                "title_seniority": payload["title_seniority"],
                "requirements_seniority": payload["requirements_seniority"],
                "seniority_evidence_status": payload["seniority_evidence_status"],
            },
        )
        _require(cur.rowcount == 1, "assessment refresh did not update exactly one row")


def apply_refresh(
    conn: psycopg.Connection[Any],
    *,
    expected_plan: RefreshPlan,
    authorized_sources: Sequence[str],
    applied_by: str,
) -> bool:
    if not expected_plan.would_change:
        return False
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (f"{REFRESH_KEY_PREFIX}:{expected_plan.silver_job_id}",),
        )
    current = load_current_row(conn, silver_job_id=expected_plan.silver_job_id, for_update=True)
    final_url, _page_title, detail_text = fetch_public_https_detail_text(str(current["source_url"]))
    rebuilt = build_refresh_plan(
        row=current,
        authorized_sources=authorized_sources,
        final_url=final_url,
        detail_text=detail_text,
    )
    _require(rebuilt.revision_key == expected_plan.revision_key, "detail refresh changed between plan and Apply")
    _require(
        _json_safe(rebuilt.next_payload) == _json_safe(expected_plan.next_payload),
        "assessment refresh payload changed between plan and Apply",
    )
    _require(not _revision_exists(conn, plan=rebuilt), "assessment refresh revision already exists before Apply")
    _insert_revision(conn, plan=rebuilt, applied_by=applied_by)
    _update_assessment(conn, plan=rebuilt)
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--silver-job-id", type=int, required=True)
    parser.add_argument("--applied-by", default="jens")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".runtime/demo/product_v1_assessment_detail_refresh.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    _require(args.silver_job_id > 0, "silver_job_id must be positive")
    applied_by = args.applied_by.strip()
    _require(bool(applied_by), "applied_by must not be blank")
    if args.apply:
        _require(args.approval_token == APPROVAL_TOKEN, "invalid assessment detail refresh approval token")

    authorized_sources = authorized_recurring_employer_origin_sources(JobIngestionRepository())
    conn = connect()
    try:
        ensure_schema(conn)
        row = load_current_row(conn, silver_job_id=args.silver_job_id)
        final_url, _page_title, detail_text = fetch_public_https_detail_text(str(row["source_url"]))
        plan = build_refresh_plan(
            row=row,
            authorized_sources=authorized_sources,
            final_url=final_url,
            detail_text=detail_text,
        )
        conn.rollback()
        changed = False
        if args.apply:
            changed = apply_refresh(
                conn,
                expected_plan=plan,
                authorized_sources=authorized_sources,
                applied_by=applied_by,
            )
            conn.commit()
        after = load_current_row(conn, silver_job_id=args.silver_job_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT hard_filter_status, operator_review_valid
                FROM gold_product_v1_hard_filter_evaluation
                WHERE silver_job_id = %s
                """,
                (args.silver_job_id,),
            )
            hard_filter_after = cur.fetchone()
        conn.rollback()
    finally:
        conn.close()

    report = {
        "schema": REPORT_SCHEMA,
        "mode": "apply" if args.apply else "plan",
        "silver_job_id": plan.silver_job_id,
        "source_name": plan.source_name,
        "title": plan.title,
        "previous_detail_sha256": plan.previous_detail_sha256,
        "current_detail_sha256": plan.next_detail_sha256,
        "revision_key": plan.revision_key,
        "changed_fields": list(plan.changed_fields),
        "would_change": plan.would_change,
        "changed": changed,
        "post_apply": {
            "capability_fit_status": after.get("capability_fit_status"),
            "hard_filter_status": hard_filter_after.get("hard_filter_status") if hard_filter_after else None,
            "operator_review_valid": hard_filter_after.get("operator_review_valid") if hard_filter_after else None,
            "ranking_scores_present": any(
                after.get(key) is not None
                for key in (
                    "profile_direction_score",
                    "data_focus_score",
                    "reliability_focus_score",
                    "evidence_quality_score",
                    "overall_quality_score",
                )
            ),
        },
        "boundaries": {
            "bounded_origin_detail_reads": 2 if args.apply and plan.would_change else 1,
            "database_writes": bool(args.apply and changed),
            "revision_audit_inserted": bool(args.apply and changed),
            "capability_fit_reset": bool(args.apply and changed),
            "hard_filter_review_deleted": False,
            "capability_fit_review_deleted": False,
            "ranking_reset": bool(args.apply and changed),
            "direct_rank_or_top5_writes": False,
            "provider_or_llm_requests": 0,
            "application_or_submission_actions": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(_json_safe(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("============================================")
    print("PRODUCT V1 ASSESSMENT DETAIL REFRESH")
    print("============================================")
    print(f"MODE={report['mode']}")
    print(f"JOB={plan.silver_job_id}|{plan.source_name}|{plan.title}")
    print(f"DETAIL_SHA={plan.previous_detail_sha256}->{plan.next_detail_sha256}")
    print(f"WOULD_CHANGE={str(plan.would_change).lower()}")
    print(f"CHANGED={str(changed).lower()}")
    print(f"CHANGED_FIELDS={','.join(plan.changed_fields)}")
    if args.apply:
        print(f"CAPABILITY_FIT_AFTER={report['post_apply']['capability_fit_status']}")
        print(f"HARD_FILTER_AFTER={report['post_apply']['hard_filter_status']}")
        print(f"HARD_FILTER_REVIEW_VALID_AFTER={report['post_apply']['operator_review_valid']}")
        print(f"RANKING_SCORES_PRESENT_AFTER={str(report['post_apply']['ranking_scores_present']).lower()}")
    print("PROVIDER_REQUESTS=0")
    print(f"artifact={args.output.resolve()}")
    print("PRODUCT_V1_ASSESSMENT_DETAIL_REFRESH=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
