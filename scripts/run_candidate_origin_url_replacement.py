"""Run exact, live-revalidated candidate origin URL replacement plans."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Sequence

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.candidate_origin_url_replacement import (
    CandidateOriginSnapshot,
    ReplacementPlanItem,
    ReplacementRequest,
    build_replacement_plan_item,
    classify_apply_set,
    mark_applied,
    parse_repair_spec,
    same_url,
    summarize_replacement_plans,
    validate_apply_authority,
    validate_unique_requests,
)
from src.search_intelligence.connector_feasibility import (
    OriginCandidate,
    bounded_fetch,
)
from src.search_intelligence.connector_feasibility_runtime import (
    evaluate_connector_feasibility_runtime,
)

BOUNDARY = {
    "candidate_url_replacement": True,
    "dry_run_default": True,
    "exact_target_binding": True,
    "expected_previous_url_binding": True,
    "live_s7n_revalidation": True,
    "explicit_apply_required": True,
    "atomic_audit_and_compare_set": True,
    "no_provider_requests": True,
    "no_llm_requests": True,
    "no_feasibility_review_write": True,
    "no_connector_build": True,
    "no_connector_registration": True,
    "no_source_activation": True,
    "no_bronze_silver_gold_job_write": True,
    "no_scheduler_or_wave_change": True,
    "no_ranking_top5_candidate_fact_or_application_write": True,
}
DEFAULT_OUTPUT_ROOT = Path.home() / "product_v1_runtime_artifacts"


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def load_candidate(
    conn: psycopg.Connection[Any],
    request: ReplacementRequest,
    *,
    for_update: bool,
) -> CandidateOriginSnapshot:
    lock_sql = " FOR UPDATE" if for_update else ""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT
                id,
                company_key,
                company_name,
                status,
                candidate_url,
                source_name_candidate,
                risk_level
            FROM employer_origin_source_candidates
            WHERE id = %s
            {lock_sql}
            """,
            (request.candidate_id,),
        )
        row = cur.fetchone()
    if not row:
        raise SystemExit(f"Candidate not found for exact target {request.target}.")
    return CandidateOriginSnapshot(
        candidate_id=int(row["id"]),
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        status=str(row["status"]),
        candidate_url=row["candidate_url"],
        source_name_candidate=row["source_name_candidate"],
        risk_level=row["risk_level"],
    )


