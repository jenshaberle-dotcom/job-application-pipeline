"""Reconcile operator-visible job requirement evidence for the current F4A-R2 cohort.

Plan mode is read-only. Apply is explicit-token gated, revision-audited and bounded
to lifecycle-current employer-origin Product jobs. Candidate Facts are never read.
No ranking, Top-5, application or provider authority is created.
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

from scripts import run_f4a_requirement_evidence_refresh as refresh
from src.config import get_database_config
from src.search_intelligence.product_v1_downstream_preview import (
    DownstreamPreviewStop,
    fetch_public_https_detail_document,
)
from src.search_intelligence.product_v1_requirement_evidence import (
    ProductV1RequirementEvidence,
    extract_product_v1_requirement_evidence,
)


REPORT_SCHEMA = "job_application_pipeline.f4a_r2_requirement_reconcile.v1"
APPROVAL_TOKEN = "F4A-R2-REQUIREMENT-RECONCILE-001"
REVISION_PREFIX = "F4A-R2-REQUIREMENT-RECONCILE-001"
ASSESSED_BY = "deterministic_f4a_r2_requirement_evidence_v1"
PRESENTATION_SCHEMA = "operator_requirement_lines/v1"

AUTHORITATIVE_LIFECYCLE_REASONS = frozenset(
    {
        "authoritative_verified_ats_feed_observation",
        "authoritative_employer_origin_job_observation",
    }
)
AUTHORITATIVE_COVERAGE = frozenset({"exact_detail", "complete_inventory"})
PRODUCT_EMPLOYER_ORIGIN_TYPES = frozenset(
    {
        "employer_origin",
        "employer_origin_career_site",
        "employer_origin_ats_backed_career_site",
    }
)
RAW_EMPLOYER_ORIGIN_TYPES = frozenset(
    {
        "employer_origin_career_site",
        "employer_origin_ats_backed_career_site",
    }
)


class F4AR2ReconcileStop(RuntimeError):
    """Fail closed when the bounded F4A-R2 reconciliation contract is violated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise F4AR2ReconcileStop(message)


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


def _short(value: object, limit: int = 160) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _label(field: str) -> str:
    return {
        "employment_type": "Employment type",
        "required_languages": "Required languages",
        "weekly_hours": "Weekly hours",
        "work_model": "Work model",
        "requirements_seniority": "Requirement seniority",
        "title_seniority": "Title seniority",
    }.get(field, field.replace("_", " ").title())


def _reference_evidence(
    evidence_payload: Mapping[str, object], field: str
) -> list[str]:
    result: list[str] = []
    assessment = evidence_payload.get("assessment")
    if isinstance(assessment, Mapping):
        references = assessment.get("references")
        if isinstance(references, list):
            for item in references:
                if not isinstance(item, Mapping) or str(item.get("field") or "") != field:
                    continue
                snippet = _short(item.get("evidence"))
                if snippet and snippet not in result:
                    result.append(snippet)
    semantic = evidence_payload.get("semantic_references")
    semantic_field = "remote" if field == "work_model" else field
    if isinstance(semantic, list):
        for item in semantic:
            if not isinstance(item, Mapping) or str(item.get("field") or "") != semantic_field:
                continue
            snippet = _short(item.get("evidence"))
            if snippet and snippet not in result:
                result.append(snippet)
    return result[:2]


