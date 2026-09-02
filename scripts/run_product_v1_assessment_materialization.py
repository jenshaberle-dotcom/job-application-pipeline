"""Guarded generic Product V1 assessment materialization.

This runner bridges already-authoritative employer-origin/current-vacancy truth into
an initial ``job_product_assessments`` row and reuses the source-neutral
assessment-evidence extractor. It is plan-only by default. Apply is atomic,
approval-token gated, insert-only, and never creates capability-fit or ranking
truth.

Authority composition required before materialization:
- an existing active recurring search profile classifies the source as
  ``employer_origin``;
- Product V1 lifecycle truth is ``active_confirmed`` from an authoritative
  employer-origin observation path;
- the latest persisted per-sighting normalized evidence is bound to the exact
  Silver source URL and identifies an employer-origin source type;
- the exact already-authorized vacancy URL is fetched through the existing
  bounded public-HTTPS detail reader; cross-origin redirects are rejected.

The feed/observation evidence is not treated as product authority by itself.
Product V1 materialization is the deterministic composition boundary above.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.connectors.registry import SourceRole
from src.ingest_jobs import load_recurring_profile_names, profile_source_role
from src.ingestion.repository import JobIngestionRepository
from src.search_intelligence.product_v1_assessment_evidence import (
    ProductV1AssessmentEvidence,
    extract_product_v1_assessment_evidence,
)
from src.search_intelligence.product_v1_contenders import classify_role_title
from src.search_intelligence.product_v1_downstream_preview import (
    fetch_public_https_detail_text,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / ".runtime" / "demo" / "product_v1_assessment_materialization.json"
)
APPROVAL_TOKEN = "PRODUCT-V1-ASSESSMENT-MATERIALIZE"
MATERIALIZER_CONTRACT = "product_v1_assessment_materialization.v1"
ASSESSED_BY = "deterministic_assessment_materialization_v1"

AUTHORITATIVE_LIFECYCLE_REASONS = frozenset(
    {
        "authoritative_verified_ats_feed_observation",
        "authoritative_employer_origin_job_observation",
    }
)
EMPLOYER_ORIGIN_SOURCE_TYPES = frozenset(
    {
        "employer_origin_career_site",
        "employer_origin_ats_backed_career_site",
    }
)
AUTHORITATIVE_COVERAGE = frozenset({"exact_detail", "complete_inventory"})

ASSESSMENT_COLUMNS = (
    "silver_job_id",
    "origin_validation_status",
    "activity_status",
    "hard_filter_status",
    "profile_direction_score",
    "data_focus_score",
    "reliability_focus_score",
    "evidence_quality_score",
    "overall_quality_score",
    "work_model",
    "commute_minutes",
    "public_transport_quality",
    "ranking_factors",
    "explanations",
    "uncertainties",
    "policy_key",
    "policy_version",
    "assessed_by",
    "employment_type",
    "employment_evidence_status",
    "required_languages",
    "language_evidence_status",
    "weekly_hours_min",
    "weekly_hours_max",
    "weekly_hours_evidence_status",
    "salary_min_gross_eur",
    "salary_max_gross_eur",
    "salary_evidence_status",
    "title_seniority",
    "requirements_seniority",
    "capability_fit_status",
    "seniority_evidence_status",
)


class MaterializationStop(RuntimeError):
    """Fail-closed materialization boundary."""


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


def _same_origin(left: str, right: str) -> bool:
    left_url = urlparse(left)
    right_url = urlparse(right)
    return (
        left_url.scheme.lower() == right_url.scheme.lower() == "https"
        and left_url.hostname
        and right_url.hostname
        and left_url.hostname.lower() == right_url.hostname.lower()
        and (left_url.port or 443) == (right_url.port or 443)
    )


def authorized_recurring_employer_origin_sources(
    repository: JobIngestionRepository,
) -> set[str]:
    """Return sources already admitted by active recurring employer-origin profiles."""

    profiles = repository.load_active_search_profiles()
    recurring_names = load_recurring_profile_names(repository, profiles)
    authorized: set[str] = set()
    for profile in profiles:
        if profile.profile_name not in recurring_names:
            continue
        try:
            role = profile_source_role(profile)
        except ValueError:
            continue
        if role == SourceRole.EMPLOYER_ORIGIN:
            authorized.add(str(profile.source_name))
    return authorized


def _row_binding_payload(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "silver_job_id": row.get("silver_job_id"),
        "raw_job_id": row.get("raw_job_id"),
        "source_name": row.get("source_name"),
        "source_url": row.get("source_url"),
        "title": row.get("title"),
        "lifecycle_status": row.get("lifecycle_status"),
        "lifecycle_evidence_reason": row.get("lifecycle_evidence_reason"),
        "latest_health_coverage": row.get("latest_health_coverage"),
        "latest_observation_observed_at": row.get("latest_observation_observed_at"),
        "latest_observation_source_url": row.get("latest_observation_source_url"),
        "latest_observation_evidence": row.get("latest_observation_evidence"),
    }


def _current_observation_raw_evidence(row: Mapping[str, object]) -> Mapping[str, object]:
    normalized = row.get("latest_observation_evidence")
    if not isinstance(normalized, Mapping):
        raise MaterializationStop("current normalized observation evidence is required")

    source_url = str(row.get("source_url") or "")
    observation_url = str(row.get("latest_observation_source_url") or "")
    projected_url = str(normalized.get("source_url") or "")
    if not source_url or observation_url != source_url or projected_url != source_url:
        raise MaterializationStop("current observation URL is not exact-bound to Silver")

    raw_evidence = normalized.get("raw_evidence")
    if not isinstance(raw_evidence, Mapping):
        raise MaterializationStop("normalized observation raw_evidence is missing")
    source_type = str(raw_evidence.get("source_type") or "")
    if source_type not in EMPLOYER_ORIGIN_SOURCE_TYPES:
        raise MaterializationStop("current observation is not employer-origin evidence")

    job = raw_evidence.get("job")
    if not isinstance(job, Mapping) or str(job.get("source_url") or "") != source_url:
        raise MaterializationStop("current observation job URL is not exact-bound")
    return raw_evidence


def validate_materialization_authority(
    row: Mapping[str, object],
    *,
    authorized_sources: set[str],
) -> Mapping[str, object]:
    source_name = str(row.get("source_name") or "")
    if source_name not in authorized_sources:
        raise MaterializationStop(
            "source lacks active recurring employer-origin profile authority"
        )
    if row.get("origin_validation_status") is not None:
        raise MaterializationStop("initial assessment already has origin state")
    if str(row.get("product_readiness_status") or "") != "assessment_required":
        raise MaterializationStop("job is not at the initial assessment gate")
    if str(row.get("lifecycle_status") or "") != "active_confirmed":
        raise MaterializationStop("current active lifecycle authority is required")
    if (
        str(row.get("lifecycle_evidence_reason") or "")
        not in AUTHORITATIVE_LIFECYCLE_REASONS
    ):
        raise MaterializationStop("lifecycle evidence is not product-admissible origin proof")
    if str(row.get("latest_health_coverage") or "") not in AUTHORITATIVE_COVERAGE:
        raise MaterializationStop("authoritative lifecycle coverage is required")
    return _current_observation_raw_evidence(row)


def _evidence_explanations(
    evidence: ProductV1AssessmentEvidence,
) -> list[dict[str, object]]:
    return [
        {
            "factor": reference.field,
            "status": "source_observed",
            "canonical_value": reference.canonical_value,
            "evidence": reference.evidence,
            "source_url": reference.source_url,
            "span_start": reference.span_start,
            "span_end": reference.span_end,
        }
        for reference in evidence.references
    ]


def _evidence_uncertainties(
    evidence: ProductV1AssessmentEvidence,
) -> list[dict[str, object]]:
    uncertainties = [
        {
            "factor": field,
            "status": "unknown",
            "action": "deterministic_evidence_missing",
        }
        for field in evidence.unresolved_fields
    ]
    uncertainties.append(
        {
            "factor": "capability_fit",
            "status": "unknown",
            "action": "approved_candidate_fact_comparison_required",
        }
    )
    return uncertainties


def build_assessment_payload(
    *,
    row: Mapping[str, object],
    authorized_sources: set[str],
    policy_version: str,
    final_url: str,
    detail_text: str,
) -> dict[str, object]:
    raw_evidence = validate_materialization_authority(
        row,
        authorized_sources=authorized_sources,
    )
    source_url = str(row.get("source_url") or "")
    if not _same_origin(source_url, final_url):
        raise MaterializationStop("detail fetch redirected outside the authorized origin")

    title = str(row.get("title") or "").strip()
    if not title:
        raise MaterializationStop("Silver job title is missing")

    evidence = extract_product_v1_assessment_evidence(
        description=detail_text,
        title=title,
        source_url=final_url,
    )
    patch = evidence.assessment_patch()
    observation_fingerprint = _fingerprint(row.get("latest_observation_evidence"))

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
        "work_model": patch["work_model"],
        "commute_minutes": None,
        "public_transport_quality": "unknown",
        "ranking_factors": {
            "schema": MATERIALIZER_CONTRACT,
            "source_evidence_only": True,
            "detail_description_sha256": evidence.description_sha256,
            "observation_evidence_sha256": observation_fingerprint,
            "reference_count": len(evidence.references),
            "conflicted_fields": list(evidence.conflicted_fields),
            "authority": {
                "profile_source_role": "employer_origin",
                "recurring_profile_active": True,
                "lifecycle_status": row.get("lifecycle_status"),
                "lifecycle_evidence_reason": row.get("lifecycle_evidence_reason"),
                "latest_health_coverage": row.get("latest_health_coverage"),
                "observation_observed_at": _json_safe(
                    row.get("latest_observation_observed_at")
                ),
                "observation_source_type": raw_evidence.get("source_type"),
            },
        },
        "explanations": _evidence_explanations(evidence),
        "uncertainties": _evidence_uncertainties(evidence),
        "policy_key": "default",
        "policy_version": policy_version,
        "assessed_by": ASSESSED_BY,
        "employment_type": patch["employment_type"],
        "employment_evidence_status": patch["employment_evidence_status"],
        "required_languages": patch["required_languages"],
        "language_evidence_status": patch["language_evidence_status"],
        "weekly_hours_min": patch["weekly_hours_min"],
        "weekly_hours_max": patch["weekly_hours_max"],
        "weekly_hours_evidence_status": patch["weekly_hours_evidence_status"],
        "salary_min_gross_eur": None,
        "salary_max_gross_eur": None,
        "salary_evidence_status": "unknown",
        "title_seniority": patch["title_seniority"],
        "requirements_seniority": patch["requirements_seniority"],
        "capability_fit_status": "unknown",
        "seniority_evidence_status": patch["seniority_evidence_status"],
    }
    payload["materialization_fingerprint"] = _fingerprint(
        {
            "binding": _row_binding_payload(row),
            "final_url": final_url,
            "policy_version": policy_version,
            "assessment": {key: payload[key] for key in ASSESSMENT_COLUMNS},
        }
    )
    return payload


def select_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    role_relevant_only: bool,
) -> list[Mapping[str, object]]:
    selected: list[Mapping[str, object]] = []
    for row in rows:
        if role_relevant_only and classify_role_title(str(row.get("title") or "")) is None:
            continue
        selected.append(row)
    return selected


def _load_policy_version(conn: psycopg.Connection[Any]) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                ranking.policy_version AS ranking_version,
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
    if row is None:
        raise MaterializationStop("approved Product V1 policies are missing")
    ranking_version = str(row["ranking_version"] or "")
    hard_filter_version = str(row["hard_filter_version"] or "")
    if not ranking_version or ranking_version != hard_filter_version:
        raise MaterializationStop("Product V1 policy versions are not aligned")
    return ranking_version


def _load_candidate_rows(
    conn: psycopg.Connection[Any],
    *,
    source_names: Sequence[str],
    silver_job_ids: Sequence[int],
) -> list[dict[str, object]]:
    clauses = [
        "readiness.origin_validation_status IS NULL",
        "readiness.product_readiness_status = 'assessment_required'",
        "readiness.lifecycle_status = 'active_confirmed'",
    ]
    params: list[object] = []
    if source_names:
        clauses.append("readiness.source_name = ANY(%s)")
        params.append(list(source_names))
    if silver_job_ids:
        clauses.append("readiness.silver_job_id = ANY(%s)")
        params.append(list(silver_job_ids))

    sql = f"""
        SELECT
            readiness.*,
            silver.raw_job_id,
            latest_observation.observed_at AS latest_observation_observed_at,
            latest_observation.source_url AS latest_observation_source_url,
            latest_observation.normalized_evidence AS latest_observation_evidence
        FROM gold_product_v1_job_readiness readiness
        JOIN silver_jobs silver
          ON silver.id = readiness.silver_job_id
        LEFT JOIN LATERAL (
            SELECT
                observation.observed_at,
                observation.source_url,
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
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def _load_existing(
    conn: psycopg.Connection[Any], silver_job_id: int, *, lock: bool = False
) -> Mapping[str, object] | None:
    lock_clause = "FOR UPDATE" if lock else ""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {', '.join(ASSESSMENT_COLUMNS)}
            FROM job_product_assessments
            WHERE silver_job_id = %s
            {lock_clause}
            """,
            (silver_job_id,),
        )
        return cur.fetchone()


def _existing_matches(existing: Mapping[str, object], payload: Mapping[str, object]) -> bool:
    current = {column: _json_safe(existing.get(column)) for column in ASSESSMENT_COLUMNS}
    proposed = {column: _json_safe(payload.get(column)) for column in ASSESSMENT_COLUMNS}
    return current == proposed


def _insert_assessment(
    conn: psycopg.Connection[Any], payload: Mapping[str, object]
) -> None:
    db_payload = dict(payload)
    for field in ("ranking_factors", "explanations", "uncertainties", "required_languages"):
        db_payload[field] = json.dumps(payload[field], sort_keys=True, ensure_ascii=False)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO job_product_assessments (
                silver_job_id,
                origin_validation_status,
                activity_status,
                hard_filter_status,
                profile_direction_score,
                data_focus_score,
                reliability_focus_score,
                evidence_quality_score,
                overall_quality_score,
                work_model,
                commute_minutes,
                public_transport_quality,
                ranking_factors,
                explanations,
                uncertainties,
                policy_key,
                policy_version,
                assessed_by,
                employment_type,
                employment_evidence_status,
                required_languages,
                language_evidence_status,
                weekly_hours_min,
                weekly_hours_max,
                weekly_hours_evidence_status,
                salary_min_gross_eur,
                salary_max_gross_eur,
                salary_evidence_status,
                title_seniority,
                requirements_seniority,
                capability_fit_status,
                seniority_evidence_status
            ) VALUES (
                %(silver_job_id)s,
                %(origin_validation_status)s,
                %(activity_status)s,
                %(hard_filter_status)s,
                %(profile_direction_score)s,
                %(data_focus_score)s,
                %(reliability_focus_score)s,
                %(evidence_quality_score)s,
                %(overall_quality_score)s,
                %(work_model)s,
                %(commute_minutes)s,
                %(public_transport_quality)s,
                %(ranking_factors)s::jsonb,
                %(explanations)s::jsonb,
                %(uncertainties)s::jsonb,
                %(policy_key)s,
                %(policy_version)s,
                %(assessed_by)s,
                %(employment_type)s,
                %(employment_evidence_status)s,
                %(required_languages)s::jsonb,
                %(language_evidence_status)s,
                %(weekly_hours_min)s,
                %(weekly_hours_max)s,
                %(weekly_hours_evidence_status)s,
                %(salary_min_gross_eur)s,
                %(salary_max_gross_eur)s,
                %(salary_evidence_status)s,
                %(title_seniority)s,
                %(requirements_seniority)s,
                %(capability_fit_status)s,
                %(seniority_evidence_status)s
            )
            """,
            db_payload,
        )
        if cur.rowcount != 1:
            raise MaterializationStop("assessment insert did not write exactly one row")


