"""Run the F4A-R2 read-only requirement plan against operator-visible current truth.

F4A-R2 exists to repair the evidence shown in the Control Center. Therefore its
cohort must be the same normal review scope the operator actually sees, not the
larger lifecycle-current storage projection. The Control Center already applies
bounded presentation-only geography filtering and exact Origin identity dedup to
that scope; neither operation grants ranking or application authority.

This diagnostic deliberately does *not* treat source activation/admission as a
second gate for reading public job-side requirement evidence. A row first has to
be in canonical Product truth and then survive the exact same presentation
projection used for normal operator review. The diagnostic still fetches only the
exact persisted HTTPS detail URL, rejects cross-origin redirects, never reads
Candidate Facts, never writes the database, and grants no ranking, Top-5,
capability-fit or application authority.

A current Product row whose exact persisted Origin detail now returns HTTP 404 is
not silently closed and does not retain stale inferred metadata. F4A-R2 projects
that job's requirement evidence as explicit unknown/unavailable. This is separate
from lifecycle authority: a 404 is not closure evidence. Security-boundary and
origin-redirect failures remain hard blockers.

For source migrations, the diagnostic reports exact title+company matches already
present in Silver under another source projection and the DB-backed state of the
corresponding canonical ``generic_origin:<company>`` source. These are evidence
only: no vacancy identity, URL, lifecycle state, source activation, or Product
authority is mutated.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

import psycopg

from scripts import product_v1_control_center_base as control_center_base
from scripts import run_f4a_r2_current_requirement_plan as plan
from scripts.product_v1_job_presentation_runtime import (
    enrich_product_payload_for_operator,
)
from src.search_intelligence.product_v1_downstream_preview import DownstreamPreviewStop


CURRENT_PRODUCT_AUTHORITY = "operator_review_scope_current_origin"
_CANONICAL_LOAD_CURRENT_ROWS = plan._load_current_rows
_CANONICAL_PROPOSAL = plan._proposal


def _review_scope_ids(payload: Mapping[str, object]) -> set[int]:
    result: set[int] = set()
    rows = payload.get("job_readiness")
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        value = row.get("silver_job_id")
        try:
            silver_job_id = int(value) if value is not None else 0
        except (TypeError, ValueError):
            continue
        if silver_job_id > 0:
            result.add(silver_job_id)
    return result


def _operator_review_payload() -> dict[str, object]:
    core = control_center_base.load_product_v1_payload(
        include_source_connector_overview=False
    )
    return enrich_product_payload_for_operator(core)


def _operator_review_rows(conn: psycopg.Connection[Any]) -> list[dict[str, object]]:
    review_ids = _review_scope_ids(_operator_review_payload())
    if not review_ids:
        return []
    return [
        row
        for row in _CANONICAL_LOAD_CURRENT_ROWS(conn)
        if int(row.get("current_silver_job_id") or 0) in review_ids
    ]


def _current_product_sources(conn: psycopg.Connection[Any]) -> dict[str, str]:
    rows = _operator_review_rows(conn)
    return {
        source_name: CURRENT_PRODUCT_AUTHORITY
        for row in rows
        if (source_name := str(row.get("source_name") or "").strip())
    }


def _stabilize_representation_only_requirement_drift(
    proposal: Mapping[str, object],
) -> dict[str, object]:
    """Ignore fetch-layout churn when persisted job-side semantics are unchanged.

    Public Origin pages can move text spans or alter non-semantic markup between
    two fetches. F4A-R2 must not manufacture an endless assessment revision loop
    from those representation-only changes. We reuse the canonical stable
    requirement-evidence fingerprint from the guarded refresh path and preserve
    the already persisted exact evidence representation when its semantics match.
    Any semantic difference, any non-ranking field change, or any structural
    F4A-R2 marker change remains a real proposal and therefore stays fail-closed.
    """

    result = dict(proposal)
    if result.get("mode") != "update" or result.get("changed_fields") != [
        "ranking_factors"
    ]:
        return result

    previous_payload = result.get("previous_payload")
    next_payload = result.get("next_payload")
    if not isinstance(previous_payload, Mapping) or not isinstance(next_payload, Mapping):
        return result
    previous_factors = previous_payload.get("ranking_factors")
    next_factors = next_payload.get("ranking_factors")
    if not isinstance(previous_factors, Mapping) or not isinstance(next_factors, Mapping):
        return result
    stored_evidence = previous_factors.get("requirement_evidence")
    fresh_evidence = next_factors.get("requirement_evidence")
    if not isinstance(stored_evidence, Mapping) or not isinstance(fresh_evidence, Mapping):
        return result
    if (
        plan.refresh._stable_requirement_evidence_fingerprint(stored_evidence)
        != plan.refresh._stable_requirement_evidence_fingerprint(fresh_evidence)
    ):
        return result

    stabilized_factors = dict(next_factors)
    for key in (
        "detail_description_sha256",
        "reference_count",
        "requirement_evidence",
    ):
        if key in previous_factors:
            stabilized_factors[key] = previous_factors[key]
        else:
            stabilized_factors.pop(key, None)

    stabilized_payload = dict(next_payload)
    stabilized_payload["ranking_factors"] = stabilized_factors
    changed_fields = [
        column
        for column in plan.refresh.ASSESSMENT_COLUMNS
        if plan._json_safe(previous_payload.get(column))
        != plan._json_safe(stabilized_payload.get(column))
    ]
    result["next_payload"] = stabilized_payload
    result["changed_fields"] = changed_fields
    result["would_change"] = bool(changed_fields)
    result["representation_only_requirement_evidence_drift_ignored"] = not changed_fields
    return result


def _unavailable_origin_proposal(
    row: Mapping[str, object],
    *,
    source_authority: str,
    ranking_policy_version: str,
    hard_filter_policy_version: str,
    reason: str,
) -> dict[str, object]:
    """Project inaccessible job-side requirements to explicit unknowns only."""

    silver_job_id = int(row.get("current_silver_job_id") or 0)
    source_url = str(row.get("source_url") or "").strip()
    existing = row.get("silver_job_id") is not None
    previous = plan._assessment_payload(row) if existing else {}
    shell = dict(previous) if existing else plan._new_assessment_shell(row)
    factors = dict(shell.get("ranking_factors") or {})
    factors.pop("requirement_evidence", None)
    factors.update(
        {
            "source_evidence_only": True,
            "f4a_r2_requirement_evidence": {
                "schema": plan.REPORT_SCHEMA,
                "presentation_schema": plan.PRESENTATION_SCHEMA,
                "final_url": None,
                "source_url": source_url,
                "source_authority": source_authority,
                "job_evidence_policy_version": hard_filter_policy_version,
                "ranking_policy_version_independent": ranking_policy_version,
                "status": "origin_detail_unavailable",
                "reason": reason,
            },
        }
    )
    unknown = [
        "Unknown: Job requirements — current Origin detail unavailable; stale metadata is not reused",
        "Candidate↔Job fit remains separate: unavailable job evidence does not create capability-fit authority",
    ]
    next_payload = dict(shell)
    next_payload.update(
        {
            "hard_filter_status": "unknown",
            "profile_direction_score": None,
            "data_focus_score": None,
            "reliability_focus_score": None,
            "evidence_quality_score": None,
            "overall_quality_score": None,
            "work_model": "unknown",
            "ranking_factors": factors,
            "explanations": [],
            "uncertainties": unknown,
            "policy_key": "default",
            "policy_version": hard_filter_policy_version,
            "assessed_by": plan.ASSESSED_BY,
            "employment_type": "unknown",
            "employment_evidence_status": "unknown",
            "required_languages": [],
            "language_evidence_status": "unknown",
            "weekly_hours_min": None,
            "weekly_hours_max": None,
            "weekly_hours_evidence_status": "unknown",
            "title_seniority": "unknown",
            "requirements_seniority": "unknown",
            "capability_fit_status": "unknown",
            "seniority_evidence_status": "unknown",
        }
    )
    changed_fields = [
        column
        for column in plan.refresh.ASSESSMENT_COLUMNS
        if plan._json_safe(previous.get(column))
        != plan._json_safe(next_payload.get(column))
    ]
    evidence_payload = {
        "status": "origin_detail_unavailable",
        "reason": reason,
        "source_url": source_url,
    }
    fingerprint = plan._fingerprint(
        {
            "source_evidence": evidence_payload,
            "presentation_schema": plan.PRESENTATION_SCHEMA,
            "source_authority": source_authority,
            "hard_filter_policy_version": hard_filter_policy_version,
        }
    )
    return {
        "silver_job_id": silver_job_id,
        "source_name": row.get("source_name"),
        "title": row.get("title"),
        "source_url": source_url,
        "final_url": None,
        "source_authority": source_authority,
        "mode": "update" if existing else "insert",
        "assessment_updated_at": plan._json_safe(row.get("assessment_updated_at")),
        "revision_key": f"{plan.REVISION_PREFIX}:{fingerprint[:24]}",
        "evidence_fingerprint": fingerprint,
        "job_skill_count": 0,
        "jsonld_jobposting_count": 0,
        "verified_line_count": 0,
        "unknown_line_count": len(unknown),
        "changed_fields": changed_fields,
        "would_change": bool(changed_fields),
        "previous_payload": previous,
        "next_payload": next_payload,
        "source_evidence": evidence_payload,
        "origin_detail_unavailable": True,
    }


def _proposal_with_explicit_unavailable(
    row: Mapping[str, object],
    *,
    source_authority: str,
    ranking_policy_version: str,
    hard_filter_policy_version: str,
) -> dict[str, object]:
    try:
        canonical = _CANONICAL_PROPOSAL(
            row,
            source_authority=source_authority,
            ranking_policy_version=ranking_policy_version,
            hard_filter_policy_version=hard_filter_policy_version,
        )
        return _stabilize_representation_only_requirement_drift(canonical)
    except DownstreamPreviewStop as exc:
        reason = str(exc)
        if reason != "preview detail returned HTTP 404":
            raise
        return _unavailable_origin_proposal(
            row,
            source_authority=source_authority,
            ranking_policy_version=ranking_policy_version,
            hard_filter_policy_version=hard_filter_policy_version,
            reason=reason,
        )


def _print_exact_relocation_candidates(conn: psycopg.Connection[Any]) -> None:
    rows = _operator_review_rows(conn)
    legacy = [
        row
        for row in rows
        if not str(row.get("source_name") or "").startswith("generic_origin:")
    ]
    candidate_count = 0
    with conn.cursor() as cur:
        for row in legacy:
            title = str(row.get("title") or "").strip()
            company = str(row.get("company_name") or "").strip()
            if not title or not company:
                continue
            cur.execute(
                """
                SELECT silver.id AS silver_job_id, silver.source_name, silver.source_url,
                       silver.title, silver.company_name, lifecycle.lifecycle_status,
                       identity.is_representative, identity.canonical_vacancy_key
                FROM silver_jobs silver
                LEFT JOIN gold_job_lifecycle_health lifecycle
                  ON lifecycle.silver_job_id = silver.id
                LEFT JOIN gold_vacancy_identity identity
                  ON identity.silver_job_id = silver.id
                WHERE silver.id <> %s
                  AND lower(btrim(silver.title)) = lower(btrim(%s))
                  AND lower(btrim(coalesce(silver.company_name, ''))) = lower(btrim(%s))
                  AND silver.source_name LIKE 'generic_origin:%%'
                ORDER BY silver.id DESC
                """,
                (int(row.get("current_silver_job_id") or 0), title, company),
            )
            for candidate in cur.fetchall():
                candidate_count += 1
                print(
                    "F4A_R2_EXACT_RELOCATION_CANDIDATE="
                    + json.dumps(
                        {
                            "from_silver_job_id": int(row.get("current_silver_job_id") or 0),
                            "from_source_name": row.get("source_name"),
                            "from_source_url": row.get("source_url"),
                            "candidate": dict(candidate),
                        },
                        default=str,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
    print(f"F4A_R2_EXACT_RELOCATION_CANDIDATES={candidate_count}")


def _print_generic_source_state(conn: psycopg.Connection[Any]) -> None:
    source_name = "generic_origin:finanz_informatik"
    state: dict[str, object] = {"source_name": source_name}
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.generic_employer_origin_active_sources') AS relation")
        relation = cur.fetchone()
        active_relation = relation is not None and relation["relation"] is not None
        state["active_source_table_present"] = active_relation
        if active_relation:
            cur.execute(
                """SELECT company_key, origin_url, proof_state, authority, activated_at, updated_at
                   FROM generic_employer_origin_active_sources WHERE source_name = %s""",
                (source_name,),
            )
            active = cur.fetchone()
            state["active_source"] = dict(active) if active is not None else None
        cur.execute(
            """SELECT id, profile_name, is_active, search_location, search_radius_km
               FROM search_profiles WHERE source_name = %s ORDER BY id""",
            (source_name,),
        )
        state["profiles"] = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """SELECT id, search_profile_id, status, started_at, finished_at,
                      total_loaded, inserted_count, duplicate_count, error_message
               FROM ingestion_runs WHERE source_name = %s
               ORDER BY started_at DESC, id DESC LIMIT 5""",
            (source_name,),
        )
        state["recent_ingestion_runs"] = [dict(row) for row in cur.fetchall()]
        cur.execute(
            "SELECT count(*)::integer AS raw_count FROM raw_jobs WHERE source_name = %s",
            (source_name,),
        )
        state["raw_count"] = int(cur.fetchone()["raw_count"])
        cur.execute(
            "SELECT count(*)::integer AS silver_count FROM silver_jobs WHERE source_name = %s",
            (source_name,),
        )
        state["silver_count"] = int(cur.fetchone()["silver_count"])
    print(
        "F4A_R2_GENERIC_FI_STATE="
        + json.dumps(state, default=str, ensure_ascii=False, sort_keys=True)
    )


def main() -> int:
    with psycopg.connect(**plan.get_database_config(), row_factory=plan.dict_row) as conn:
        _print_generic_source_state(conn)
        _print_exact_relocation_candidates(conn)
        conn.rollback()
    plan._load_current_rows = _operator_review_rows
    plan._load_authorized_sources = _current_product_sources
    plan._proposal = _proposal_with_explicit_unavailable
    return plan.main()


if __name__ == "__main__":
    raise SystemExit(main())