def build_operator_requirement_lines(
    evidence_payload: Mapping[str, object],
) -> tuple[list[str], list[str]]:
    """Project structured job-side truth to the normal Verified/Unknown UI lists."""

    patch = evidence_payload.get("resolved_assessment_patch")
    if not isinstance(patch, Mapping):
        patch = {}
    assessment = evidence_payload.get("assessment")
    if not isinstance(assessment, Mapping):
        assessment = {}

    verified: list[str] = []

    def add(field: str, value: object) -> None:
        if value in (None, "", "unknown", [], ()):
            return
        rendered = (
            ", ".join(str(item) for item in value)
            if isinstance(value, (list, tuple))
            else str(value)
        )
        references = _reference_evidence(evidence_payload, field)
        suffix = (
            f" — Origin evidence: {' / '.join(references)}"
            if references
            else " — Origin evidence"
        )
        verified.append(f"{_label(field)}: {rendered}{suffix}")

    add("employment_type", patch.get("employment_type"))
    add("required_languages", patch.get("required_languages"))

    minimum = patch.get("weekly_hours_min")
    maximum = patch.get("weekly_hours_max")
    if minimum is not None or maximum is not None:
        if minimum == maximum:
            hours = (
                f"{minimum:g} h/week"
                if isinstance(minimum, (int, float))
                else str(minimum)
            )
        else:
            left = (
                "?"
                if minimum is None
                else f"{minimum:g}"
                if isinstance(minimum, (int, float))
                else str(minimum)
            )
            right = (
                "?"
                if maximum is None
                else f"{maximum:g}"
                if isinstance(maximum, (int, float))
                else str(maximum)
            )
            hours = f"{left}-{right} h/week"
        add("weekly_hours", hours)

    add("work_model", patch.get("work_model"))
    add("requirements_seniority", patch.get("requirements_seniority"))

    skills = evidence_payload.get("job_skills")
    if isinstance(skills, list) and skills:
        rendered = ", ".join(str(item) for item in skills[:12])
        if len(skills) > 12:
            rendered += f" (+{len(skills) - 12} more)"
        verified.append(
            f"Job skills: {rendered} — structured/contextual Origin evidence"
        )

    title_seniority = assessment.get("title_seniority")
    if title_seniority not in (None, "", "unknown"):
        verified.append(
            f"Title seniority: {title_seniority} — title signal only; not requirement authority"
        )

    conflicts = {
        str(item) for item in evidence_payload.get("conflicted_fields", []) if str(item)
    }
    unresolved = [
        str(item) for item in evidence_payload.get("unresolved_fields", []) if str(item)
    ]
    unknown: list[str] = []
    for field in unresolved:
        if field in conflicts:
            unknown.append(
                f"Conflict: {_label(field)} — contradictory Origin evidence; kept unknown"
            )
        else:
            unknown.append(
                f"Unknown: {_label(field)} — no sufficiently strong deterministic Origin evidence"
            )
    unknown.append(
        "Candidate↔Job fit remains separate: job-side requirement evidence does not create capability-fit authority"
    )
    return verified, unknown


