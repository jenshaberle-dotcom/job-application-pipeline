"""Plan/apply the F4A-R3 current-cohort Silver requirement-evidence backfill.

This is the historical-row bridge for the Bronze2E vertical slice. Future normal
Silver writes persist the same sidecar atomically. Existing current rows may
predate generic Bronze detail evidence, so the plan refreshes only each exact
persisted public Origin URL, runs the existing local generic connector parser
(extruct + trafilatura), projects that normalized evidence through the same
Bronze shape in memory, then builds the canonical Silver sidecar. Raw HTML is
never persisted.

Plan mode is read-only. Apply writes only ``silver_job_requirement_evidence`` and
is guarded by an explicit approval token. Candidate Facts, Product decisions,
ranking, Top-5, applications, Bronze rows and Silver identity rows are untouched.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

from scripts import run_f4a_r2_current_requirement_origin_diagnostic as current_scope
from src.config import get_database_config
from src.connectors.generic_job_detail_evidence import (
    extract_generic_job_detail_evidence,
    project_detail_evidence_into_raw_data,
)
from src.search_intelligence.product_v1_downstream_preview import (
    DownstreamPreviewStop,
    fetch_public_https_detail_document,
)
from src.silver.requirement_evidence_projection import (
    SILVER_REQUIREMENT_EVIDENCE_SCHEMA,
    build_silver_requirement_evidence,
    requirement_evidence_hash,
)


REPORT_SCHEMA = "job_application_pipeline.f4a_r3_silver_requirement_backfill.v1"
APPROVAL_TOKEN = "F4A-R3-SILVER-REQUIREMENT-BACKFILL-001"


class BackfillStop(RuntimeError):
    pass


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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


def _review_ids() -> set[int]:
    return current_scope._review_scope_ids(current_scope._operator_review_payload())


def _load_rows(conn: psycopg.Connection[Any], review_ids: set[int]) -> list[dict[str, Any]]:
    if not review_ids:
        return []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                s.id AS silver_job_id,
                s.raw_job_id,
                s.source_name,
                s.source_url,
                s.title,
                s.company_name,
                r.raw_data,
                latest.normalized_evidence
            FROM silver_jobs s
            JOIN raw_jobs r ON r.id = s.raw_job_id
            LEFT JOIN LATERAL (
                SELECT o.normalized_evidence
                FROM job_observations o
                WHERE o.raw_job_id = s.raw_job_id
                  AND o.normalized_evidence IS NOT NULL
                ORDER BY o.observed_at DESC, o.id DESC
                LIMIT 1
            ) latest ON TRUE
            WHERE s.id = ANY(%s)
            ORDER BY s.source_name, s.id
            """,
            (sorted(review_ids),),
        )
        rows = [dict(row) for row in cur.fetchall()]

        cur.execute("SELECT to_regclass('public.silver_job_requirement_evidence') AS relation")
        relation = cur.fetchone()
        if relation is not None and relation["relation"] is not None:
            cur.execute(
                """
                SELECT silver_job_id, evidence_hash, evidence_payload
                FROM silver_job_requirement_evidence
                WHERE silver_job_id = ANY(%s)
                """,
                (sorted(review_ids),),
            )
            existing = {int(row["silver_job_id"]): dict(row) for row in cur.fetchall()}
        else:
            existing = {}

    for row in rows:
        current = existing.get(int(row["silver_job_id"]))
        row["existing_evidence_hash"] = current.get("evidence_hash") if current else None
        row["existing_evidence_payload"] = current.get("evidence_payload") if current else None
    return rows