def _readiness_after(
    conn: psycopg.Connection[Any], silver_job_ids: Sequence[int]
) -> list[dict[str, object]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                silver_job_id,
                source_name,
                title,
                origin_validation_status,
                activity_status,
                hard_filter_status,
                overall_quality_score,
                product_readiness_status,
                hard_filter_reasons
            FROM gold_product_v1_job_readiness
            WHERE silver_job_id = ANY(%s)
            ORDER BY source_name, silver_job_id
            """,
            (list(silver_job_ids),),
        )
        return [dict(row) for row in cur.fetchall()]


def build_plan(
    *,
    rows: Sequence[Mapping[str, object]],
    authorized_sources: set[str],
    policy_version: str,
    fetch_detail: Callable[[str], tuple[str, str, str]] = fetch_public_https_detail_text,
) -> dict[str, object]:
    proposals: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []
    for row in rows:
        silver_job_id = int(row.get("silver_job_id") or 0)
        try:
            validate_materialization_authority(
                row,
                authorized_sources=authorized_sources,
            )
            source_url = str(row.get("source_url") or "")
            final_url, fetched_title, detail_text = fetch_detail(source_url)
            payload = build_assessment_payload(
                row=row,
                authorized_sources=authorized_sources,
                policy_version=policy_version,
                final_url=final_url,
                detail_text=detail_text,
            )
            proposals.append(
                {
                    "silver_job_id": silver_job_id,
                    "source_name": row.get("source_name"),
                    "title": row.get("title"),
                    "source_url": source_url,
                    "final_url": final_url,
                    "fetched_title": fetched_title,
                    "materialization_fingerprint": payload["materialization_fingerprint"],
                    "assessment": {
                        key: _json_safe(payload[key]) for key in ASSESSMENT_COLUMNS
                    },
                    "unresolved_fields": [
                        item["factor"]
                        for item in payload["uncertainties"]
                        if isinstance(item, Mapping)
                    ],
                }
            )
        except (MaterializationStop, ValueError) as exc:
            blocked.append(
                {
                    "silver_job_id": silver_job_id,
                    "source_name": row.get("source_name"),
                    "title": row.get("title"),
                    "reason": str(exc),
                }
            )

    return {
        "schema": MATERIALIZER_CONTRACT,
        "mode": "plan",
        "policy_version": policy_version,
        "candidate_count": len(rows),
        "proposal_count": len(proposals),
        "blocked_count": len(blocked),
        "proposals": proposals,
        "blocked": blocked,
        "boundaries": {
            "database_reads": True,
            "database_writes": False,
            "network_exact_detail_targets": len(rows),
            "provider_or_llm_requests": 0,
            "source_or_profile_activation": False,
            "assessment_rows_max_on_apply": len(proposals),
            "assessment_updates": False,
            "capability_fit_created": False,
            "ranking_scores_created": False,
            "top5_forced": False,
            "application_or_submission_writes": False,
            "raw_detail_html_persisted": False,
        },
    }


def apply_plan(
    *,
    plan: Mapping[str, object],
    source_names: Sequence[str],
    silver_job_ids: Sequence[int],
    role_relevant_only: bool,
    authorized_sources: set[str],
) -> dict[str, object]:
    raw_proposals = plan.get("proposals")
    if not isinstance(raw_proposals, list):
        raise MaterializationStop("plan proposals are missing")
    proposals = [item for item in raw_proposals if isinstance(item, Mapping)]
    if not proposals:
        return {"inserted": 0, "already_materialized": 0, "readiness_after": []}

    expected_by_id = {int(item["silver_job_id"]): item for item in proposals}
    conn = psycopg.connect(**get_database_config(), row_factory=dict_row)
    try:
        with conn.transaction():
            current_policy_version = _load_policy_version(conn)
            if current_policy_version != plan.get("policy_version"):
                raise MaterializationStop("Product V1 policy changed after preflight")

            current_rows = select_rows(
                _load_candidate_rows(
                    conn,
                    source_names=source_names,
                    silver_job_ids=silver_job_ids,
                ),
                role_relevant_only=role_relevant_only,
            )
            current_by_id = {int(row["silver_job_id"]): row for row in current_rows}
            if set(current_by_id) != set(expected_by_id):
                raise MaterializationStop("eligible candidate set changed after preflight")

            inserted = 0
            already_materialized = 0
            for silver_job_id, proposal in expected_by_id.items():
                row = current_by_id[silver_job_id]
                validate_materialization_authority(
                    row,
                    authorized_sources=authorized_sources,
                )
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%s))",
                        (f"{MATERIALIZER_CONTRACT}:{silver_job_id}",),
                    )

                existing = _load_existing(conn, silver_job_id, lock=True)
                assessment = proposal.get("assessment")
                if not isinstance(assessment, Mapping):
                    raise MaterializationStop("proposal assessment is missing")
                if existing is None:
                    _insert_assessment(conn, assessment)
                    inserted += 1
                elif _existing_matches(existing, assessment):
                    already_materialized += 1
                else:
                    raise MaterializationStop(
                        f"conflicting assessment already exists for {silver_job_id}"
                    )

            readiness = _readiness_after(conn, sorted(expected_by_id))
        return {
            "inserted": inserted,
            "already_materialized": already_materialized,
            "readiness_after": [_json_safe(row) for row in readiness],
        }
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-name", action="append", default=[])
    parser.add_argument("--silver-job-id", action="append", type=int, default=[])
    parser.add_argument("--role-relevant-only", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_names = tuple(dict.fromkeys(str(value).strip() for value in args.source_name if str(value).strip()))
    silver_job_ids = tuple(dict.fromkeys(int(value) for value in args.silver_job_id))
    if not source_names and not silver_job_ids:
        raise SystemExit("at least one --source-name or --silver-job-id is required")
    if any(value <= 0 for value in silver_job_ids):
        raise SystemExit("--silver-job-id values must be positive")
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit(f"--apply requires --approval-token {APPROVAL_TOKEN}")
    if not args.apply and args.approval_token:
        raise SystemExit("--approval-token is accepted only with --apply")

    repository = JobIngestionRepository()
    authorized_sources = authorized_recurring_employer_origin_sources(repository)
    requested_sources = set(source_names)
    unauthorized_requested = sorted(requested_sources - authorized_sources)
    if unauthorized_requested:
        raise SystemExit(
            "requested source lacks active recurring employer-origin authority: "
            + ", ".join(unauthorized_requested)
        )

    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        policy_version = _load_policy_version(conn)
        rows = select_rows(
            _load_candidate_rows(
                conn,
                source_names=source_names,
                silver_job_ids=silver_job_ids,
            ),
            role_relevant_only=args.role_relevant_only,
        )
        conn.rollback()

    plan = build_plan(
        rows=rows,
        authorized_sources=authorized_sources,
        policy_version=policy_version,
    )
    result: dict[str, object] = dict(plan)

    if args.apply:
        if plan["blocked_count"]:
            raise SystemExit("apply refused because the plan contains blocked candidates")
        applied = apply_plan(
            plan=plan,
            source_names=source_names,
            silver_job_ids=silver_job_ids,
            role_relevant_only=args.role_relevant_only,
            authorized_sources=authorized_sources,
        )
        result["mode"] = "apply"
        result["apply_result"] = applied
        result["boundaries"] = {
            **dict(result["boundaries"]),
            "database_writes": True,
            "assessment_rows_inserted": applied["inserted"],
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, default=str, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    unresolved = Counter(
        field
        for proposal in result["proposals"]
        for field in proposal.get("unresolved_fields", [])
    )
    print("============================================")
    print("PRODUCT V1 ASSESSMENT MATERIALIZATION")
    print("============================================")
    print(f"MODE={result['mode']}")
    print(f"CANDIDATES={result['candidate_count']}")
    print(f"PROPOSALS={result['proposal_count']}")
    print(f"BLOCKED={result['blocked_count']}")
    print("UNRESOLVED_COUNTS=" + json.dumps(dict(sorted(unresolved.items()))))
    for proposal in result["proposals"]:
        assessment = proposal["assessment"]
        print(
            "ASSESSMENT="
            f"{proposal['silver_job_id']}|{proposal['source_name']}|"
            f"employment={assessment['employment_type']}|"
            f"languages={assessment['required_languages']}|"
            f"hours={assessment['weekly_hours_min']}-{assessment['weekly_hours_max']}|"
            f"work_model={assessment['work_model']}|"
            f"title_seniority={assessment['title_seniority']}"
        )
    for blocked in result["blocked"]:
        print(
            "BLOCKED_JOB="
            f"{blocked['silver_job_id']}|{blocked['source_name']}|{blocked['reason']}"
        )
    if args.apply:
        apply_result = result["apply_result"]
        print(f"INSERTED={apply_result['inserted']}")
        print(f"ALREADY_MATERIALIZED={apply_result['already_materialized']}")
        for row in apply_result["readiness_after"]:
            print(
                "READINESS="
                f"{row['silver_job_id']}|{row['product_readiness_status']}|"
                f"hard_filter={row['hard_filter_status']}"
            )
    print("PROVIDER_REQUESTS=0")
    print("RANKING_SCORES_CREATED=0")
    print(f"artifact={args.output.resolve()}")
    print("PRODUCT_V1_ASSESSMENT_MATERIALIZATION=COMPLETE")
    return 0 if not result["blocked_count"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
