from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_detail_evidence_repair_agent import (
    DEFAULT_SEARCH_PROVIDER,
    DEFAULT_SEARCH_QUERY_LIMIT,
    DEFAULT_SEARCH_RESULT_LIMIT,
    SUPPORTED_SEARCH_PROVIDERS,
    SourceCandidate,
    build_repair_outcome,
    build_terms,
    load_local_env_file,
)
from src.config import get_database_config
from src.search_intelligence.detail001_detail_evidence_discovery import (
    BOUNDARY,
    DETAIL_EVIDENCE_GATE,
    CandidateDetailEvidenceSnapshot,
    DetailEvidencePlan,
    DetailProbeEvidence,
    GateSnapshot,
    build_detail_evidence_plan,
    early_gates_ready,
    normalize_url,
    report_payload,
    render_markdown,
)

DEFAULT_OUTPUT_DIR = Path("exports/detail001_detail_evidence_discovery")
EVIDENCE_TABLE = "employer_origin_job_detail_evidence"


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def db_object_exists(conn: psycopg.Connection[Any], object_name: str) -> bool:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT to_regclass(%s) AS object_name", (object_name,))
        row = cur.fetchone()
    return bool(row and row["object_name"])


def load_candidate(conn: psycopg.Connection[Any], company_key: str) -> SourceCandidate:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                id,
                company_key,
                company_name,
                candidate_url,
                source_name_candidate,
                source_family_candidate,
                source_target_candidate,
                source_type_candidate,
                status,
                risk_level
            FROM employer_origin_source_candidates
            WHERE company_key = %s
            ORDER BY updated_at DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (company_key,),
        )
        row = cur.fetchone()
    if row is None:
        raise SystemExit(f"No employer-origin candidate found for company_key={company_key!r}.")
    return SourceCandidate(
        id=int(row["id"]),
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        candidate_url=str(row["candidate_url"] or ""),
        source_name_candidate=str(row["source_name_candidate"] or ""),
        source_family_candidate=str(row["source_family_candidate"] or ""),
        source_target_candidate=row["source_target_candidate"],
        source_type_candidate=str(row["source_type_candidate"] or ""),
        status=str(row["status"] or ""),
        risk_level=str(row["risk_level"] or ""),
    )


def candidate_snapshot(candidate: SourceCandidate) -> CandidateDetailEvidenceSnapshot:
    return CandidateDetailEvidenceSnapshot(
        candidate_id=candidate.id,
        company_key=candidate.company_key,
        company_name=candidate.company_name,
        status=candidate.status,
        candidate_url=normalize_url(candidate.candidate_url),
    )


def load_gates(conn: psycopg.Connection[Any], candidate_id: int) -> tuple[GateSnapshot, ...]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT gate_name, gate_status, decision, evidence
            FROM employer_origin_candidate_gate_reviews
            WHERE candidate_id = %s
            """,
            (candidate_id,),
        )
        rows = cur.fetchall()
    return tuple(
        GateSnapshot(
            gate_name=str(row["gate_name"]),
            gate_status=str(row["gate_status"]),
            decision=row["decision"],
            evidence=dict(row["evidence"] or {}),
        )
        for row in rows
    )


def load_gate_mapping(conn: psycopg.Connection[Any], candidate_id: int) -> dict[str, dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT *
            FROM employer_origin_candidate_gate_reviews
            WHERE candidate_id = %s
            """,
            (candidate_id,),
        )
        return {str(row["gate_name"]): dict(row) for row in cur.fetchall()}


def probes_from_repair_outcome(outcome) -> tuple[DetailProbeEvidence, ...]:
    probes: list[DetailProbeEvidence] = []
    for detail in outcome.details:
        probes.append(
            DetailProbeEvidence(
                url=detail.url,
                final_url=detail.final_url,
                status_code=detail.status_code,
                title=detail.title,
                response_bytes=detail.html_bytes,
                profile_hits=tuple(detail.profile_terms),
                location_hits=tuple(detail.location_terms),
                remote_hits=(),
                flexibility_hits=(),
                source_url=detail.url,
                reason=detail.reason,
            )
        )
    return tuple(probes)