def _decorate_payload(
    payload: Mapping[str, object],
    *,
    evidence: ProductV1RequirementEvidence,
    final_url: str,
) -> dict[str, object]:
    result = dict(payload)
    patch = evidence.assessment_patch()
    evidence_payload = evidence.canonical_payload()
    verified, unknown = build_operator_requirement_lines(evidence_payload)
    raw_factors = result.get("ranking_factors")
    factors = dict(raw_factors) if isinstance(raw_factors, Mapping) else {}
    factors.update(
        {
            "source_evidence_only": True,
            "detail_description_sha256": evidence.assessment.description_sha256,
            "reference_count": len(evidence.assessment.references)
            + len(evidence.semantic_references),
            "conflicted_fields": list(evidence.conflicted_fields),
            "requirement_evidence": evidence_payload,
            "f4a_r2_requirement_reconcile": {
                "schema": REPORT_SCHEMA,
                "presentation_schema": PRESENTATION_SCHEMA,
                "final_url": final_url,
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


def _existing_proposal(row: Mapping[str, object]) -> dict[str, object]:
    proposal = refresh._build_proposal(row)
    evidence_payload = proposal.get("source_evidence")
    next_payload = proposal.get("next_payload")
    previous = proposal.get("previous_payload")
    _require(isinstance(evidence_payload, Mapping), "existing source evidence payload missing")
    _require(isinstance(next_payload, Mapping), "existing next assessment payload missing")
    _require(isinstance(previous, Mapping), "existing previous assessment payload missing")

    verified, unknown = build_operator_requirement_lines(evidence_payload)
    decorated = dict(next_payload)
    decorated["explanations"] = verified
    decorated["uncertainties"] = unknown
    decorated["assessed_by"] = ASSESSED_BY
    factors = decorated.get("ranking_factors")
    _require(isinstance(factors, Mapping), "existing ranking_factors missing")
    decorated_factors = dict(factors)
    decorated_factors["f4a_r2_requirement_reconcile"] = {
        "schema": REPORT_SCHEMA,
        "presentation_schema": PRESENTATION_SCHEMA,
        "final_url": proposal.get("final_url"),
    }
    decorated["ranking_factors"] = decorated_factors

    changed_fields = [
        column
        for column in refresh.ASSESSMENT_COLUMNS
        if _json_safe(previous.get(column)) != _json_safe(decorated.get(column))
    ]
    fingerprint = _fingerprint(
        {
            "requirement_evidence": evidence_payload,
            "presentation_schema": PRESENTATION_SCHEMA,
        }
    )
    result = dict(proposal)
    result.update(
        {
            "revision_key": f"{REVISION_PREFIX}:{fingerprint[:24]}",
            "evidence_fingerprint": fingerprint,
            "changed_fields": changed_fields,
            "next_payload": decorated,
            "would_change": bool(changed_fields),
            "mode": "update",
        }
    )
    return result


def _current_observation_raw_evidence(row: Mapping[str, object]) -> Mapping[str, object]:
    normalized = row.get("latest_observation_evidence")
    _require(
        isinstance(normalized, Mapping),
        "current normalized observation evidence required",
    )
    source_url = str(row.get("source_url") or "")
    _require(
        str(row.get("latest_observation_source_url") or "") == source_url
        and str(normalized.get("source_url") or "") == source_url,
        "current observation URL is not exact-bound to Silver",
    )
    raw = normalized.get("raw_evidence")
    _require(isinstance(raw, Mapping), "normalized observation raw_evidence missing")
    _require(
        str(raw.get("source_type") or "") in RAW_EMPLOYER_ORIGIN_TYPES,
        "current observation is not employer-origin evidence",
    )
    job = raw.get("job")
    _require(
        isinstance(job, Mapping) and str(job.get("source_url") or "") == source_url,
        "current observation job URL is not exact-bound",
    )
    return raw


def _validate_missing_authority(row: Mapping[str, object]) -> Mapping[str, object]:
    _require(row.get("origin_validation_status") is None, "assessment already has origin state")
    _require(
        str(row.get("product_readiness_status") or "") == "assessment_required",
        "job is not at initial assessment gate",
    )
    _require(
        str(row.get("lifecycle_status") or "") == "active_confirmed",
        "current active lifecycle authority required",
    )
    _require(
        str(row.get("canonical_source_type") or "") in PRODUCT_EMPLOYER_ORIGIN_TYPES,
        "current Product row is not employer-origin",
    )
    _require(
        str(row.get("lifecycle_evidence_reason") or "") in AUTHORITATIVE_LIFECYCLE_REASONS,
        "lifecycle evidence is not product-admissible origin proof",
    )
    _require(
        str(row.get("latest_health_coverage") or "") in AUTHORITATIVE_COVERAGE,
        "authoritative lifecycle coverage required",
    )
    return _current_observation_raw_evidence(row)


def _initial_payload(
    row: Mapping[str, object],
    *,
    evidence: ProductV1RequirementEvidence,
    final_url: str,
    policy_version: str,
) -> dict[str, object]:
    raw = _validate_missing_authority(row)
    source_url = str(row.get("source_url") or "")
    _require(
        _same_origin(source_url, final_url),
        "detail fetch redirected outside authorized origin",
    )
    payload: dict[str, object] = {
        "silver_job_id": int(row["silver_job_id"]),
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
        "ranking_factors": {
            "schema": REPORT_SCHEMA,
            "source_evidence_only": True,
            "authority": {
                "lifecycle_status": row.get("lifecycle_status"),
                "lifecycle_evidence_reason": row.get("lifecycle_evidence_reason"),
                "latest_health_coverage": row.get("latest_health_coverage"),
                "observation_source_type": raw.get("source_type"),
            },
        },
        "explanations": [],
        "uncertainties": [],
        "policy_key": "default",
        "policy_version": policy_version,
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
    return _decorate_payload(payload, evidence=evidence, final_url=final_url)


def _missing_proposal(
    row: Mapping[str, object], *, policy_version: str
) -> dict[str, object]:
    _validate_missing_authority(row)
    source_url = str(row.get("source_url") or "").strip()
    _require(bool(source_url), "source URL missing")
    document = fetch_public_https_detail_document(source_url)
    _require(
        _same_origin(source_url, document.final_url),
        "detail fetch redirected outside authorized origin",
    )
    title = str(row.get("title") or document.title or "").strip()
    _require(bool(title), "job title missing")
    evidence = extract_product_v1_requirement_evidence(
        html=document.html,
        text=document.text,
        title=title,
        page_title=document.title,
        source_url=document.final_url,
        target_location=str(row.get("city") or ""),
    )
    next_payload = _initial_payload(
        row,
        evidence=evidence,
        final_url=document.final_url,
        policy_version=policy_version,
    )
    evidence_payload = evidence.canonical_payload()
    fingerprint = _fingerprint(
        {
            "requirement_evidence": evidence_payload,
            "presentation_schema": PRESENTATION_SCHEMA,
        }
    )
    return {
        "silver_job_id": int(row["silver_job_id"]),
        "source_name": row.get("source_name"),
        "title": title,
        "source_url": source_url,
        "final_url": document.final_url,
        "assessment_updated_at": None,
        "revision_key": f"{REVISION_PREFIX}:{fingerprint[:24]}",
        "evidence_fingerprint": fingerprint,
        "job_skill_count": len(evidence.job_skills),
        "job_skills": list(evidence.job_skills),
        "jsonld_jobposting_count": evidence.jsonld_jobposting_count,
        "requirements_seniority": next_payload.get("requirements_seniority"),
        "requirements_seniority_from_title": False,
        "changed_fields": list(refresh.ASSESSMENT_COLUMNS),
        "previous_payload": {},
        "next_payload": next_payload,
        "source_evidence": evidence_payload,
        "would_change": True,
        "mode": "insert",
    }


def build_plan(
    *,
    existing_rows: Sequence[Mapping[str, object]],
    missing_rows: Sequence[Mapping[str, object]],
    policy_version: str,
) -> dict[str, object]:
    proposals: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []
    for mode, rows in (("update", existing_rows), ("insert", missing_rows)):
        for row in rows:
            try:
                proposals.append(
                    _existing_proposal(row)
                    if mode == "update"
                    else _missing_proposal(row, policy_version=policy_version)
                )
            except (
                F4AR2ReconcileStop,
                refresh.RequirementEvidenceRefreshStop,
                DownstreamPreviewStop,
                ValueError,
            ) as exc:
                blocked.append(
                    {
                        "silver_job_id": int(row.get("silver_job_id") or 0),
                        "source_name": row.get("source_name"),
                        "title": row.get("title"),
                        "mode": mode,
                        "reason": str(exc),
                    }
                )
    mode_counts = Counter(str(item.get("mode")) for item in proposals)
    return {
        "schema": REPORT_SCHEMA,
        "mode": "plan",
        "candidate_count": len(existing_rows) + len(missing_rows),
        "existing_candidate_count": len(existing_rows),
        "missing_candidate_count": len(missing_rows),
        "proposal_count": len(proposals),
        "blocked_count": len(blocked),
        "would_change_count": sum(bool(item.get("would_change")) for item in proposals),
        "insert_count": mode_counts.get("insert", 0),
        "update_count": mode_counts.get("update", 0),
        "jobs_with_skills": sum(
            int(item.get("job_skill_count") or 0) > 0 for item in proposals
        ),
        "jsonld_jobposting_count": sum(
            int(item.get("jsonld_jobposting_count") or 0) > 0 for item in proposals
        ),
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
            "operator_projection_uses_existing_explanations_surface": True,
        },
    }


def _load_policy_version(conn: psycopg.Connection[Any]) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ranking.policy_version AS ranking_version,
                   hard_filter.policy_version AS hard_filter_version
            FROM product_v1_ranking_policy ranking
            CROSS JOIN product_v1_hard_filter_policy hard_filter
            WHERE ranking.policy_key = 'default'
              AND hard_filter.policy_key = 'default'
              AND ranking.status = 'approved'
              AND hard_filter.status = 'approved'
            """
        )
        row = cur.fetchone()
    _require(row is not None, "approved Product V1 policies missing")
    ranking_version = str(row["ranking_version"] or "")
    hard_filter_version = str(row["hard_filter_version"] or "")
    _require(
        bool(ranking_version) and ranking_version == hard_filter_version,
        "Product V1 policy versions not aligned",
    )
    return ranking_version


def _load_missing_rows(
    conn: psycopg.Connection[Any], *, silver_job_ids: Sequence[int] = ()
) -> list[dict[str, object]]:
    clauses = [
        "readiness.origin_validation_status IS NULL",
        "readiness.product_readiness_status = 'assessment_required'",
        "readiness.lifecycle_status = 'active_confirmed'",
    ]
    params: list[object] = []
    if silver_job_ids:
        clauses.append("readiness.silver_job_id = ANY(%s)")
        params.append(list(silver_job_ids))
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT readiness.*, silver.raw_job_id,
                   latest_observation.observed_at AS latest_observation_observed_at,
                   latest_observation.source_url AS latest_observation_source_url,
                   latest_observation.normalized_evidence AS latest_observation_evidence
            FROM gold_product_v1_job_readiness readiness
            JOIN silver_jobs silver ON silver.id = readiness.silver_job_id
            LEFT JOIN LATERAL (
                SELECT observation.observed_at, observation.source_url,
                       observation.normalized_evidence
                FROM job_observations observation
                WHERE observation.raw_job_id = silver.raw_job_id
                  AND observation.source_name = silver.source_name
                  AND observation.is_seen = TRUE
                  AND observation.normalized_evidence IS NOT NULL
                ORDER BY observation.observed_at DESC, observation.id DESC
                LIMIT 1
            ) latest_observation ON TRUE
            WHERE {' AND '.join(clauses)}
            ORDER BY readiness.source_name, readiness.silver_job_id
            """,
            params,
        )
        return [dict(row) for row in cur.fetchall()]


def _load_existing_assessment(
    conn: psycopg.Connection[Any], silver_job_id: int, *, lock: bool = False
) -> Mapping[str, object] | None:
    lock_clause = "FOR UPDATE" if lock else ""
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {', '.join(refresh.ASSESSMENT_COLUMNS)} "
            f"FROM job_product_assessments WHERE silver_job_id = %s {lock_clause}",
            (silver_job_id,),
        )
        return cur.fetchone()


def _insert_assessment(
    conn: psycopg.Connection[Any], payload: Mapping[str, object]
) -> None:
    db_payload = dict(payload)
    for field in (
        "ranking_factors",
        "explanations",
        "uncertainties",
        "required_languages",
    ):
        db_payload[field] = Jsonb(payload[field])
    columns = ", ".join(refresh.ASSESSMENT_COLUMNS)
    placeholders = ", ".join(
        f"%({column})s" for column in refresh.ASSESSMENT_COLUMNS
    )
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO job_product_assessments ({columns}) VALUES ({placeholders})",
            db_payload,
        )
        _require(
            cur.rowcount == 1,
            "assessment insert did not write exactly one row",
        )