def duplicate_selected_url_exists(
    conn: psycopg.Connection[Any],
    *,
    candidate: CandidateOriginSnapshot,
    proposed_url: str,
) -> bool:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, candidate_url
            FROM employer_origin_source_candidates
            WHERE company_key = %s
              AND id <> %s
              AND candidate_url IS NOT NULL
            ORDER BY id
            """,
            (candidate.company_key, candidate.candidate_id),
        )
        rows = cur.fetchall()
    return any(same_url(row["candidate_url"], proposed_url) for row in rows)


def live_plan(
    conn: psycopg.Connection[Any],
    *,
    request: ReplacementRequest,
    candidate: CandidateOriginSnapshot,
    timeout_seconds: float,
    max_response_bytes: int,
) -> tuple[ReplacementPlanItem, dict[str, object]]:
    origin = OriginCandidate(
        candidate_id=candidate.candidate_id,
        company_key=candidate.company_key,
        company_name=candidate.company_name,
        origin_url=candidate.candidate_url,
        source_name_candidate=candidate.source_name_candidate,
        status=candidate.status,
        risk_level=candidate.risk_level,
    )
    if candidate.candidate_url:
        fetch_result = bounded_fetch(
            candidate.candidate_url,
            timeout_seconds=timeout_seconds,
            max_bytes=max_response_bytes,
        )
        item = evaluate_connector_feasibility_runtime(
            origin,
            fetch_enabled=True,
            fetch_result=fetch_result,
        )
    else:
        item = evaluate_connector_feasibility_runtime(
            origin,
            fetch_enabled=False,
        )

    duplicate_exists = duplicate_selected_url_exists(
        conn,
        candidate=candidate,
        proposed_url=request.proposed_url,
    )
    plan = build_replacement_plan_item(
        request,
        candidate,
        item,
        duplicate_selected_url_exists=duplicate_exists,
    )
    evidence = {
        "http_status": item.http_status,
        "reachable": item.reachable,
        "page_type": item.page_type,
        "feasibility_status": item.feasibility_status,
        "decision": item.decision,
        "blocker_code": item.blocker_code,
        "reason": item.reason,
        "recommended_next_action": item.recommended_next_action,
        "url_quality": asdict(item.url_quality),
        "structural_job_evidence_count": item.structural_job_evidence_count,
        "job_search_page_evidence_count": item.job_search_page_evidence_count,
        "job_detail_candidate_evidence_count": (
            item.job_detail_candidate_evidence_count
        ),
        "career_context_evidence_count": item.career_context_evidence_count,
        "rejected_noise_count": item.rejected_noise_count,
        "sample_job_urls": list(item.sample_job_urls),
        "evidence_classification": item.evidence_classification.as_dict(),
        "runtime_evidence": item.evidence,
    }
    return plan, evidence


def apply_replacement(
    conn: psycopg.Connection[Any],
    *,
    request: ReplacementRequest,
    candidate: CandidateOriginSnapshot,
    plan: ReplacementPlanItem,
    evidence: dict[str, object],
    reviewed_by: str,
) -> int:
    if not plan.apply_allowed:
        raise SystemExit(f"Apply blocked for {request.target}: {plan.decision}")

    boundary = dict(BOUNDARY)
    audit_evidence = {
        "exact_target": request.target,
        "expected_previous_url": request.expected_previous_url,
        "proposed_url": request.proposed_url,
        "current_candidate_url": candidate.candidate_url,
        "live_s7n": evidence,
    }
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO candidate_origin_url_persistence_reviews (
                candidate_id,
                company_key,
                company_name,
                previous_candidate_url,
                selected_candidate_url,
                selected_url_source,
                decision,
                review_status,
                reason,
                boundary,
                evidence,
                reviewed_by,
                applied_at
            )
            VALUES (
                %(candidate_id)s,
                %(company_key)s,
                %(company_name)s,
                %(previous_candidate_url)s,
                %(selected_candidate_url)s,
                'live_s7n_repair_candidate',
                'replace_validated_candidate_url',
                'applied',
                %(reason)s,
                %(boundary)s::jsonb,
                %(evidence)s::jsonb,
                %(reviewed_by)s,
                now()
            )
            RETURNING id
            """,
            {
                "candidate_id": candidate.candidate_id,
                "company_key": candidate.company_key,
                "company_name": candidate.company_name,
                "previous_candidate_url": candidate.candidate_url,
                "selected_candidate_url": request.proposed_url,
                "reason": plan.reason,
                "boundary": json.dumps(boundary, sort_keys=True),
                "evidence": json.dumps(audit_evidence, sort_keys=True),
                "reviewed_by": reviewed_by,
            },
        )
        review_id = int(cur.fetchone()["id"])
        cur.execute(
            """
            UPDATE employer_origin_source_candidates
            SET candidate_url = %s,
                updated_at = now()
            WHERE id = %s
              AND company_key = %s
              AND candidate_url = %s
              AND status <> 'active_controlled'
            """,
            (
                request.proposed_url,
                request.candidate_id,
                request.company_key,
                candidate.candidate_url,
            ),
        )
        if cur.rowcount != 1:
            raise SystemExit(
                "Candidate URL replacement did not update exactly one exact "
                f"compare-and-set row for {request.target}; transaction will abort."
            )
    return review_id


def default_output_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return DEFAULT_OUTPUT_ROOT / f"candidate_origin_url_replacement_{timestamp}"


