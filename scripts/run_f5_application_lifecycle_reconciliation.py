"""Read-only F5 application-lifecycle reconciliation.

F5 must not invent a submitted application, response, interview or outcome merely
because drafting state or future-state UI copy exists.  This diagnostic measures
the real PostgreSQL application-shaped relations and the current Control Center
surface before any lifecycle schema or Gmail bridge is introduced.

Boundary: database reads only, no provider calls, no Gmail access, no network
probes, no application-state mutation and no send/submit action.
"""
from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig

ROOT = Path(__file__).resolve().parents[1]


class ReconciliationStop(RuntimeError):
    """Fail closed when the diagnostic input is structurally invalid."""


def _json_safe(value: object) -> object:
    if isinstance(value, datetime):
        current = value
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc).isoformat()
    return value


def _relation_columns(cur: psycopg.Cursor[dict[str, Any]], relation: str) -> list[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (relation,),
    )
    return [str(row["column_name"]) for row in cur.fetchall()]


def _constraint_definitions(
    cur: psycopg.Cursor[dict[str, Any]], relation: str
) -> list[dict[str, str]]:
    cur.execute(
        """
        SELECT con.conname AS name, pg_get_constraintdef(con.oid) AS definition
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace ns ON ns.oid = rel.relnamespace
        WHERE ns.nspname = 'public'
          AND rel.relname = %s
        ORDER BY con.conname
        """,
        (relation,),
    )
    return [
        {"name": str(row["name"]), "definition": str(row["definition"])}
        for row in cur.fetchall()
    ]


