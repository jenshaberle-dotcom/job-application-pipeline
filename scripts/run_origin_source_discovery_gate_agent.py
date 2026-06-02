"""Run the S7D/S7H Origin Source Discovery Gate agent.

The agent evaluates persisted URL evidence and optional human-provided URL
review evidence only. It does not browse or probe the web and it never activates
sources, registers connectors, writes Bronze data or changes scheduler state.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
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


def load_candidate_keys(
    conn: psycopg.Connection[Any],
    *,
    include_active: bool = False,
    limit: int | None = None,
) -> list[str]:
    """Load candidate keys for portfolio-wide origin-source gate review."""

    status_filter = ""
    if not include_active:
        status_filter = "WHERE coalesce(status, '') <> 'active_controlled'"

    limit_clause = ""
    params: list[Any] = []
    if limit is not None:
        limit_clause = "LIMIT %s"
        params.append(limit)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT company_key
            FROM employer_origin_source_candidates
            {status_filter}
            ORDER BY updated_at DESC NULLS LAST, id DESC
            {limit_clause}
            """,
            params,
        )
        return [str(row["company_key"]) for row in cur.fetchall()]


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
                "evidence": json.dumps({
                    "boundary": decision["boundary"],
                    "candidate_url_auto_assignment_allowed": decision.get("candidate_url_auto_assignment_allowed", False),
                    "candidate_url_auto_assignment_reason": decision.get("candidate_url_auto_assignment_reason"),
                    "candidate_url_auto_assignment_result": decision.get("candidate_url_auto_assignment_result"),
                }),
                "reviewed_by": reviewed_by,
            },
        )
    conn.commit()


def maybe_auto_assign_candidate_url(
    conn: psycopg.Connection[Any],
    candidate: dict[str, Any],
    decision: dict[str, Any],
    reviewed_by: str,
) -> str:
    """Persist a trusted selected origin URL on the candidate without extra approval.

    This is deliberately only URL evidence assignment. It does not approve the
    candidate, build/register a connector, activate a source, write Bronze data or
    change schedules. Conflicting existing candidate URLs are left untouched for
    manual review.
    """

    if not decision.get("candidate_url_auto_assignment_allowed"):
        return "not_allowed"
    selected_url = decision.get("selected_origin_url")
    if not selected_url:
        return "not_selected"

    existing_url = str(candidate.get("candidate_url") or "").strip()
    if existing_url == selected_url:
        return "already_set"
    if existing_url and existing_url != selected_url:
        return "manual_review_required_conflicting_candidate_url"

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE employer_origin_source_candidates
            SET candidate_url = %s::text,
                source_type_candidate = COALESCE(%s::text, source_type_candidate),
                notes = concat_ws(
                    ' ',
                    nullif(notes, ''),
                    %s::text
                ),
                updated_at = now()
            WHERE id = %s::bigint
              AND candidate_url IS NULL
            """,
            (
                selected_url,
                decision.get("selected_source_type"),
                f"Origin URL assigned by trusted URL evidence policy; reviewed_by={reviewed_by}.",
                candidate["id"],
            ),
        )
    conn.commit()
    return "applied"


def run(
    company_key: str,
    reviewed_by: str,
    write: bool,
    manual_origin_url: str | None = None,
) -> dict[str, Any]:
    with db_connect() as conn:
        candidate = load_candidate(conn, company_key)
        evidence = load_url_evidence(conn, candidate)
        if manual_origin_url:
            evidence.append(
                CandidateUrlEvidence(
                    url=manual_origin_url,
                    evidence_source="manual_origin_url_review_override",
                    source_priority=1,
                    evidence={
                        "reviewed_by": reviewed_by,
                        "manual_input": True,
                        "boundary": "same URL safety policy as automatic evidence",
                    },
                )
            )
        decision = decide_origin_source(
            company_key=str(candidate["company_key"]),
            company_name=str(candidate["company_name"]),
            url_evidence=evidence,
        )
        payload = decision_to_json(decision)
        payload["candidate_id"] = candidate["id"]
        payload["candidate_status"] = candidate.get("status")
        payload["candidate_url_before"] = candidate.get("candidate_url")
        payload["manual_origin_url_provided"] = bool(manual_origin_url)
        payload["write_requested"] = write
        if write:
            assignment_result = maybe_auto_assign_candidate_url(conn, candidate, payload, reviewed_by)
            payload["candidate_url_auto_assignment_result"] = assignment_result
            persist_decision(conn, int(candidate["id"]), payload, reviewed_by)
            payload["persisted"] = True
        else:
            payload["candidate_url_auto_assignment_result"] = (
                "already_set_dry_run"
                if payload.get("candidate_url_auto_assignment_allowed")
                else "not_allowed"
            )
            payload["persisted"] = False
        return payload


def run_portfolio(
    *,
    reviewed_by: str,
    write: bool,
    include_active: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Run the discovery gate for all candidate records selected from the DB."""

    with db_connect() as conn:
        company_keys = load_candidate_keys(conn, include_active=include_active, limit=limit)
    return [run(company_key, reviewed_by, write) for company_key in company_keys]