def _host_and_pattern(url: str | None) -> tuple[str | None, str | None]:
    parsed = urlparse(str(url or ""))
    path = parsed.path.lower()
    pattern = None
    for marker in ("/job/", "/jobs/", "/stellen/", "/stellenangebote/", "/vacancy/", "/vacancies/"):
        if marker in path:
            pattern = marker.rstrip("/") + "/..."
            break
    return parsed.netloc.lower() or None, pattern


def write_detail_evidence_rows(
    conn: psycopg.Connection[Any],
    *,
    plan: DetailEvidencePlan,
    reviewed_by: str,
) -> int:
    supported = list(plan.evidence.get("supported_details") or [])
    if not supported:
        return 0
    if not db_object_exists(conn, EVIDENCE_TABLE):
        raise SystemExit(f"Missing {EVIDENCE_TABLE}. Apply migrations before running DETAIL-001 with --apply.")

    written = 0
    with conn.cursor(row_factory=dict_row) as cur:
        for detail in supported:
            source_url = str(detail.get("url") or detail.get("final_url") or "").strip()
            if not source_url:
                continue
            final_url = str(detail.get("final_url") or source_url)
            host, path_pattern = _host_and_pattern(final_url)
            evidence_payload = {
                "campaign": plan.evidence.get("campaign"),
                "boundary": BOUNDARY,
                "detail": detail,
                "raw_html_persisted": False,
            }
            cur.execute(
                """
                INSERT INTO employer_origin_job_detail_evidence (
                    candidate_id,
                    company_key,
                    source_url,
                    final_url,
                    evidence_host,
                    path_pattern,
                    status_code,
                    page_title,
                    profile_hits,
                    location_hits,
                    remote_hits,
                    flexibility_hits,
                    relevance_decision,
                    confidence,
                    reason,
                    evidence,
                    discovered_by,
                    reviewed_by
                )
                VALUES (
                    %(candidate_id)s,
                    %(company_key)s,
                    %(source_url)s,
                    %(final_url)s,
                    %(evidence_host)s,
                    %(path_pattern)s,
                    %(status_code)s,
                    %(page_title)s,
                    %(profile_hits)s::jsonb,
                    %(location_hits)s::jsonb,
                    %(remote_hits)s::jsonb,
                    %(flexibility_hits)s::jsonb,
                    'relevant',
                    %(confidence)s,
                    %(reason)s,
                    %(evidence)s::jsonb,
                    'detail001_detail_evidence_discovery',
                    %(reviewed_by)s
                )
                ON CONFLICT (candidate_id, source_url)
                DO UPDATE SET
                    final_url = EXCLUDED.final_url,
                    evidence_host = EXCLUDED.evidence_host,
                    path_pattern = EXCLUDED.path_pattern,
                    status_code = EXCLUDED.status_code,
                    page_title = EXCLUDED.page_title,
                    profile_hits = EXCLUDED.profile_hits,
                    location_hits = EXCLUDED.location_hits,
                    remote_hits = EXCLUDED.remote_hits,
                    flexibility_hits = EXCLUDED.flexibility_hits,
                    relevance_decision = EXCLUDED.relevance_decision,
                    confidence = EXCLUDED.confidence,
                    reason = EXCLUDED.reason,
                    evidence = EXCLUDED.evidence,
                    reviewed_by = EXCLUDED.reviewed_by,
                    updated_at = now()
                """,
                {
                    "candidate_id": plan.candidate_id,
                    "company_key": plan.company_key,
                    "source_url": source_url,
                    "final_url": final_url,
                    "evidence_host": host,
                    "path_pattern": path_pattern,
                    "status_code": detail.get("status_code"),
                    "page_title": detail.get("title"),
                    "profile_hits": json.dumps(detail.get("profile_hits") or []),
                    "location_hits": json.dumps(detail.get("location_hits") or []),
                    "remote_hits": json.dumps(detail.get("remote_hits") or []),
                    "flexibility_hits": json.dumps(detail.get("flexibility_hits") or []),
                    "confidence": plan.evidence.get("confidence_score", 0.0),
                    "reason": detail.get("reason") or plan.evidence.get("confidence_reason") or "DETAIL-001 supported detail evidence",
                    "evidence": json.dumps(evidence_payload, ensure_ascii=False),
                    "reviewed_by": reviewed_by,
                },
            )
            written += 1
    return written


