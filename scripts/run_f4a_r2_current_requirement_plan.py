"""Plan F4A-R2 job-side requirement evidence for every current Product job.

This is the durable read-only preflight for the installed-v1.0.26 operator
rejection. It deliberately separates three authorities:

* Employer-Origin admission: an active-controlled source candidate or the generic
  proof=PASS active-source projection;
* current vacancy truth: membership in ``gold_current_job_opportunities``;
* job-side requirement evidence: the exact current Origin detail document.

Candidate Facts, capability fit, ranking, Top-5 and application authority are not
read or created. Raw detail HTML stays memory-only.
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

from scripts import run_f4a_requirement_evidence_refresh as refresh
from scripts.run_f4a_r2_requirement_reconcile import build_operator_requirement_lines
from src.config import get_database_config
from src.search_intelligence.product_v1_downstream_preview import (
    DownstreamPreviewStop,
    fetch_public_https_detail_document,
)
from src.search_intelligence.product_v1_requirement_evidence import (
    ProductV1RequirementEvidence,
    extract_product_v1_requirement_evidence,
)


REPORT_SCHEMA = "job_application_pipeline.f4a_r2_current_requirement_plan.v2"
ASSESSED_BY = "deterministic_f4a_r2_requirement_evidence_v2"
PRESENTATION_SCHEMA = "operator_requirement_lines/v1"
REVISION_PREFIX = "F4A-R2-REQUIREMENT-EVIDENCE-002"


class CurrentRequirementPlanStop(RuntimeError):
    """Fail closed when one authority boundary is not satisfied."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CurrentRequirementPlanStop(message)


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
        _json_safe(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _fingerprint(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


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


def _load_policy_versions(conn: psycopg.Connection[Any]) -> tuple[str, str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ranking.status AS ranking_status,
                   ranking.policy_version AS ranking_version,
                   hard_filter.status AS hard_filter_status,
                   hard_filter.policy_version AS hard_filter_version
            FROM product_v1_ranking_policy ranking
            CROSS JOIN product_v1_hard_filter_policy hard_filter
            WHERE ranking.policy_key = 'default'
              AND hard_filter.policy_key = 'default'
            """
        )
        row = cur.fetchone()
    _require(row is not None, "Product policies are missing")
    _require(str(row["ranking_status"] or "") == "approved", "ranking policy is not approved")
    _require(str(row["hard_filter_status"] or "") == "approved", "hard-filter policy is not approved")
    ranking_version = str(row["ranking_version"] or "").strip()
    hard_filter_version = str(row["hard_filter_version"] or "").strip()
    _require(bool(ranking_version), "ranking policy version is missing")
    _require(bool(hard_filter_version), "hard-filter policy version is missing")
    return ranking_version, hard_filter_version


def _load_authorized_sources(conn: psycopg.Connection[Any]) -> dict[str, str]:
    """Load DB-backed Employer-Origin source admission without connector imports."""

    result: dict[str, str] = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source_name_candidate AS source_name
            FROM employer_origin_source_candidates
            WHERE status = 'active_controlled'
              AND source_name_candidate IS NOT NULL
              AND btrim(source_name_candidate) <> ''
            """
        )
        for row in cur.fetchall():
            result[str(row["source_name"])] = "active_controlled_candidate"

        cur.execute("SELECT to_regclass('public.generic_employer_origin_active_sources') AS relation")
        relation = cur.fetchone()
        if relation is not None and relation["relation"] is not None:
            cur.execute(
                """
                SELECT source_name
                FROM generic_employer_origin_active_sources
                WHERE proof_state = 'pass'
                  AND authority = 'generic_evidence_driven_layer_model'
                """
            )
            for row in cur.fetchall():
                result[str(row["source_name"])] = "generic_proof_pass_active_source"
    return result


def _load_current_rows(conn: psycopg.Connection[Any]) -> list[dict[str, object]]:
    assessment_select = ",\n                ".join(
        f"assessment.{column} AS {column}" for column in refresh.ASSESSMENT_COLUMNS
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
                current_job.country,
                current_job.canonical_source_type,
                current_job.lifecycle_status,
                current_job.lifecycle_evidence_reason,
                current_job.latest_health_outcome,
                current_job.latest_health_coverage,
                assessment.updated_at AS assessment_updated_at,
                {assessment_select}
            FROM gold_current_job_opportunities current_job
            LEFT JOIN job_product_assessments assessment
              ON assessment.silver_job_id = current_job.id
            ORDER BY current_job.source_name, current_job.id
            """
        )
        return [dict(row) for row in cur.fetchall()]


def _assessment_payload(row: Mapping[str, object]) -> dict[str, object]:
    return {column: _json_safe(row.get(column)) for column in refresh.ASSESSMENT_COLUMNS}


def _decorate(
    payload: Mapping[str, object],
    *,
    evidence: ProductV1RequirementEvidence,
    final_url: str,
    source_authority: str,
    ranking_policy_version: str,
    hard_filter_policy_version: str,
) -> dict[str, object]:
    result = dict(payload)
    patch = evidence.assessment_patch()
    evidence_payload = evidence.canonical_payload()
    verified, unknown = build_operator_requirement_lines(evidence_payload)
    factors = dict(result.get("ranking_factors") or {})
    factors.update(
        {
            "source_evidence_only": True,
            "detail_description_sha256": evidence.assessment.description_sha256,
            "reference_count": len(evidence.assessment.references)
            + len(evidence.semantic_references),
            "conflicted_fields": list(evidence.conflicted_fields),
            "requirement_evidence": evidence_payload,
            "f4a_r2_requirement_evidence": {
                "schema": REPORT_SCHEMA,
                "presentation_schema": PRESENTATION_SCHEMA,
                "final_url": final_url,
                "source_authority": source_authority,
                "job_evidence_policy_version": hard_filter_policy_version,
                "ranking_policy_version_independent": ranking_policy_version,
            },
        }
    )
    result.update(
        {
            "hard_filter_status": "unknown",
            "profile_direction_score": None,
            "data_focus_score": None,
            "reliability_focus_score": None,
            "evidence_quality_score": None,
            "overall_quality_score": None,
            "work_model": patch["work_model"],
            "ranking_factors": factors,
            "explanations": verified,
            "uncertainties": unknown,
            "policy_key": "default",
            # Assessment/job-evidence policy binds to hard-filter semantics.
            # Ranking policy is separately versioned in ranking_factors above.
            "policy_version": hard_filter_policy_version,
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
    return result


def _new_assessment_shell(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "silver_job_id": int(row["current_silver_job_id"]),
        "origin_validation_status": "validated",
        "activity_status": "active",
        "hard_filter_status": "unknown",
        "profile_direction_score": None,
        "data_focus_score": None,
        "reliability_focus_score": None,
        "evidence_quality_score": None,
        "overall_quality_score": None,
        "work_model": "unknown",
        "commute_minutes": None,
        "public_transport_quality": "unknown",
        "ranking_factors": {},
        "explanations": [],
        "uncertainties": [],
        "policy_key": "default",
        "policy_version": None,
        "assessed_by": ASSESSED_BY,
        "employment_type": "unknown",
        "employment_evidence_status": "unknown",
        "required_languages": [],
        "language_evidence_status": "unknown",
        "weekly_hours_min": None,
        "weekly_hours_max": None,
        "weekly_hours_evidence_status": "unknown",
        "salary_min_gross_eur": None,
        "salary_max_gross_eur": None,
        "salary_evidence_status": "unknown",
        "title_seniority": "unknown",
        "requirements_seniority": "unknown",
        "capability_fit_status": "unknown",
        "seniority_evidence_status": "unknown",
    }


def _proposal(
    row: Mapping[str, object],
    *,
    source_authority: str,
    ranking_policy_version: str,
    hard_filter_policy_version: str,
) -> dict[str, object]:
    silver_job_id = int(row.get("current_silver_job_id") or 0)
    _require(silver_job_id > 0, "current Silver binding is missing")
    _require(str(row.get("lifecycle_status") or "") == "active_confirmed", "job is not lifecycle-current")
    source_url = str(row.get("source_url") or "").strip()
    _require(bool(source_url), "current Origin detail URL is missing")

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

    existing = row.get("silver_job_id") is not None
    previous = _assessment_payload(row) if existing else {}
    shell = previous if existing else _new_assessment_shell(row)
    next_payload = _decorate(
        shell,
        evidence=evidence,
        final_url=document.final_url,
        source_authority=source_authority,
        ranking_policy_version=ranking_policy_version,
        hard_filter_policy_version=hard_filter_policy_version,
    )
    changed_fields = [
        column
        for column in refresh.ASSESSMENT_COLUMNS
        if _json_safe(previous.get(column)) != _json_safe(next_payload.get(column))
    ]
    fingerprint = _fingerprint(
        {
            "requirement_evidence": evidence.canonical_payload(),
            "presentation_schema": PRESENTATION_SCHEMA,
            "source_authority": source_authority,
            "hard_filter_policy_version": hard_filter_policy_version,
        }
    )
    return {
        "silver_job_id": silver_job_id,
        "source_name": row.get("source_name"),
        "title": title,
        "source_url": source_url,
        "final_url": document.final_url,
        "source_authority": source_authority,
        "mode": "update" if existing else "insert",
        "assessment_updated_at": _json_safe(row.get("assessment_updated_at")),
        "revision_key": f"{REVISION_PREFIX}:{fingerprint[:24]}",
        "evidence_fingerprint": fingerprint,
        "job_skill_count": len(evidence.job_skills),
        "jsonld_jobposting_count": evidence.jsonld_jobposting_count,
        "verified_line_count": len(next_payload["explanations"]),
        "unknown_line_count": len(next_payload["uncertainties"]),
        "changed_fields": changed_fields,
        "would_change": bool(changed_fields),
        "previous_payload": previous,
        "next_payload": next_payload,
        "source_evidence": evidence.canonical_payload(),
    }


def build_plan(
    rows: Sequence[Mapping[str, object]],
    *,
    authorized_sources: Mapping[str, str],
    ranking_policy_version: str,
    hard_filter_policy_version: str,
) -> dict[str, object]:
    proposals: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []
    for row in rows:
        silver_job_id = int(row.get("current_silver_job_id") or 0)
        source_name = str(row.get("source_name") or "")
        source_authority = authorized_sources.get(source_name)
        if not source_authority:
            blocked.append(
                {
                    "silver_job_id": silver_job_id,
                    "source_name": source_name,
                    "title": row.get("title"),
                    "reason": "source lacks current DB-backed Employer-Origin admission authority",
                    "canonical_source_type": row.get("canonical_source_type"),
                }
            )
            continue
        try:
            proposals.append(
                _proposal(
                    row,
                    source_authority=source_authority,
                    ranking_policy_version=ranking_policy_version,
                    hard_filter_policy_version=hard_filter_policy_version,
                )
            )
        except (CurrentRequirementPlanStop, DownstreamPreviewStop, ValueError) as exc:
            blocked.append(
                {
                    "silver_job_id": silver_job_id,
                    "source_name": source_name,
                    "title": row.get("title"),
                    "reason": str(exc),
                    "canonical_source_type": row.get("canonical_source_type"),
                    "source_authority": source_authority,
                }
            )

    modes = Counter(str(item["mode"]) for item in proposals)
    return {
        "schema": REPORT_SCHEMA,
        "mode": "plan",
        "candidate_count": len(rows),
        "proposal_count": len(proposals),
        "blocked_count": len(blocked),
        "insert_count": modes.get("insert", 0),
        "update_count": modes.get("update", 0),
        "would_change_count": sum(bool(item["would_change"]) for item in proposals),
        "jobs_with_skills": sum(int(item["job_skill_count"]) > 0 for item in proposals),
        "jobs_with_verified_lines": sum(int(item["verified_line_count"]) > 0 for item in proposals),
        "jsonld_jobposting_count": sum(int(item["jsonld_jobposting_count"]) > 0 for item in proposals),
        "ranking_policy_version": ranking_policy_version,
        "job_evidence_policy_version": hard_filter_policy_version,
        "proposals": proposals,
        "blocked": blocked,
        "boundaries": {
            "candidate_fact_reads": False,
            "database_writes": False,
            "network_exact_current_origin_details": len(rows),
            "provider_or_llm_requests": 0,
            "raw_html_persisted": False,
            "capability_fit_authority": False,
            "ranking_authority": False,
            "top5_authority": False,
            "application_authority": False,
        },
    }


def _print_report(report: Mapping[str, object]) -> None:
    print("=== F4A-R2 FULL CURRENT JOB REQUIREMENT PLAN ===")
    for key in (
        "candidate_count",
        "proposal_count",
        "blocked_count",
        "insert_count",
        "update_count",
        "would_change_count",
        "jobs_with_skills",
        "jobs_with_verified_lines",
        "jsonld_jobposting_count",
        "ranking_policy_version",
        "job_evidence_policy_version",
    ):
        print(f"{key.upper()}={report.get(key)}")
    for item in report.get("blocked", []):
        print("BLOCKED=" + json.dumps(item, ensure_ascii=False, sort_keys=True))
    print("CANDIDATE_FACT_READS=0")
    print("DATABASE_WRITES=0")
    print("RANKING_AUTHORITY=0")
    print("TOP5_AUTHORITY=0")
    print("APPLICATION_AUTHORITY=0")
    print("RAW_HTML_PERSISTED=0")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".runtime/demo/f4a_r2_current_requirement_plan.json"),
    )
    args = parser.parse_args(argv)

    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        rows = _load_current_rows(conn)
        authorized_sources = _load_authorized_sources(conn)
        ranking_version, hard_filter_version = _load_policy_versions(conn)
        conn.rollback()

    _require(bool(rows), "no lifecycle-current Product jobs found")
    report = build_plan(
        rows,
        authorized_sources=authorized_sources,
        ranking_policy_version=ranking_version,
        hard_filter_policy_version=hard_filter_version,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(_json_safe(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _print_report(report)
    print(f"artifact={args.output.resolve()}")
    if int(report["blocked_count"]):
        raise SystemExit("F4A_R2_CURRENT_REQUIREMENT_PLAN_BLOCKED")
    print("F4A_R2_CURRENT_REQUIREMENT_PLAN=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