def _best_raw_data(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _mapping(row.get("normalized_evidence"))
    raw_evidence = normalized.get("raw_evidence")
    if isinstance(raw_evidence, Mapping):
        return deepcopy(dict(raw_evidence))
    raw = row.get("raw_data")
    return deepcopy(dict(raw)) if isinstance(raw, Mapping) else {}


def _unavailable_payload(*, source_url: str, reason: str) -> dict[str, object]:
    fields = {
        "employment_type": {"status": "origin_unavailable", "value": "unknown"},
        "required_languages": {"status": "origin_unavailable", "values": []},
        "weekly_hours": {"status": "origin_unavailable", "minimum": None, "maximum": None},
        "work_model": {"status": "origin_unavailable", "value": "unknown"},
        "requirements_seniority": {"status": "origin_unavailable", "value": "unknown"},
        "job_skills": {"status": "origin_unavailable", "values": []},
    }
    return {
        "schema": SILVER_REQUIREMENT_EVIDENCE_SCHEMA,
        "source_evidence_schema": None,
        "parser_family": "origin_unavailable",
        "methods": [],
        "source_url": source_url,
        "description_source": None,
        "structured_jobposting_found": False,
        "fields": fields,
        "conflicted_fields": [],
        "unresolved_fields": sorted(fields),
        "origin_unavailable_reason": reason,
        "raw_html_persisted": False,
        "authority": {
            "job_source_evidence_only": True,
            "candidate_fact_authority": False,
            "capability_fit_authority": False,
            "hard_filter_authority": False,
            "ranking_authority": False,
            "top5_authority": False,
            "application_authority": False,
        },
    }


def _proposal(row: Mapping[str, Any]) -> dict[str, object]:
    silver_job_id = int(row["silver_job_id"])
    raw_job_id = int(row["raw_job_id"])
    source_url = str(row.get("source_url") or "").strip()
    if not source_url:
        raise BackfillStop("Silver source URL missing")

    try:
        document = fetch_public_https_detail_document(source_url)
        if not _same_origin(source_url, document.final_url):
            raise BackfillStop("detail fetch redirected outside exact Origin")
        evidence = extract_generic_job_detail_evidence(
            html=document.html,
            url=document.final_url,
            page_title=document.title,
        )
        raw_data = project_detail_evidence_into_raw_data(_best_raw_data(row), evidence)
        job = raw_data.get("job")
        if not isinstance(job, dict):
            job = {}
            raw_data["job"] = job
        job["source_url"] = source_url
        if not str(job.get("title") or "").strip():
            job["title"] = str(row.get("title") or "").strip()
        payload = build_silver_requirement_evidence(
            {
                "id": raw_job_id,
                "source_name": row.get("source_name"),
                "source_url": source_url,
                "title": row.get("title"),
                "raw_data": raw_data,
            }
        )
        payload["refresh_binding"] = {
            "mode": "exact_origin_generic_parser_refresh",
            "final_url": document.final_url,
        }
        origin_unavailable = False
    except DownstreamPreviewStop as exc:
        reason = str(exc)
        if reason not in {
            "preview detail returned HTTP 404",
            "preview detail returned HTTP 410",
        }:
            raise
        payload = _unavailable_payload(source_url=source_url, reason=reason)
        origin_unavailable = True

    digest = requirement_evidence_hash(payload)
    previous_hash = str(row.get("existing_evidence_hash") or "") or None
    fields = _mapping(payload.get("fields"))
    status_counts = Counter(
        str(_mapping(value).get("status") or "unknown") for value in fields.values()
    )
    return {
        "silver_job_id": silver_job_id,
        "raw_job_id": raw_job_id,
        "source_name": row.get("source_name"),
        "source_url": source_url,
        "title": row.get("title"),
        "company_name": row.get("company_name"),
        "parser_family": payload.get("parser_family"),
        "structured_jobposting_found": payload.get("structured_jobposting_found") is True,
        "origin_unavailable": origin_unavailable,
        "field_status_counts": dict(sorted(status_counts.items())),
        "evidence_hash": digest,
        "previous_evidence_hash": previous_hash,
        "would_change": previous_hash != digest,
        "payload": payload,
    }


def build_plan(rows: list[Mapping[str, Any]]) -> dict[str, object]:
    proposals: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []
    for row in rows:
        try:
            proposals.append(_proposal(row))
        except (BackfillStop, DownstreamPreviewStop, ValueError) as exc:
            blocked.append(
                {
                    "silver_job_id": row.get("silver_job_id"),
                    "source_name": row.get("source_name"),
                    "source_url": row.get("source_url"),
                    "title": row.get("title"),
                    "reason": str(exc),
                }
            )

    parser_families = Counter(str(item["parser_family"]) for item in proposals)
    field_statuses: Counter[str] = Counter()
    for item in proposals:
        for status, count in _mapping(item.get("field_status_counts")).items():
            field_statuses[str(status)] += int(count)

    reachable = [item for item in proposals if not item["origin_unavailable"]]
    reachable_with_any_observed = sum(
        any(
            str(_mapping(field).get("status") or "").startswith("observed_")
            for field in _mapping(item["payload"].get("fields")).values()
        )
        for item in reachable
    )
    return {
        "schema": REPORT_SCHEMA,
        "mode": "plan",
        "candidate_count": len(rows),
        "proposal_count": len(proposals),
        "blocked_count": len(blocked),
        "origin_unavailable_count": sum(bool(item["origin_unavailable"]) for item in proposals),
        "reachable_count": len(reachable),
        "reachable_with_any_observed_requirement_count": reachable_with_any_observed,
        "reachable_with_any_observed_requirement_ratio": (
            reachable_with_any_observed / len(reachable) if reachable else 0.0
        ),
        "would_change_count": sum(bool(item["would_change"]) for item in proposals),
        "parser_family_counts": dict(sorted(parser_families.items())),
        "field_status_counts": dict(sorted(field_statuses.items())),
        "proposals": proposals,
        "blocked": blocked,
        "boundaries": {
            "bronze_writes": 0,
            "silver_identity_writes": 0,
            "candidate_fact_reads": 0,
            "product_decision_writes": 0,
            "ranking_authority": 0,
            "top5_authority": 0,
            "application_authority": 0,
            "raw_html_persisted": 0,
        },
    }


def _upsert_payload(cur: Any, proposal: Mapping[str, object]) -> None:
    payload = proposal["payload"]
    assert isinstance(payload, Mapping)
    cur.execute(
        """
        INSERT INTO silver_job_requirement_evidence (
            silver_job_id, raw_job_id, evidence_schema, source_evidence_schema,
            parser_family, evidence_hash, evidence_payload
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (silver_job_id)
        DO UPDATE SET
            raw_job_id = EXCLUDED.raw_job_id,
            evidence_schema = EXCLUDED.evidence_schema,
            source_evidence_schema = EXCLUDED.source_evidence_schema,
            parser_family = EXCLUDED.parser_family,
            evidence_hash = EXCLUDED.evidence_hash,
            evidence_payload = EXCLUDED.evidence_payload,
            updated_at = NOW()
        WHERE silver_job_requirement_evidence.evidence_hash IS DISTINCT FROM EXCLUDED.evidence_hash
           OR silver_job_requirement_evidence.raw_job_id IS DISTINCT FROM EXCLUDED.raw_job_id
        """,
        (
            int(proposal["silver_job_id"]),
            int(proposal["raw_job_id"]),
            SILVER_REQUIREMENT_EVIDENCE_SCHEMA,
            payload.get("source_evidence_schema"),
            str(payload.get("parser_family") or "unclassified"),
            str(proposal["evidence_hash"]),
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
        ),
    )


def apply_plan(conn: psycopg.Connection[Any], report: Mapping[str, object]) -> int:
    if int(report.get("blocked_count") or 0) != 0:
        raise BackfillStop("refusing Apply while current-cohort proposals are blocked")
    proposals = report.get("proposals")
    if not isinstance(proposals, list):
        raise BackfillStop("plan proposals missing")

    applied = 0
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.silver_job_requirement_evidence') AS relation")
            relation = cur.fetchone()
            if relation is None or relation["relation"] is None:
                raise BackfillStop("Silver requirement sidecar migration is not applied")

            for proposal in proposals:
                if not isinstance(proposal, Mapping):
                    raise BackfillStop("invalid proposal payload")
                cur.execute(
                    "SELECT raw_job_id, source_url FROM silver_jobs WHERE id = %s FOR UPDATE",
                    (int(proposal["silver_job_id"]),),
                )
                current = cur.fetchone()
                if current is None:
                    raise BackfillStop("Silver row disappeared before Apply")
                if int(current["raw_job_id"]) != int(proposal["raw_job_id"]):
                    raise BackfillStop("Silver raw binding changed before Apply")
                if str(current["source_url"] or "") != str(proposal["source_url"] or ""):
                    raise BackfillStop("Silver Origin URL changed before Apply")
                _upsert_payload(cur, proposal)
                applied += 1
    return applied


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit("F4A_R3_SILVER_REQUIREMENT_APPROVAL_TOKEN_REQUIRED")

    review_ids = _review_ids()
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        rows = _load_rows(conn, review_ids)
        conn.rollback()

    report = build_plan(rows)
    print(f"F4A_R3_SILVER_REQUIREMENT_CANDIDATES={report['candidate_count']}")
    print(f"F4A_R3_SILVER_REQUIREMENT_PROPOSALS={report['proposal_count']}")
    print(f"F4A_R3_SILVER_REQUIREMENT_BLOCKED={report['blocked_count']}")
    print(f"F4A_R3_SILVER_REQUIREMENT_UNAVAILABLE={report['origin_unavailable_count']}")
    print(f"F4A_R3_SILVER_REQUIREMENT_REACHABLE={report['reachable_count']}")
    print(
        "F4A_R3_SILVER_REQUIREMENT_OBSERVED_RATIO="
        f"{report['reachable_with_any_observed_requirement_ratio']:.4f}"
    )
    print(f"F4A_R3_SILVER_REQUIREMENT_WOULD_CHANGE={report['would_change_count']}")
    print(
        "F4A_R3_SILVER_REQUIREMENT_PARSER_FAMILIES="
        + json.dumps(report["parser_family_counts"], sort_keys=True)
    )
    print(
        "F4A_R3_SILVER_REQUIREMENT_FIELD_STATUSES="
        + json.dumps(report["field_status_counts"], sort_keys=True)
    )

    if args.apply:
        if int(report["blocked_count"]) != 0:
            raise SystemExit("F4A_R3_SILVER_REQUIREMENT_BLOCKED_APPLY")
        with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
            applied = apply_plan(conn, report)
        report["mode"] = "apply"
        report["applied_count"] = applied
        print(f"F4A_R3_SILVER_REQUIREMENT_APPLIED={applied}")
    else:
        print("F4A_R3_SILVER_REQUIREMENT_PLAN=PASS")

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