def summarize_portfolio_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Return stable counts for CLI output and tests."""

    statuses = Counter(str(item.get("discovery_status") or "unknown") for item in results)
    blockers = Counter(str(item.get("blocker_code") or "none") for item in results)
    decisions = Counter(str(item.get("decision") or "unknown") for item in results)
    return {
        "candidate_count": len(results),
        "status_counts": dict(sorted(statuses.items())),
        "decision_counts": dict(sorted(decisions.items())),
        "blocker_counts": dict(sorted(blockers.items())),
        "selected_count": statuses.get("selected", 0),
        "manual_review_count": decisions.get("manual_review_required", 0),
        "blocked_count": statuses.get("blocked_unsafe_url", 0),
    }


def print_single_result(result: dict[str, Any]) -> None:
    print("S7M Manual Origin URL Review Override")
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
        "candidate_url_auto_assignment_allowed",
        "candidate_url_auto_assignment_reason",
        "candidate_url_auto_assignment_result",
        "manual_origin_url_provided",
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


def print_portfolio_results(results: list[dict[str, Any]]) -> None:
    summary = summarize_portfolio_results(results)
    print("S7L Origin Source URL Assignment Policy")
    print("boundary: no browsing, no connector registration, no source activation, no Bronze write, no scheduler change")
    print("---")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print("---")
    print("candidates:")
    for item in results:
        selected = item.get("selected_origin_url") or "-"
        blocker = item.get("blocker_code") or "none"
        print(
            "- "
            f"{item.get('company_name')} [{item.get('company_key')}] | "
            f"status={item.get('discovery_status')} | "
            f"decision={item.get('decision')} | "
            f"selected={selected} | "
            f"url_assignment={item.get('candidate_url_auto_assignment_result')} | "
            f"blocker={blocker} | "
            f"persisted={item.get('persisted')}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the origin-source discovery gate.")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--company-key")
    scope.add_argument("--all-candidates", action="store_true", help="Run the gate for all employer-origin candidates.")
    parser.add_argument("--include-active", action="store_true", help="Include active controlled sources in portfolio mode.")
    parser.add_argument("--limit", type=int, help="Limit candidate count in portfolio mode.")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument(
        "--manual-origin-url",
        help=(
            "Human-provided candidate origin URL for one company. The URL still runs through "
            "the same HTTPS/public-domain/aggregator/career-path policy before it can be written."
        ),
    )
    parser.add_argument("--write", action="store_true", help="Persist gate result(s). Dry-run by default.")
    args = parser.parse_args()

    if args.manual_origin_url and not args.company_key:
        raise SystemExit("--manual-origin-url can only be used together with --company-key.")

    if args.company_key:
        result = run(
            args.company_key,
            args.reviewed_by,
            args.write,
            manual_origin_url=args.manual_origin_url,
        )
        print_single_result(result)
        return

    results = run_portfolio(
        reviewed_by=args.reviewed_by,
        write=args.write,
        include_active=args.include_active,
        limit=args.limit,
    )
    print_portfolio_results(results)


if __name__ == "__main__":
    main()