def markdown_report(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    assert isinstance(summary, dict)
    lines = [
        "# Candidate Origin URL Replacement",
        "",
        f"- Mode: `{payload['mode']}`",
        f"- Apply set state: `{payload['apply_set_state']}`",
        f"- Provider requests: `{payload['provider_requests']}`",
        f"- LLM requests: `{payload['llm_requests']}`",
        f"- Candidates: `{summary['candidate_count']}`",
        f"- Ready: `{summary['ready_count']}`",
        f"- Applied: `{summary['applied_count']}`",
        f"- Idempotent: `{summary['idempotent_count']}`",
        f"- Valid stops: `{summary['valid_stop_count']}`",
        "",
        "## Items",
        "",
        "| Target | Current URL | Proposed URL | Decision | Status | Apply allowed |",
        "|---|---|---|---|---|---|",
    ]
    items = payload["items"]
    assert isinstance(items, list)
    for item in items:
        assert isinstance(item, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item["target"]),
                    str(item.get("current_url") or "<none>"),
                    str(item["proposed_url"]),
                    str(item["decision"]),
                    str(item["status"]),
                    "yes" if item["apply_allowed"] else "no",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or apply exact candidate origin URL replacements after fresh "
            "bounded S7N confirmation."
        )
    )
    parser.add_argument(
        "--repair",
        action="append",
        required=True,
        help=(
            "Exact target|expected_previous_url|proposed_url specification. "
            "Quote the complete value."
        ),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--approved-target", action="append", default=[])
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--max-response-bytes", type=int, default=250_000)
    parser.add_argument("--output-dir", type=Path)
    return parser


def run(args: argparse.Namespace) -> dict[str, object]:
    try:
        requests = validate_unique_requests(
            [parse_repair_spec(value) for value in args.repair]
        )
        if args.apply:
            validate_apply_authority(
                requests,
                approval_token=args.approval_token,
                approved_targets=args.approved_target,
            )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be positive")
    if args.max_response_bytes <= 0:
        raise SystemExit("--max-response-bytes must be positive")

    plans: list[ReplacementPlanItem] = []
    evidence_by_target: dict[str, dict[str, object]] = {}

    with connect() as conn:
        for request in requests:
            candidate = load_candidate(
                conn,
                request,
                for_update=args.apply,
            )
            plan, evidence = live_plan(
                conn,
                request=request,
                candidate=candidate,
                timeout_seconds=args.timeout_seconds,
                max_response_bytes=args.max_response_bytes,
            )
            plans.append(plan)
            evidence_by_target[request.target] = evidence

        apply_set_state = classify_apply_set(plans)
        if args.apply:
            if apply_set_state == "idempotent_replay":
                conn.rollback()
            elif apply_set_state != "apply_ready":
                conn.rollback()
                blockers = ", ".join(
                    f"{item.target}:{item.decision}" for item in plans
                )
                raise SystemExit(
                    "Apply requires every target to be replacement-ready; "
                    f"blocked={blockers}"
                )
            else:
                applied: list[ReplacementPlanItem] = []
                for request, candidate_plan in zip(requests, plans, strict=True):
                    candidate = load_candidate(
                        conn,
                        request,
                        for_update=True,
                    )
                    if not same_url(
                        candidate.candidate_url,
                        candidate_plan.current_url,
                    ):
                        raise SystemExit(
                            f"Candidate URL drift detected before apply for {request.target}."
                        )
                    review_id = apply_replacement(
                        conn,
                        request=request,
                        candidate=candidate,
                        plan=candidate_plan,
                        evidence=evidence_by_target[request.target],
                        reviewed_by=args.reviewed_by,
                    )
                    applied.append(
                        mark_applied(
                            candidate_plan,
                            audit_review_id=review_id,
                        )
                    )
                plans = applied
                conn.commit()
        else:
            conn.rollback()

    summary = summarize_replacement_plans(plans)
    status_counts = Counter(item.status for item in plans)
    payload: dict[str, object] = {
        "mode": "apply" if args.apply else "dry_run",
        "apply_set_state": classify_apply_set(plans),
        "provider_requests": 0,
        "llm_requests": 0,
        "boundary": dict(BOUNDARY),
        "summary": asdict(summary),
        "status_counts": dict(sorted(status_counts.items())),
        "items": [
            {
                **item.as_dict(),
                "live_s7n_evidence": evidence_by_target[item.target],
            }
            for item in plans
        ],
    }

    output_dir = args.output_dir or default_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "result.json"
    markdown_path = output_dir / "result.md"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(markdown_report(payload), encoding="utf-8")

    print("Candidate Origin URL Replacement")
    print(f"mode: {payload['mode']}")
    print(f"apply_set_state: {payload['apply_set_state']}")
    print(f"provider_requests: {payload['provider_requests']}")
    print(f"llm_requests: {payload['llm_requests']}")
    print(f"json_report: {json_path}")
    print(f"markdown_report: {markdown_path}")
    print("---")
    for item in plans:
        print(
            f"- {item.target} | decision={item.decision} | status={item.status} "
            f"| apply_allowed={item.apply_allowed} | http={item.http_status or '-'}"
        )
        print(f"  current_url: {item.current_url or '-'}")
        print(f"  proposed_url: {item.proposed_url}")
        print(f"  live_repair_candidate: {item.live_repair_candidate_url or '-'}")
        print(f"  reason: {item.reason}")
        if item.audit_review_id:
            print(f"  audit_review_id: {item.audit_review_id}")
    if not args.apply:
        print("NEXT: exact operator review; rerun with apply authority only if approved.")
    elif payload["apply_set_state"] == "idempotent_replay":
        print("RESULT: idempotent replay; no database mutation.")
    else:
        print("RESULT: exact candidate origin URL replacements applied atomically.")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
