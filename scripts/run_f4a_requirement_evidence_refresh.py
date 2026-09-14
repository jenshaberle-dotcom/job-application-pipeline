"""Guarded F4A-Q refresh from current structured/contextual Origin evidence.

The runner is read/plan-only by default. Apply is explicit-token gated, atomic,
revision-audited and bounded to existing lifecycle-current, origin-validated
Product V1 assessment rows. It never reads Candidate Facts and never creates
capability-fit, ranking, Top-5 or application authority.

A successful refresh deliberately invalidates stale downstream decisions by
resetting capability fit, hard-filter state and ranking scores. Existing review
rows remain as history and become stale through the changed assessment timestamp.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from scripts.run_product_v1_assessment_materialization import ASSESSMENT_COLUMNS
from src.config import get_database_config
from src.search_intelligence.product_v1_downstream_preview import (
    DownstreamPreviewStop,
    fetch_public_https_detail_document,
)
from src.search_intelligence.product_v1_requirement_evidence import (
    ProductV1RequirementEvidence,
    extract_product_v1_requirement_evidence,
)


REPORT_SCHEMA = "job_application_pipeline.f4a_requirement_evidence_refresh.v1"
APPROVAL_TOKEN = "F4A-REQUIREMENT-EVIDENCE-REFRESH-001"
REVISION_PREFIX = "F4A-REQUIREMENT-EVIDENCE-REFRESH-001"
ASSESSED_BY = "deterministic_f4a_requirement_evidence_v1"
REVISION_TABLE = "job_product_assessment_revisions"


class RequirementEvidenceRefreshStop(RuntimeError):
    """Fail closed when the bounded Product refresh contract is not satisfied."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RequirementEvidenceRefreshStop(message)


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
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _fingerprint(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _same_origin(left: str, right: str) -> bool:
    left_url = urlparse(left)
    right_url = urlparse(right)
    return (
        left_url.scheme.casefold() == right_url.scheme.casefold() == "https"
        and bool(left_url.hostname)
        and bool(right_url.hostname)
        and left_url.hostname.casefold() == right_url.hostname.casefold()
        and (left_url.port or 443) == (right_url.port or 443)
    )


def _assessment_payload(row: Mapping[str, object]) -> dict[str, object]:
    return {column: _json_safe(row.get(column)) for column in ASSESSMENT_COLUMNS}


def _flat_explanations(evidence: ProductV1RequirementEvidence) -> list[dict[str, object]]:
    result = [
        {
            "factor": reference.field,
            "status": "source_observed",
            "canonical_value": reference.canonical_value,
            "evidence": reference.evidence,
            "source_url": reference.source_url,
            "span_start": reference.span_start,
            "span_end": reference.span_end,
        }
        for reference in evidence.assessment.references
    ]
    result.extend(
        {
            "factor": reference.field,
            "status": "contextual_source_observed",
            "canonical_value": reference.value,
            "evidence": reference.evidence,
            "source_url": reference.source_url,
            "span_start": reference.span_start,
            "span_end": reference.span_end,
        }
        for reference in evidence.semantic_references
    )
    return result


def _uncertainties(evidence: ProductV1RequirementEvidence) -> list[dict[str, object]]:
    result = [
        {
            "factor": field,
            "status": "unknown",
            "action": (
                "conflicting_source_evidence"
                if field in evidence.conflicted_fields
                else "deterministic_evidence_missing"
            ),
        }
        for field in evidence.unresolved_fields
    ]
    result.append(
        {
            "factor": "capability_fit",
            "status": "unknown",
            "action": "approved_candidate_fact_comparison_required",
        }
    )
    return result


def _build_next_payload(
    row: Mapping[str, object],
    *,
    evidence: ProductV1RequirementEvidence,
    final_url: str,
) -> dict[str, object]:
    patch = evidence.assessment_patch()
    current = _assessment_payload(row)
    ranking_factors = row.get("ranking_factors")
    _require(isinstance(ranking_factors, Mapping), "assessment ranking_factors are missing")
    refreshed_factors = dict(ranking_factors)
    refreshed_factors.update(
        {
            "source_evidence_only": True,
            "detail_description_sha256": evidence.assessment.description_sha256,
            "reference_count": (
                len(evidence.assessment.references) + len(evidence.semantic_references)
            ),
            "conflicted_fields": list(evidence.conflicted_fields),
            "requirement_evidence": evidence.canonical_payload(),
            "f4a_requirement_evidence_refresh": {
                "schema": REPORT_SCHEMA,
                "final_url": final_url,
            },
        }
    )

    next_payload = dict(current)
    next_payload.update(
        {
            "hard_filter_status": "unknown",
            "profile_direction_score": None,
            "data_focus_score": None,
            "reliability_focus_score": None,
            "evidence_quality_score": None,
            "overall_quality_score": None,
            "work_model": patch["work_model"],
            "ranking_factors": refreshed_factors,
            "explanations": _flat_explanations(evidence),
            "uncertainties": _uncertainties(evidence),
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
    return next_payload


def _load_rows(
    conn: psycopg.Connection[Any], *, for_update: bool = False
) -> list[dict[str, object]]:
    lock_clause = "FOR UPDATE OF assessment" if for_update else ""
    assessment_select = ",\n            ".join(
        f"assessment.{column} AS {column}" for column in ASSESSMENT_COLUMNS
    )
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                current_job.id AS current_silver_job_id,
                current_job.source_name,
                current_job.source_url,
                current_job.title,
                current_job.company_name,
                current_job.city,
                current_job.lifecycle_status,
                assessment.updated_at AS assessment_updated_at,
                {assessment_select}
            FROM gold_current_job_opportunities current_job
            JOIN job_product_assessments assessment
              ON assessment.silver_job_id = current_job.id
            WHERE assessment.origin_validation_status = 'validated'
              AND assessment.activity_status = 'active'
            ORDER BY current_job.source_name, current_job.id
            {lock_clause}
            """
        )
        return [dict(row) for row in cur.fetchall()]


def _build_proposal(row: Mapping[str, object]) -> dict[str, object]:
    silver_job_id = int(row.get("silver_job_id") or 0)
    _require(silver_job_id > 0, "assessment Silver binding is missing")
    _require(
        silver_job_id == int(row.get("current_silver_job_id") or 0),
        "current Product membership does not match assessment binding",
    )
    _require(str(row.get("lifecycle_status") or "") == "active_confirmed", "job is not lifecycle-current")
    source_url = str(row.get("source_url") or "").strip()
    _require(bool(source_url), "source URL is missing")
    document = fetch_public_https_detail_document(source_url)
    _require(_same_origin(source_url, document.final_url), "detail fetch redirected outside authorized origin")
    title = str(row.get("title") or document.title or "").strip()
    _require(bool(title), "job title is missing")

    evidence = extract_product_v1_requirement_evidence(
        html=document.html,
        text=document.text,
        title=title,
        page_title=document.title,
        source_url=document.final_url,
        target_location=str(row.get("city") or ""),
    )
    previous_payload = _assessment_payload(row)
    next_payload = _build_next_payload(row, evidence=evidence, final_url=document.final_url)
    changed_fields = tuple(
        column
        for column in ASSESSMENT_COLUMNS
        if _json_safe(previous_payload.get(column)) != _json_safe(next_payload.get(column))
    )
    evidence_fingerprint = _fingerprint(evidence.canonical_payload())
    revision_key = f"{REVISION_PREFIX}:{evidence_fingerprint[:24]}"
    return {
        "silver_job_id": silver_job_id,
        "source_name": row.get("source_name"),
        "title": title,
        "source_url": source_url,
        "final_url": document.final_url,
        "assessment_updated_at": _json_safe(row.get("assessment_updated_at")),
        "revision_key": revision_key,
        "evidence_fingerprint": evidence_fingerprint,
        "work_model_before": previous_payload.get("work_model"),
        "work_model_after": next_payload.get("work_model"),
        "work_model_resolution": evidence.work_model_resolution,
        "job_skill_count": len(evidence.job_skills),
        "job_skills": list(evidence.job_skills),
        "jsonld_jobposting_count": evidence.jsonld_jobposting_count,
        "requirements_seniority": next_payload.get("requirements_seniority"),
        "requirements_seniority_from_title": False,
        "changed_fields": list(changed_fields),
        "previous_payload": previous_payload,
        "next_payload": next_payload,
        "source_evidence": evidence.canonical_payload(),
        "would_change": bool(changed_fields),
    }


def build_plan(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    proposals: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []
    for row in rows:
        try:
            proposals.append(_build_proposal(row))
        except (RequirementEvidenceRefreshStop, DownstreamPreviewStop, ValueError) as exc:
            blocked.append(
                {
                    "silver_job_id": int(row.get("silver_job_id") or 0),
                    "source_name": row.get("source_name"),
                    "title": row.get("title"),
                    "reason": str(exc),
                }
            )

    fills = Counter(
        str(item.get("work_model_resolution") or "unknown") for item in proposals
    )
    return {
        "schema": REPORT_SCHEMA,
        "mode": "plan",
        "candidate_count": len(rows),
        "proposal_count": len(proposals),
        "blocked_count": len(blocked),
        "would_change_count": sum(1 for item in proposals if item["would_change"]),
        "jsonld_jobposting_count": sum(
            1 for item in proposals if int(item["jsonld_jobposting_count"]) > 0
        ),
        "jobs_with_skills": sum(1 for item in proposals if int(item["job_skill_count"]) > 0),
        "work_model_resolutions": dict(sorted(fills.items())),
        "proposals": proposals,
        "blocked": blocked,
        "boundaries": {
            "candidate_fact_reads": False,
            "database_writes": False,
            "provider_or_llm_requests": 0,
            "requirements_seniority_from_title": False,
            "capability_fit_authority": False,
            "ranking_authority": False,
            "top5_authority": False,
            "application_authority": False,
            "raw_html_persisted": False,
        },
    }


def _revision_exists(
    conn: psycopg.Connection[Any], *, silver_job_id: int, revision_key: str
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM job_product_assessment_revisions WHERE silver_job_id = %s AND revision_key = %s",
            (silver_job_id, revision_key),
        )
        return cur.fetchone() is not None


def _insert_revision(
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


def _update_assessment(
    conn: psycopg.Connection[Any], *, proposal: Mapping[str, object]
) -> None:
    payload = proposal["next_payload"]
    _require(isinstance(payload, Mapping), "proposal next payload is missing")
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE job_product_assessments
            SET hard_filter_status = 'unknown',
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
                "silver_job_id": proposal["silver_job_id"],
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


def apply_plan(
    *, plan: Mapping[str, object], applied_by: str
) -> dict[str, object]:
    _require(int(plan.get("blocked_count") or 0) == 0, "blocked cohort rows forbid Apply")
    raw_proposals = plan.get("proposals")
    _require(isinstance(raw_proposals, list), "plan proposals are missing")
    expected = {
        int(item["silver_job_id"]): item
        for item in raw_proposals
        if isinstance(item, Mapping) and item.get("would_change") is True
    }
    if not expected:
        return {"updated": 0, "already_current": 0}

    conn = psycopg.connect(**get_database_config(), row_factory=dict_row)
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                for relation in (REVISION_TABLE, "job_product_assessments"):
                    cur.execute("SELECT to_regclass(%s) AS relation", (f"public.{relation}",))
                    relation_row = cur.fetchone()
                    _require(
                        relation_row is not None and relation_row["relation"] is not None,
                        f"missing relation: {relation}",
                    )
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (REVISION_PREFIX,),
                )

            current_rows = _load_rows(conn, for_update=True)
            current_by_id = {int(row["silver_job_id"]): row for row in current_rows}
            _require(
                set(expected).issubset(current_by_id),
                "current assessed cohort changed before Apply",
            )

            updated = 0
            already_current = 0
            for silver_job_id, expected_proposal in expected.items():
                rebuilt = _build_proposal(current_by_id[silver_job_id])
                _require(
                    rebuilt["evidence_fingerprint"] == expected_proposal["evidence_fingerprint"],
                    f"requirement evidence changed before Apply: {silver_job_id}",
                )
                _require(
                    _json_safe(rebuilt["next_payload"])
                    == _json_safe(expected_proposal["next_payload"]),
                    f"assessment payload changed before Apply: {silver_job_id}",
                )
                revision_key = str(rebuilt["revision_key"])
                if _revision_exists(
                    conn,
                    silver_job_id=silver_job_id,
                    revision_key=revision_key,
                ):
                    already_current += 1
                    continue
                _insert_revision(conn, proposal=rebuilt, applied_by=applied_by)
                _update_assessment(conn, proposal=rebuilt)
                updated += 1
        return {"updated": updated, "already_current": already_current}
    finally:
        conn.close()


def _print_report(report: Mapping[str, object]) -> None:
    print("=== F4A-Q REQUIREMENT EVIDENCE REFRESH ===")
    for key in (
        "mode",
        "candidate_count",
        "proposal_count",
        "blocked_count",
        "would_change_count",
        "jsonld_jobposting_count",
        "jobs_with_skills",
    ):
        print(f"{key.upper()}={report.get(key)}")
    print(
        "WORK_MODEL_RESOLUTIONS="
        + json.dumps(report.get("work_model_resolutions", {}), sort_keys=True)
    )
    for item in report.get("blocked", []):
        print("BLOCKED=" + json.dumps(item, ensure_ascii=False, sort_keys=True))
    print("CANDIDATE_FACT_READS=0")
    print("REQUIREMENTS_SENIORITY_FROM_TITLE=0")
    print("PROVIDER_REQUESTS=0")
    print("RAW_HTML_PERSISTED=0")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--applied-by", default="f4a-q")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".runtime/demo/f4a_requirement_evidence_refresh.json"),
    )
    args = parser.parse_args(argv)
    if args.apply:
        _require(args.approval_token == APPROVAL_TOKEN, "invalid F4A refresh approval token")
    _require(bool(args.applied_by.strip()), "applied_by must not be blank")

    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        rows = _load_rows(conn)
        conn.rollback()
    _require(bool(rows), "no current Product assessment rows found")
    report = build_plan(rows)
    result = {"updated": 0, "already_current": 0}
    if args.apply:
        result = apply_plan(plan=report, applied_by=args.applied_by.strip())
        report = dict(report)
        report["mode"] = "apply"
        report["apply_result"] = result
        report["boundaries"] = {
            **dict(report["boundaries"]),
            "database_writes": bool(result["updated"]),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(_json_safe(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _print_report(report)
    if args.apply:
        print(f"UPDATED={result['updated']}")
        print(f"ALREADY_CURRENT={result['already_current']}")
    print(f"artifact={args.output.resolve()}")
    print("F4A_REQUIREMENT_EVIDENCE_REFRESH=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