def apply_plan(plan: Mapping[str, object], *, applied_by: str) -> dict[str, int]:
    _require(
        int(plan.get("blocked_count") or 0) == 0,
        "blocked cohort rows forbid Apply",
    )
    raw = plan.get("proposals")
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
                revision = cur.fetchone()
                _require(
                    revision is not None and revision["relation"] is not None,
                    "revision table missing",
                )
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (REVISION_PREFIX,),
                )
            for proposal in proposals:
                silver_job_id = int(proposal["silver_job_id"])
                mode = str(proposal.get("mode") or "")
                next_payload = proposal.get("next_payload")
                _require(
                    isinstance(next_payload, Mapping),
                    "proposal next payload missing",
                )
                if mode == "update":
                    if proposal.get("would_change") is not True:
                        already_current += 1
                        continue
                    current = refresh._lock_assessment(conn, silver_job_id)
                    _require(
                        _json_safe(current.get("assessment_updated_at"))
                        == proposal.get("assessment_updated_at"),
                        f"assessment changed before Apply: {silver_job_id}",
                    )
                    revision_key = str(proposal["revision_key"])
                    if refresh._revision_exists(
                        conn,
                        silver_job_id=silver_job_id,
                        revision_key=revision_key,
                    ):
                        already_current += 1
                        continue
                    refresh._insert_revision(
                        conn,
                        proposal=proposal,
                        applied_by=applied_by,
                    )
                    refresh._update_assessment(conn, proposal=proposal)
                    updated += 1
                    continue

                _require(mode == "insert", f"unsupported proposal mode: {mode}")
                current_rows = _load_missing_rows(
                    conn, silver_job_ids=(silver_job_id,)
                )
                _require(
                    len(current_rows) == 1,
                    f"missing-assessment eligibility changed before Apply: {silver_job_id}",
                )
                _validate_missing_authority(current_rows[0])
                _require(
                    _load_existing_assessment(conn, silver_job_id, lock=True) is None,
                    f"assessment appeared before Apply: {silver_job_id}",
                )
                _insert_assessment(conn, next_payload)
                refresh._insert_revision(
                    conn,
                    proposal=proposal,
                    applied_by=applied_by,
                )
                inserted += 1
    finally:
        conn.close()
    return {
        "inserted": inserted,
        "updated": updated,
        "already_current": already_current,
    }