def load_database_snapshot() -> dict[str, object]:
    """Measure application-shaped persistence in one read-only transaction."""

    with psycopg.connect(DatabaseConfig.from_environment().dsn(), row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    rel.relname AS relation_name,
                    rel.relkind AS relation_kind
                FROM pg_class rel
                JOIN pg_namespace ns ON ns.oid = rel.relnamespace
                WHERE ns.nspname = 'public'
                  AND rel.relkind IN ('r', 'p', 'v', 'm')
                  AND (
                      rel.relname LIKE 'application%'
                      OR rel.relname LIKE 'gold_product_v1_application%'
                  )
                ORDER BY rel.relname
                """
            )
            relations = [
                {
                    "name": str(row["relation_name"]),
                    "kind": str(row["relation_kind"]),
                }
                for row in cur.fetchall()
            ]

            for relation in relations:
                name = str(relation["name"])
                relation["columns"] = _relation_columns(cur, name)
                relation["constraints"] = _constraint_definitions(cur, name)

            relation_names = {str(item["name"]) for item in relations}

            source_documents: dict[str, object] = {
                "present": "application_source_documents" in relation_names,
                "row_count": 0,
                "status_counts": {},
                "document_type_counts": {},
            }
            if source_documents["present"]:
                cur.execute("SELECT count(*)::integer AS count FROM application_source_documents")
                source_documents["row_count"] = int(cur.fetchone()["count"])
                cur.execute(
                    """
                    SELECT status, count(*)::integer AS count
                    FROM application_source_documents
                    GROUP BY status
                    ORDER BY status
                    """
                )
                source_documents["status_counts"] = {
                    str(row["status"]): int(row["count"]) for row in cur.fetchall()
                }
                cur.execute(
                    """
                    SELECT document_type, count(*)::integer AS count
                    FROM application_source_documents
                    GROUP BY document_type
                    ORDER BY document_type
                    """
                )
                source_documents["document_type_counts"] = {
                    str(row["document_type"]): int(row["count"])
                    for row in cur.fetchall()
                }

            draft_requests: dict[str, object] = {
                "present": "application_draft_requests" in relation_names,
                "row_count": 0,
                "distinct_job_count": 0,
                "status_counts": {},
                "latest_created_at": None,
                "latest_updated_at": None,
            }
            if draft_requests["present"]:
                cur.execute(
                    """
                    SELECT
                        count(*)::integer AS row_count,
                        count(DISTINCT silver_job_id)::integer AS distinct_job_count,
                        max(created_at) AS latest_created_at,
                        max(updated_at) AS latest_updated_at
                    FROM application_draft_requests
                    """
                )
                row = cur.fetchone()
                draft_requests.update(
                    {
                        "row_count": int(row["row_count"] or 0),
                        "distinct_job_count": int(row["distinct_job_count"] or 0),
                        "latest_created_at": _json_safe(row["latest_created_at"]),
                        "latest_updated_at": _json_safe(row["latest_updated_at"]),
                    }
                )
                cur.execute(
                    """
                    SELECT status, count(*)::integer AS count
                    FROM application_draft_requests
                    GROUP BY status
                    ORDER BY status
                    """
                )
                draft_requests["status_counts"] = {
                    str(row["status"]): int(row["count"]) for row in cur.fetchall()
                }

            readiness: dict[str, object] = {
                "present": "gold_product_v1_application_readiness" in relation_names,
                "row_count": 0,
            }
            if readiness["present"]:
                cur.execute(
                    "SELECT count(*)::integer AS count FROM gold_product_v1_application_readiness"
                )
                readiness["row_count"] = int(cur.fetchone()["count"])

            return {
                "relations": relations,
                "source_documents": source_documents,
                "draft_requests": draft_requests,
                "application_readiness": readiness,
            }


def surface_contract_evidence() -> dict[str, object]:
    """Inspect the active public UI contract without executing it."""

    workspace = (ROOT / "frontend/control-center/src/OperatorWorkspace.tsx").read_text(
        encoding="utf-8"
    )
    payload_type = workspace.split("type ProductPayload =", 1)[1].split("type View =", 1)[0]
    return {
        "applications_surface_present": "function Applications" in workspace,
        "static_no_submitted_copy_present": "No submitted applications yet" in workspace,
        "manual_submission_boundary_present": "Submission is manual" in workspace,
        "future_interview_copy_present": "Future tracking can hold interview dates" in workspace,
        "future_decision_copy_present": "Offer, rejected and withdrawn" in workspace,
        "product_payload_has_application_portfolio_field": (
            "applications:" in payload_type
            or "application_portfolio:" in payload_type
            or "application_events:" in payload_type
        ),
    }


def _as_mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReconciliationStop(f"{name.upper()}_INVALID")
    return value


def reconcile(
    snapshot: Mapping[str, object],
    *,
    source_sha: str,
    observed_at: datetime,
    surface_evidence: Mapping[str, object],
) -> dict[str, object]:
    raw_relations = snapshot.get("relations")
    if not isinstance(raw_relations, Sequence) or isinstance(raw_relations, (str, bytes)):
        raise ReconciliationStop("RELATIONS_INVALID")

    relations: list[dict[str, object]] = []
    for raw in raw_relations:
        if not isinstance(raw, Mapping):
            raise ReconciliationStop("RELATION_ROW_INVALID")
        name = str(raw.get("name") or "").strip()
        if not name:
            raise ReconciliationStop("RELATION_NAME_MISSING")
        columns_raw = raw.get("columns") or []
        constraints_raw = raw.get("constraints") or []
        columns = [str(item) for item in columns_raw] if isinstance(columns_raw, Sequence) else []
        constraints = (
            [dict(item) for item in constraints_raw if isinstance(item, Mapping)]
            if isinstance(constraints_raw, Sequence)
            else []
        )
        relations.append(
            {
                "name": name,
                "kind": str(raw.get("kind") or "unknown"),
                "columns": columns,
                "constraints": constraints,
            }
        )

    source_documents = _as_mapping(snapshot.get("source_documents"), name="source_documents")
    draft_requests = _as_mapping(snapshot.get("draft_requests"), name="draft_requests")
    readiness = _as_mapping(snapshot.get("application_readiness"), name="application_readiness")

    status_counts_raw = draft_requests.get("status_counts") or {}
    if not isinstance(status_counts_raw, Mapping):
        raise ReconciliationStop("DRAFT_STATUS_COUNTS_INVALID")
    status_counts = Counter(
        {str(key): int(value or 0) for key, value in status_counts_raw.items()}
    )

    relation_names = [str(item["name"]) for item in relations]
    post_submit_keywords = (
        "submission",
        "submitted",
        "event",
        "outcome",
        "response",
        "communication",
        "interview",
    )
    post_submit_candidate_relations = sorted(
        name
        for name in relation_names
        if name not in {
            "application_source_documents",
            "application_draft_requests",
            "gold_product_v1_application_readiness",
        }
        and any(keyword in name.lower() for keyword in post_submit_keywords)
    )

    submitted_like_status_count = sum(
        count
        for status, count in status_counts.items()
        if any(token in status.lower() for token in ("submit", "applied", "interview", "offer", "reject", "withdraw"))
    )

    return {
        "schema": "jap.f5.application_lifecycle_reconciliation.v1",
        "source_sha": source_sha,
        "observed_at": observed_at.astimezone(timezone.utc).isoformat(),
        "authority": "diagnostic_only_no_application_lifecycle_mutation",
        "summary": {
            "application_relation_count": len(relations),
            "application_source_document_count": int(source_documents.get("row_count") or 0),
            "application_draft_request_count": int(draft_requests.get("row_count") or 0),
            "application_draft_distinct_job_count": int(
                draft_requests.get("distinct_job_count") or 0
            ),
            "application_draft_status_counts": dict(sorted(status_counts.items())),
            "operator_approved_draft_count": int(status_counts.get("approved_by_operator", 0)),
            "submitted_like_draft_status_count": submitted_like_status_count,
            "application_readiness_row_count": int(readiness.get("row_count") or 0),
            "post_submit_candidate_relation_count": len(post_submit_candidate_relations),
            "persisted_application_portfolio_projected_to_ui": bool(
                surface_evidence.get("product_payload_has_application_portfolio_field")
            ),
        },
        "relations": relations,
        "source_documents": dict(source_documents),
        "draft_requests": dict(draft_requests),
        "application_readiness": dict(readiness),
        "post_submit_candidate_relations": post_submit_candidate_relations,
        "surface_contract_evidence": dict(surface_evidence),
        "authority_findings": {
            "draft_request_is_submission_authority": False,
            "draft_or_operator_approval_implies_submitted": False,
            "relation_name_alone_creates_lifecycle_authority": False,
            "current_f5_contract_defines_submission_authority_store": False,
            "current_ui_may_invent_submitted_application": False,
            "gmail_evidence_is_application_state_authority": False,
        },
        "boundaries": {
            "db_writes": 0,
            "provider_calls": 0,
            "network_probes": 0,
            "gmail_reads": 0,
            "email_actions": 0,
            "application_submission_actions": 0,
            "application_state_mutations": 0,
            "ranking_authority_changed": False,
            "top5_authority_changed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = reconcile(
        load_database_snapshot(),
        source_sha=args.source_sha,
        observed_at=datetime.now(timezone.utc),
        surface_evidence=surface_contract_evidence(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    summary = report["summary"]
    print(f"F5_SOURCE_SHA={report['source_sha']}")
    print(f"F5_APPLICATION_RELATIONS={summary['application_relation_count']}")
    print(f"F5_DRAFT_REQUESTS={summary['application_draft_request_count']}")
    print(f"F5_DRAFT_JOBS={summary['application_draft_distinct_job_count']}")
    print(f"F5_DRAFT_STATUS_COUNTS={json.dumps(summary['application_draft_status_counts'], sort_keys=True)}")
    print(f"F5_SUBMITTED_LIKE_DRAFT_STATUSES={summary['submitted_like_draft_status_count']}")
    print(f"F5_POST_SUBMIT_CANDIDATE_RELATIONS={summary['post_submit_candidate_relation_count']}")
    print("F5_DATABASE_WRITES=0")
    print("F5_PROVIDER_CALLS=0")
    print("F5_GMAIL_READS=0")
    print("F5_EMAIL_ACTIONS=0")
    print("F5_APPLICATION_STATE_MUTATIONS=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
