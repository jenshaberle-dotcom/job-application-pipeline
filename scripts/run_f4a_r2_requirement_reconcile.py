"""Reconcile operator-visible job requirement evidence for the current F4A-R2 cohort.

The runner composes two already-reviewed paths:
- initial Product assessment authority for lifecycle-current employer-origin jobs;
- structured/contextual F4A requirement evidence for existing assessments.

Plan mode is read-only. Apply is explicit-token gated, revision-audited and bounded to
current employer-origin jobs. Candidate Facts are never read. No ranking, Top-5,
application or provider authority is created.
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

import psycopg
from psycopg.rows import dict_row

from scripts import run_f4a_requirement_evidence_refresh as refresh
from scripts import run_product_v1_assessment_materialization as materializer
from src.ingestion.repository import JobIngestionRepository
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


def _short(value: object, limit: int = 160) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


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
    """Project source evidence to bounded strings for the existing normal UI."""

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
        if isinstance(value, (list, tuple)):
            rendered = ", ".join(str(item) for item in value)
        else:
            rendered = str(value)
        references = _reference_evidence(evidence_payload, field)
        suffix = f" — Origin evidence: {' / '.join(references)}" if references else " — Origin evidence"
        verified.append(f"{_label(field)}: {rendered}{suffix}")

    add("employment_type", patch.get("employment_type"))
    add("required_languages", patch.get("required_languages"))

    minimum = patch.get("weekly_hours_min")
    maximum = patch.get("weekly_hours_max")
    if minimum is not None or maximum is not None:
        if minimum == maximum:
            hours = f"{minimum:g} h/week" if isinstance(minimum, (int, float)) else str(minimum)
        else:
            left = "?" if minimum is None else f"{minimum:g}" if isinstance(minimum, (int, float)) else str(minimum)
            right = "?" if maximum is None else f"{maximum:g}" if isinstance(maximum, (int, float)) else str(maximum)
            hours = f"{left}-{right} h/week"
        add("weekly_hours", hours)

    add("work_model", patch.get("work_model"))
    add("requirements_seniority", patch.get("requirements_seniority"))

    skills = evidence_payload.get("job_skills")
    if isinstance(skills, list) and skills:
        rendered = ", ".join(str(item) for item in skills[:12])
        if len(skills) > 12:
            rendered += f" (+{len(skills) - 12} more)"
        verified.append(f"Job skills: {rendered} — structured/contextual Origin evidence")

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
    result.pop("materialization_fingerprint", None)
    return result


def _existing_proposal(row: Mapping[str, object]) -> dict[str, object]:
    proposal = refresh._build_proposal(row)
    evidence_payload = proposal.get("source_evidence")
    _require(isinstance(evidence_payload, Mapping), "existing source evidence payload missing")
    next_payload = proposal.get("next_payload")
    _require(isinstance(next_payload, Mapping), "existing next assessment payload missing")

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

    previous = proposal.get("previous_payload")
    _require(isinstance(previous, Mapping), "existing previous assessment payload missing")
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


def _missing_proposal(
    row: Mapping[str, object],
    *,
    authorized_sources: set[str],
    policy_version: str,
) -> dict[str, object]:
    materializer.validate_materialization_authority(
        row,
        authorized_sources=authorized_sources,
    )
    source_url = str(row.get("source_url") or "").strip()
    document = fetch_public_https_detail_document(source_url)
    _require(
        materializer._same_origin(source_url, document.final_url),
        "detail fetch redirected outside authorized origin",
    )
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
    baseline = materializer.build_assessment_payload(
        row=row,
        authorized_sources=authorized_sources,
        policy_version=policy_version,
        final_url=document.final_url,
        detail_text=document.text,
    )
    next_payload = _decorate_payload(
        baseline,
        evidence=evidence,
        final_url=document.final_url,
    )
    fingerprint = _fingerprint(
        {
            "requirement_evidence": evidence.canonical_payload(),
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
        "source_evidence": evidence.canonical_payload(),
        "would_change": True,
        "mode": "insert",
    }


def build_plan(
    *,
    existing_rows: Sequence[Mapping[str, object]],
    missing_rows: Sequence[Mapping[str, object]],
    authorized_sources: set[str],
    policy_version: str,
) -> dict[str, object]:
    proposals: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []

    for mode, rows in (("update", existing_rows), ("insert", missing_rows)):
        for row in rows:
            try:
                proposal = (
                    _existing_proposal(row)
                    if mode == "update"
                    else _missing_proposal(
                        row,
                        authorized_sources=authorized_sources,
                        policy_version=policy_version,
                    )
                )
                proposals.append(proposal)
            except (
                F4AR2ReconcileStop,
                refresh.RequirementEvidenceRefreshStop,
                materializer.MaterializationStop,
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
        "jobs_with_skills": sum(int(item.get("job_skill_count") or 0) > 0 for item in proposals),
        "jsonld_jobposting_count": sum(int(item.get("jsonld_jobposting_count") or 0) > 0 for item in proposals),
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


def apply_plan(
    plan: Mapping[str, object],
    *,
    authorized_sources: set[str],
    applied_by: str,
) -> dict[str, int]:
    _require(int(plan.get("blocked_count") or 0) == 0, "blocked cohort rows forbid Apply")
    raw_proposals = plan.get("proposals")
    _require(isinstance(raw_proposals, list), "plan proposals missing")
    proposals = [item for item in raw_proposals if isinstance(item, Mapping)]

    inserted = 0
    updated = 0
    already_current = 0
    conn = psycopg.connect(**materializer.get_database_config(), row_factory=dict_row)
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.job_product_assessment_revisions') AS relation")
                revision = cur.fetchone()
                _require(
                    revision is not None and revision["relation"] is not None,
                    "revision table missing",
                )
                cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (REVISION_PREFIX,))

            for proposal in proposals:
                silver_job_id = int(proposal["silver_job_id"])
                mode = str(proposal.get("mode") or "")
                next_payload = proposal.get("next_payload")
                _require(isinstance(next_payload, Mapping), "proposal next payload missing")

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
                current_rows = materializer._load_candidate_rows(
                    conn,
                    source_names=(),
                    silver_job_ids=(silver_job_id,),
                )
                _require(
                    len(current_rows) == 1,
                    f"missing-assessment eligibility changed before Apply: {silver_job_id}",
                )
                materializer.validate_materialization_authority(
                    current_rows[0],
                    authorized_sources=authorized_sources,
                )
                existing = materializer._load_existing(conn, silver_job_id, lock=True)
                _require(existing is None, f"assessment appeared before Apply: {silver_job_id}")
                materializer._insert_assessment(conn, next_payload)
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


def _load_inputs() -> tuple[list[dict[str, object]], list[dict[str, object]], set[str], str]:
    repository = JobIngestionRepository()
    authorized_sources = materializer.authorized_recurring_employer_origin_sources(repository)
    with psycopg.connect(**materializer.get_database_config(), row_factory=dict_row) as conn:
        existing = refresh._load_rows(conn)
        missing = materializer._load_candidate_rows(
            conn,
            source_names=(),
            silver_job_ids=(),
        )
        policy_version = materializer._load_policy_version(conn)
        conn.rollback()
    return existing, missing, authorized_sources, policy_version


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
        _require(args.approval_token == APPROVAL_TOKEN, "invalid F4A-R2 approval token")
    _require(bool(args.applied_by.strip()), "applied_by must not be blank")

    existing, missing, authorized_sources, policy_version = _load_inputs()
    _require(bool(existing or missing), "no lifecycle-current Product jobs found")
    report = build_plan(
        existing_rows=existing,
        missing_rows=missing,
        authorized_sources=authorized_sources,
        policy_version=policy_version,
    )
    result = {"inserted": 0, "updated": 0, "already_current": 0}
    if args.apply:
        result = apply_plan(
            report,
            authorized_sources=authorized_sources,
            applied_by=args.applied_by.strip(),
        )
        report = dict(report)
        report["mode"] = "apply"
        report["apply_result"] = result
        report["boundaries"] = {
            **dict(report["boundaries"]),
            "database_writes": bool(result["inserted"] or result["updated"]),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(_json_safe(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
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