def _load_inputs() -> tuple[list[dict[str, object]], list[dict[str, object]], str]:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        existing = refresh._load_rows(conn)
        missing = _load_missing_rows(conn)
        policy_version = _load_policy_version(conn)
        conn.rollback()
    return existing, missing, policy_version


def _print_report(report: Mapping[str, object]) -> None:
    print("=== F4A-R2 CURRENT REQUIREMENT RECONCILE ===")
    for key in (
        "mode",
        "candidate_count",
        "existing_candidate_count",
        "missing_candidate_count",
        "proposal_count",
        "blocked_count",
        "would_change_count",
        "insert_count",
        "update_count",
        "jobs_with_skills",
        "jsonld_jobposting_count",
    ):
        print(f"{key.upper()}={report.get(key)}")
    for item in report.get("blocked", []):
        print("BLOCKED=" + json.dumps(item, ensure_ascii=False, sort_keys=True))
    print("CANDIDATE_FACT_READS=0")
    print("RANKING_AUTHORITY=0")
    print("TOP5_AUTHORITY=0")
    print("APPLICATION_AUTHORITY=0")
    print("PROVIDER_REQUESTS=0")
    print("RAW_HTML_PERSISTED=0")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--applied-by", default="f4a-r2")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".runtime/demo/f4a_r2_requirement_reconcile.json"),
    )
    args = parser.parse_args(argv)
    if args.apply:
        _require(
            args.approval_token == APPROVAL_TOKEN,
            "invalid F4A-R2 approval token",
        )
    _require(bool(args.applied_by.strip()), "applied_by must not be blank")

    existing, missing, policy_version = _load_inputs()
    _require(bool(existing or missing), "no lifecycle-current Product jobs found")
    report = build_plan(
        existing_rows=existing,
        missing_rows=missing,
        policy_version=policy_version,
    )
    result = {"inserted": 0, "updated": 0, "already_current": 0}
    if args.apply:
        result = apply_plan(report, applied_by=args.applied_by.strip())
        report = dict(report)
        report["mode"] = "apply"
        report["apply_result"] = result
        report["boundaries"] = {
            **dict(report["boundaries"]),
            "database_writes": bool(result["inserted"] or result["updated"]),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            _json_safe(report), ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    _print_report(report)
    if args.apply:
        print(f"INSERTED={result['inserted']}")
        print(f"UPDATED={result['updated']}")
        print(f"ALREADY_CURRENT={result['already_current']}")
    print(f"artifact={args.output.resolve()}")
    if int(report.get("blocked_count") or 0):
        raise SystemExit("F4A_R2_REQUIREMENT_RECONCILE_BLOCKED")
    print("F4A_R2_REQUIREMENT_RECONCILE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
