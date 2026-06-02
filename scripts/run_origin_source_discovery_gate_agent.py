"""Run the S7D Origin Source Discovery Gate agent.

The agent evaluates persisted URL evidence only. It does not browse or probe the
web and it never activates sources, registers connectors, writes Bronze data or
changes scheduler state.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.search_intelligence.origin_source_discovery import (
    CandidateUrlEvidence,
    decide_origin_source,
    decision_to_json,
)


def db_connect() -> psycopg.Connection[Any]:
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "job_pipeline"),
        user=os.getenv("POSTGRES_USER", "job_user"),
        password=os.getenv("POSTGRES_PASSWORD", "job_password"),
        row_factory=dict_row,
    )


def load_candidate(conn: psycopg.Connection[Any], company_key: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, company_key, company_name, candidate_url, status,
                   source_name_candidate, source_type_candidate
            FROM employer_origin_source_candidates
            WHERE company_key = %s
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (company_key,),
        )
        row = cur.fetchone()
    if row is None:
        raise SystemExit(f"No employer-origin source candidate found for company_key={company_key!r}.")
    return dict(row)


def load_url_evidence(conn: psycopg.Connection[Any], candidate: dict[str, Any]) -> list[CandidateUrlEvidence]:
    evidence: list[CandidateUrlEvidence] = []
    candidate_url = candidate.get("candidate_url")
    if candidate_url:
        evidence.append(
            CandidateUrlEvidence(
                url=str(candidate_url),
                evidence_source="employer_origin_source_candidates.candidate_url",
                source_priority=10,
                evidence={"candidate_id": candidate["id"]},
            )
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT evidence_url, source_name, title, observed_at
            FROM aggregator_novelty_items
            WHERE known_candidate_id = %s
               OR company_key = %s
            ORDER BY observed_at DESC NULLS LAST, created_at DESC
            LIMIT 20
            """,
            (candidate["id"], candidate["company_key"]),
        )
        for row in cur.fetchall():
            if row.get("evidence_url"):
                evidence.append(
                    CandidateUrlEvidence(
                        url=str(row["evidence_url"]),
                        evidence_source="aggregator_novelty_items.evidence_url",
                        source_priority=40,
                        evidence={
                            "source_name": row.get("source_name"),
                            "title": row.get("title"),
                            "observed_at": str(row.get("observed_at")),
                        },
                    )
                )
    return evidence


def persist_decision(
    conn: psycopg.Connection[Any],
    candidate_id: int,
    decision: dict[str, Any],
    reviewed_by: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO employer_origin_source_discovery_reviews (
                candidate_id,
                discovery_status,
                decision,
                selected_origin_url,
                selected_domain,
                selected_source_type,
                confidence_score,
                risk_level,
                blocker_code,
                reason,
                alternatives,
                rejected_urls,
                evidence,
                reviewed_by,
                updated_at
            ) VALUES (
                %(candidate_id)s,
                %(discovery_status)s,
                %(decision)s,
                %(selected_origin_url)s,
                %(selected_domain)s,
                %(selected_source_type)s,
                %(confidence_score)s,
                %(risk_level)s,
                %(blocker_code)s,
                %(reason)s,
                %(alternatives)s::jsonb,
                %(rejected_urls)s::jsonb,
                %(evidence)s::jsonb,
                %(reviewed_by)s,
                now()
            )
            ON CONFLICT (candidate_id) DO UPDATE SET
                discovery_status = EXCLUDED.discovery_status,
                decision = EXCLUDED.decision,
                selected_origin_url = EXCLUDED.selected_origin_url,
                selected_domain = EXCLUDED.selected_domain,
                selected_source_type = EXCLUDED.selected_source_type,
                confidence_score = EXCLUDED.confidence_score,
                risk_level = EXCLUDED.risk_level,
                blocker_code = EXCLUDED.blocker_code,
                reason = EXCLUDED.reason,
                alternatives = EXCLUDED.alternatives,
                rejected_urls = EXCLUDED.rejected_urls,
                evidence = EXCLUDED.evidence,
                reviewed_by = EXCLUDED.reviewed_by,
                updated_at = now()
            """,
            {
                "candidate_id": candidate_id,
                "discovery_status": decision["discovery_status"],
                "decision": decision["decision"],
                "selected_origin_url": decision["selected_origin_url"],
                "selected_domain": decision["selected_domain"],
                "selected_source_type": decision["selected_source_type"],
                "confidence_score": decision["confidence_score"],
                "risk_level": decision["risk_level"],
                "blocker_code": decision["blocker_code"],
                "reason": decision["reason"],
                "alternatives": json.dumps(decision["alternatives"]),
                "rejected_urls": json.dumps(decision["rejected_urls"]),
                "evidence": json.dumps({"boundary": decision["boundary"]}),
                "reviewed_by": reviewed_by,
            },
        )
    conn.commit()


def run(company_key: str, reviewed_by: str, write: bool) -> dict[str, Any]:
    with db_connect() as conn:
        candidate = load_candidate(conn, company_key)
        evidence = load_url_evidence(conn, candidate)
        decision = decide_origin_source(
            company_key=str(candidate["company_key"]),
            company_name=str(candidate["company_name"]),
            url_evidence=evidence,
        )
        payload = decision_to_json(decision)
        payload["candidate_id"] = candidate["id"]
        payload["candidate_status"] = candidate.get("status")
        payload["write_requested"] = write
        if write:
            persist_decision(conn, int(candidate["id"]), payload, reviewed_by)
            payload["persisted"] = True
        else:
            payload["persisted"] = False
        return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the S7D origin-source discovery gate.")
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--write", action="store_true", help="Persist the gate result. Dry-run by default.")
    args = parser.parse_args()

    result = run(args.company_key, args.reviewed_by, args.write)
    print("S7D Origin Source Discovery Gate")
    print("boundary: no browsing, no connector registration, no source activation, no Bronze write, no scheduler change")
    print("---")
    for key in (
        "candidate_id",
        "company_key",
        "company_name",
        "discovery_status",
        "decision",
        "selected_origin_url",
        "selected_domain",
        "selected_source_type",
        "confidence_score",
        "risk_level",
        "blocker_code",
        "reason",
        "persisted",
    ):
        print(f"{key}: {result.get(key)}")
    print("---")
    print("alternatives:")
    for item in result["alternatives"]:
        print(f"- {item['normalized_url']} | {item['source_type']} | {item['decision']} | confidence={item['confidence_score']}")
    if result["rejected_urls"]:
        print("---")
        print("rejected_urls:")
        for item in result["rejected_urls"]:
            print(f"- {item['input_url']} | {item['source_type']} | {', '.join(item['reasons'])}")


if __name__ == "__main__":
    main()