def write_detail_gate_review(
    conn: psycopg.Connection[Any],
    *,
    plan: DetailEvidencePlan,
    reviewed_by: str,
) -> int:
    if not plan.apply_allowed:
        raise SystemExit(f"Apply blocked for {plan.company_key}: {plan.decision}")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, gate_status, decision, stop_reason, evidence
            FROM employer_origin_candidate_gate_reviews
            WHERE candidate_id = %s
              AND gate_name = %s
            """,
            (plan.candidate_id, DETAIL_EVIDENCE_GATE),
        )
        previous = cur.fetchone()
        previous_state = dict(previous) if previous else None

        cur.execute(
            """
            INSERT INTO employer_origin_candidate_gate_reviews (
                candidate_id,
                gate_order,
                gate_name,
                gate_status,
                decision,
                stop_reason,
                evidence,
                reviewed_by,
                reviewed_at
            )
            VALUES (%s, 8, %s, %s, %s, %s, %s::jsonb, %s, now())
            ON CONFLICT (candidate_id, gate_name)
            DO UPDATE SET
                gate_order = EXCLUDED.gate_order,
                gate_status = EXCLUDED.gate_status,
                decision = EXCLUDED.decision,
                stop_reason = EXCLUDED.stop_reason,
                evidence = EXCLUDED.evidence,
                reviewed_by = EXCLUDED.reviewed_by,
                reviewed_at = now(),
                updated_at = now()
            RETURNING id
            """,
            (
                plan.candidate_id,
                DETAIL_EVIDENCE_GATE,
                plan.gate_status,
                plan.decision,
                plan.stop_reason,
                json.dumps(plan.evidence, ensure_ascii=False),
                reviewed_by,
            ),
        )
        gate_review_id = int(cur.fetchone()["id"])
        cur.execute(
            """
            INSERT INTO employer_origin_candidate_gate_events (
                candidate_id,
                gate_review_id,
                event_type,
                previous_state,
                new_state,
                event_reason,
                created_by
            )
            VALUES (%s, %s, 'gate_updated', %s::jsonb, %s::jsonb, %s, %s)
            """,
            (
                plan.candidate_id,
                gate_review_id,
                json.dumps(previous_state, default=str, ensure_ascii=False) if previous_state else None,
                json.dumps(
                    {
                        "gate_name": DETAIL_EVIDENCE_GATE,
                        "gate_status": plan.gate_status,
                        "decision": plan.decision,
                        "stop_reason": plan.stop_reason,
                        "evidence": plan.evidence,
                    },
                    ensure_ascii=False,
                ),
                "DETAIL-001 detail evidence discovery gate transition",
                reviewed_by,
            ),
        )
    return gate_review_id


def apply_plan(conn: psycopg.Connection[Any], *, plan: DetailEvidencePlan, reviewed_by: str) -> DetailEvidencePlan:
    written = write_detail_evidence_rows(conn, plan=plan, reviewed_by=reviewed_by)
    gate_review_id = write_detail_gate_review(conn, plan=plan, reviewed_by=reviewed_by)
    return DetailEvidencePlan(
        **{
            **plan.__dict__,
            "applied": True,
            "gate_review_id": gate_review_id,
            "written_detail_evidence_count": written,
        }
    )


def build_plan_for_candidate(
    conn: psycopg.Connection[Any],
    *,
    args: argparse.Namespace,
    company_key: str,
) -> DetailEvidencePlan:
    candidate = load_candidate(conn, company_key)
    gates = load_gates(conn, candidate.id)
    probes: tuple[DetailProbeEvidence, ...] = ()
    requested_urls: Sequence[str] = ()
    rejected_urls: Sequence[str] = ()
    discovery_evidence: dict[str, Any] = {}
    detail_candidate_count = 0

    if normalize_url(candidate.candidate_url) and early_gates_ready(gates) and not args.no_probe:
        profile_terms, location_terms = build_terms(args)
        outcome = build_repair_outcome(
            candidate=candidate,
            gates=load_gate_mapping(conn, candidate.id),
            profile_terms=profile_terms,
            location_terms=location_terms,
            max_seed_pages=args.max_seed_pages,
            max_detail_pages=args.max_detail_pages,
            enable_search_discovery=not args.disable_search_discovery,
            max_search_queries=args.max_search_queries,
            max_search_results=args.max_search_results,
            search_provider=args.search_provider,
        )
        probes = probes_from_repair_outcome(outcome)
        requested_urls = tuple(outcome.requested_urls)
        rejected_urls = tuple(outcome.rejected_urls)
        raw_discovery = outcome.evidence.get("discovery_evidence") or {}
        discovery_evidence = {
            "repair_agent_evidence": {
                key: value
                for key, value in outcome.evidence.items()
                if key
                not in {
                    "details",
                    "supported_details",
                    "requested_urls",
                    "rejected_urls",
                }
            },
            "raw_discovery": raw_discovery,
        }
        detail_candidate_count = len(outcome.evidence.get("candidate_links") or [])

    return build_detail_evidence_plan(
        candidate_snapshot(candidate),
        gates,
        probes,
        reviewed_by=args.reviewed_by,
        requested_urls=requested_urls,
        rejected_urls=rejected_urls,
        discovery_evidence=discovery_evidence,
        detail_candidate_count=detail_candidate_count,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    load_local_env_file()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    plans: list[DetailEvidencePlan] = []

    with connect() as conn:
        for company_key in args.company_key:
            plan = build_plan_for_candidate(conn, args=args, company_key=company_key)
            if args.apply and plan.apply_allowed:
                plan = apply_plan(conn, plan=plan, reviewed_by=args.reviewed_by)
                print(
                    "detail_evidence_applied: "
                    f"company_key={company_key} gate_status={plan.gate_status} "
                    f"gate_review_id={plan.gate_review_id} evidence_rows={plan.written_detail_evidence_count}"
                )
            else:
                print(
                    "detail_evidence_plan: "
                    f"company_key={company_key} gate_status={plan.gate_status} "
                    f"decision={plan.decision} apply_allowed={plan.apply_allowed} "
                    f"next={plan.recommended_next_safe_action}"
                )
            plans.append(plan)
        if args.apply:
            conn.commit()
        else:
            conn.rollback()

    payload = report_payload(benchmark_label=args.benchmark_label, plans=plans)
    json_path = args.output_json or output_dir / f"{args.benchmark_label}.json"
    md_path = args.output_markdown or output_dir / f"{args.benchmark_label}.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print("json_report_written:", json_path)
    print("markdown_report_written:", md_path)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DETAIL-001 bounded detail evidence discovery for persisted origin URLs.")
    parser.add_argument("--benchmark-label", required=True)
    parser.add_argument("--company-key", action="append", required=True)
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--profile-term", action="append")
    parser.add_argument("--location-term", action="append")
    parser.add_argument("--max-seed-pages", type=int, default=12)
    parser.add_argument("--max-detail-pages", type=int, default=8)
    parser.add_argument("--max-search-queries", type=int, default=DEFAULT_SEARCH_QUERY_LIMIT)
    parser.add_argument("--max-search-results", type=int, default=DEFAULT_SEARCH_RESULT_LIMIT)
    parser.add_argument("--search-provider", choices=SUPPORTED_SEARCH_PROVIDERS, default=DEFAULT_SEARCH_PROVIDER)
    parser.add_argument("--disable-search-discovery", action="store_true")
    parser.add_argument("--no-probe", action="store_true", help="Create a plan without HTTP probing. Apply is blocked.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.apply and args.no_probe:
        raise SystemExit("DETAIL-001 --apply requires bounded probing; remove --no-probe.")
    run(args)


if __name__ == "__main__":
    main()
