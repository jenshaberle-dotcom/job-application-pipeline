from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Sequence

import psycopg
import requests

from src.config import get_database_config
from src.search_intelligence.gate001_initial_gate_review import (
    CandidateInitialGatePlan,
    CandidateSnapshot,
    ProbeResult,
    build_initial_gate_plan,
    report_payload,
    render_markdown,
    security_precheck_url,
)

DEFAULT_OUTPUT_DIR = Path("exports/gate001_initial_gate_review")
CAREER_MARKERS = ("career", "careers", "karriere", "job", "jobs", "stellen", "stellenangebote")
RISK_MARKERS = ("captcha", "recaptcha", "hcaptcha", "cloudflare", "access denied", "forbidden")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GATE-001 dry-run/apply initial gate review for persisted origin URLs.")
    parser.add_argument("--benchmark-label", required=True)
    parser.add_argument("--company-key", action="append", default=[], help="Company key to review. Repeat for multiple candidates.")
    parser.add_argument("--reviewed-by", default="system")
    parser.add_argument("--timeout-seconds", type=float, default=3.0)
    parser.add_argument("--max-response-bytes", type=int, default=250_000)
    parser.add_argument("--no-probe", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args()


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def find_title(text: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return clean_text(match.group(1))[:250]


def detect_career_like(url: str, title: str | None, body_sample: str) -> bool:
    haystack = " ".join([url, title or "", body_sample[:5000]]).lower()
    return any(marker in haystack for marker in CAREER_MARKERS)


def detect_risk_markers(title: str | None, body_sample: str, reason: str) -> tuple[str, ...]:
    haystack = " ".join([title or "", body_sample[:5000], reason]).lower()
    return tuple(sorted(marker for marker in RISK_MARKERS if marker in haystack))


def http_probe(url: str, *, timeout_seconds: float, max_response_bytes: int) -> ProbeResult:
    allowed, security_reason = security_precheck_url(url)
    if not allowed:
        return ProbeResult(
            url=url,
            final_url=None,
            reachable=False,
            career_like=False,
            status_code=None,
            title=None,
            response_bytes=0,
            reason=security_reason or "blocked by security precheck",
            risk_markers=(),
            blocked_by_security=True,
        )
    try:
        response = requests.get(
            url,
            timeout=timeout_seconds,
            allow_redirects=True,
            headers={"User-Agent": "job-application-pipeline-gate001/0.1"},
            stream=True,
        )
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            chunks.append(chunk)
            total += len(chunk)
            if total >= max_response_bytes:
                break
        body = b"".join(chunks).decode(response.encoding or "utf-8", errors="ignore")
        title = find_title(body)
        final_url = response.url
        reachable = response.status_code < 500
        career_like = reachable and detect_career_like(final_url, title, body)
        risk_markers = detect_risk_markers(title, body, "")
        return ProbeResult(
            url=url,
            final_url=final_url,
            reachable=reachable,
            career_like=career_like,
            status_code=response.status_code,
            title=title,
            response_bytes=total,
            reason="reachable career/job-like URL" if career_like else "URL reachable but not clearly career/job-like",
            risk_markers=risk_markers,
        )
    except requests.RequestException as exc:
        return ProbeResult(
            url=url,
            final_url=None,
            reachable=False,
            career_like=False,
            status_code=None,
            title=None,
            response_bytes=0,
            reason=f"request failed: {type(exc).__name__}",
            risk_markers=(),
        )


def load_candidates(conn: psycopg.Connection, company_keys: Sequence[str]) -> list[CandidateSnapshot]:
    if not company_keys:
        raise SystemExit("At least one --company-key is required for GATE-001.")
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """
            SELECT id, company_key, company_name, status, candidate_url
            FROM employer_origin_source_candidates
            WHERE company_key = ANY(%s)
            ORDER BY company_key
            """,
            (list(company_keys),),
        )
        rows = cur.fetchall()
    found = {str(row["company_key"]) for row in rows}
    missing = [key for key in company_keys if key not in found]
    if missing:
        raise SystemExit("Missing employer-origin candidate(s): " + ", ".join(missing))
    return [
        CandidateSnapshot(
            candidate_id=int(row["id"]),
            company_key=str(row["company_key"]),
            company_name=str(row["company_name"] or row["company_key"]),
            status=str(row["status"]),
            candidate_url=row["candidate_url"],
        )
        for row in rows
    ]


def apply_gate_reviews(conn: psycopg.Connection, *, plan: CandidateInitialGatePlan, reviewed_by: str) -> CandidateInitialGatePlan:
    with conn.cursor() as cur:
        for evaluation in plan.evaluations:
            if not evaluation.apply_allowed:
                continue
            cur.execute(
                """
                INSERT INTO employer_origin_candidate_gate_reviews (
                    candidate_id,
                    gate_name,
                    gate_order,
                    gate_status,
                    decision,
                    stop_reason,
                    evidence,
                    reviewed_at,
                    reviewed_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, now(), %s)
                ON CONFLICT (candidate_id, gate_name)
                DO UPDATE SET
                    gate_order = EXCLUDED.gate_order,
                    gate_status = EXCLUDED.gate_status,
                    decision = EXCLUDED.decision,
                    stop_reason = EXCLUDED.stop_reason,
                    evidence = EXCLUDED.evidence,
                    reviewed_at = EXCLUDED.reviewed_at,
                    reviewed_by = EXCLUDED.reviewed_by,
                    updated_at = now()
                """,
                (
                    evaluation.candidate_id,
                    evaluation.gate_name,
                    evaluation.gate_order,
                    evaluation.gate_status,
                    evaluation.decision,
                    evaluation.stop_reason,
                    json.dumps(evaluation.evidence, ensure_ascii=False),
                    reviewed_by,
                ),
            )
    return CandidateInitialGatePlan(
        candidate_id=plan.candidate_id,
        company_key=plan.company_key,
        company_name=plan.company_name,
        candidate_url=plan.candidate_url,
        evaluations=plan.evaluations,
        recommended_next_safe_action=plan.recommended_next_safe_action,
        recommendation_reason=plan.recommendation_reason,
        applied=True,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    with psycopg.connect(**get_database_config()) as conn:
        candidates = load_candidates(conn, args.company_key)
        plans: list[CandidateInitialGatePlan] = []
        for candidate in candidates:
            probe = None if args.no_probe or not candidate.candidate_url else http_probe(
                candidate.candidate_url,
                timeout_seconds=args.timeout_seconds,
                max_response_bytes=args.max_response_bytes,
            )
            plan = build_initial_gate_plan(candidate, probe=probe, reviewed_by=args.reviewed_by)
            if args.apply:
                plan = apply_gate_reviews(conn, plan=plan, reviewed_by=args.reviewed_by)
            plans.append(plan)
        if args.apply:
            conn.commit()
    payload = report_payload(benchmark_label=args.benchmark_label, plans=plans)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{args.benchmark_label}.json"
    md_path = output_dir / f"{args.benchmark_label}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print("summary:", json.dumps(payload["summary"], sort_keys=True))
    for plan in payload["plans"]:
        print(
            "initial_gate_plan:",
            f"company_key={plan['company_key']}",
            f"next={plan['recommended_next_safe_action']}",
            f"applied={plan['applied']}",
        )
    print("json_report_written:", json_path)
    print("markdown_report_written:", md_path)
    return payload


def main() -> None:
    args = parse_args()
    run(args)


if __name__ == "__main__":
    main()
