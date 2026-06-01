from __future__ import annotations

import argparse
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import psycopg

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig
from scripts.search_intelligence_control_center import (
    BUILD_APPROVAL_TOKEN,
    REGISTRATION_APPROVAL_TOKEN,
    ControlCenterCandidate,
    build_approval_command,
    registration_approval_command,
    render_control_center,
)


class ControlCenterState:
    def __init__(self, *, reviewed_by: str, target_location: str, allow_write_actions: bool) -> None:
        self.reviewed_by = reviewed_by
        self.target_location = target_location
        self.allow_write_actions = allow_write_actions
        self.flash_message: str | None = None


def _rows_to_candidates(rows: list[tuple[object, ...]]) -> list[ControlCenterCandidate]:
    return [
        ControlCenterCandidate(
            candidate_id=int(row[0]),
            company_key=str(row[1]),
            company_name=str(row[2]),
            candidate_url=row[3],
            source_name_candidate=str(row[4]),
            source_type_candidate=str(row[5]),
            status=str(row[6]),
            operational_risk_level=str(row[7]),
            false_negative_risk_level=row[8],
            reassessment_status=row[9],
            reassessment_reason=row[10],
            generation_status=row[11],
            generation_recommendation=row[12],
            build_status=row[13],
            build_recommendation=row[14],
            build_mode=row[15],
            build_next_command=row[16],
            connector_module_path=row[17],
            connector_test_path=row[18],
            connector_docs_path=row[19],
            gate_passed_count=int(row[20] or 0),
            gate_manual_review_count=int(row[21] or 0),
            gate_blocked_count=int(row[22] or 0),
            gate_total_count=int(row[23] or 0),
            latest_blocking_gate=row[24],
            latest_blocking_reason=row[25],
            connector_validation_status=row[26],
            connector_validation_decision=row[27],
            final_approval_status=row[28],
            final_approval_decision=row[29],
        )
        for row in rows
    ]


def load_control_center_candidates() -> list[ControlCenterCandidate]:
    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                with gate_counts as (
                    select
                        candidate_id,
                        count(*) filter (where gate_status = 'passed') as passed_count,
                        count(*) filter (where gate_status = 'manual_review_required') as manual_review_count,
                        count(*) filter (where gate_status = 'blocked') as blocked_count,
                        count(*) as total_count
                    from employer_origin_candidate_gate_reviews
                    group by candidate_id
                ),
                latest_blocker as (
                    select distinct on (candidate_id)
                        candidate_id,
                        gate_name,
                        stop_reason
                    from employer_origin_candidate_gate_reviews
                    where gate_status in ('manual_review_required', 'blocked')
                    order by candidate_id, gate_order asc, reviewed_at desc nulls last
                ),
                connector_validation as (
                    select distinct on (candidate_id)
                        candidate_id,
                        gate_status,
                        decision
                    from employer_origin_candidate_gate_reviews
                    where gate_name = 'connector_validation_gate'
                    order by candidate_id, reviewed_at desc nulls last
                ),
                final_approval as (
                    select distinct on (candidate_id)
                        candidate_id,
                        gate_status,
                        decision
                    from employer_origin_candidate_gate_reviews
                    where gate_name = 'final_approval_gate'
                    order by candidate_id, reviewed_at desc nulls last
                ),
                reassessment as (
                    select distinct on (candidate_id)
                        candidate_id,
                        risk_level,
                        status,
                        trigger_reason
                    from candidate_reassessment_queue
                    order by candidate_id, updated_at desc
                ),
                generation_plan as (
                    select distinct on (candidate_id)
                        candidate_id,
                        generation_status,
                        recommendation
                    from employer_origin_connector_generation_plans
                    order by candidate_id, updated_at desc
                ),
                build_request as (
                    select distinct on (candidate_id)
                        candidate_id,
                        build_status,
                        recommendation,
                        build_mode,
                        next_command,
                        connector_module_path,
                        connector_test_path,
                        connector_docs_path
                    from employer_origin_connector_build_requests
                    order by candidate_id, updated_at desc
                )
                select
                    c.id,
                    c.company_key,
                    c.company_name,
                    c.candidate_url,
                    c.source_name_candidate,
                    c.source_type_candidate,
                    c.status,
                    c.risk_level,
                    reassessment.risk_level as false_negative_risk_level,
                    reassessment.status as reassessment_status,
                    reassessment.trigger_reason as reassessment_reason,
                    generation_plan.generation_status,
                    generation_plan.recommendation,
                    build_request.build_status,
                    build_request.recommendation as build_recommendation,
                    build_request.build_mode,
                    build_request.next_command,
                    build_request.connector_module_path,
                    build_request.connector_test_path,
                    build_request.connector_docs_path,
                    coalesce(gate_counts.passed_count, 0),
                    coalesce(gate_counts.manual_review_count, 0),
                    coalesce(gate_counts.blocked_count, 0),
                    coalesce(gate_counts.total_count, 0),
                    latest_blocker.gate_name,
                    latest_blocker.stop_reason,
                    connector_validation.gate_status,
                    connector_validation.decision,
                    final_approval.gate_status,
                    final_approval.decision
                from employer_origin_source_candidates c
                left join gate_counts on gate_counts.candidate_id = c.id
                left join latest_blocker on latest_blocker.candidate_id = c.id
                left join connector_validation on connector_validation.candidate_id = c.id
                left join final_approval on final_approval.candidate_id = c.id
                left join reassessment on reassessment.candidate_id = c.id and reassessment.status = 'open'
                left join generation_plan on generation_plan.candidate_id = c.id
                left join build_request on build_request.candidate_id = c.id
                order by
                    case when build_request.build_status = 'build_approval_required' then 0 else 1 end,
                    case when reassessment.risk_level = 'critical' then 0 when reassessment.risk_level = 'high' then 1 else 2 end,
                    c.status,
                    c.company_name
                """
            )
            rows = cur.fetchall()
    return _rows_to_candidates(rows)


def run_command(command: tuple[str, ...]) -> str:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    output = (completed.stdout or completed.stderr or "").strip().splitlines()
    summary = output[0] if output else "No output."
    return f"exit={completed.returncode}; {summary}"


class ControlCenterHandler(BaseHTTPRequestHandler):
    server_version = "SearchIntelligenceControlCenter/0.1"

    @property
    def state(self) -> ControlCenterState:
        return self.server.control_center_state  # type: ignore[attr-defined]

    def send_html(self, body: str, *, status: int = 200) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if parsed.path not in {"/", "/index.html"}:
            self.send_error(404)
            return
        query = parse_qs(parsed.query)
        active_tab = query.get("tab", ["dashboard"])[0]
        try:
            candidates = load_control_center_candidates()
            body = render_control_center(
                candidates,
                reviewed_by=self.state.reviewed_by,
                target_location=self.state.target_location,
                write_actions_enabled=self.state.allow_write_actions,
                flash_message=self.state.flash_message,
                active_tab=active_tab,
            )
        except Exception as exc:  # pragma: no cover - browser diagnostics
            body = f"<html><body><h1>Control Center failed</h1><pre>{exc}</pre></body></html>"
        self.state.flash_message = None
        self.send_html(body)

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        if self.path == "/actions/shutdown":
            self.send_html("<html><body><h1>Control Center stopped</h1><p>You can close this tab.</p></body></html>")
            threading.Thread(target=self.server.shutdown, daemon=True).start()  # type: ignore[attr-defined]
            return
        if self.path not in {"/actions/approve-build", "/actions/approve-registration"}:
            self.send_error(404)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")
        fields = {key: values[0] for key, values in parse_qs(body).items() if values}
        company_key = fields.get("company_key", "")
        approval_token = fields.get("approval_token", "")
        reviewed_by = fields.get("reviewed_by") or self.state.reviewed_by

        if not self.state.allow_write_actions:
            self.state.flash_message = "Action blocked: restart with --allow-write-actions."
        elif self.path == "/actions/approve-build":
            if approval_token != BUILD_APPROVAL_TOKEN:
                self.state.flash_message = f"Action blocked: exact token {BUILD_APPROVAL_TOKEN!r} required."
            else:
                self.state.flash_message = run_command(build_approval_command(company_key, reviewed_by))
        elif self.path == "/actions/approve-registration":
            if approval_token != REGISTRATION_APPROVAL_TOKEN:
                self.state.flash_message = f"Action blocked: exact token {REGISTRATION_APPROVAL_TOKEN!r} required."
            else:
                self.state.flash_message = run_command(
                    registration_approval_command(company_key, self.state.target_location, reviewed_by)
                )

        self.send_response(303)
        self.send_header("Location", "/?tab=approvals")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the Search Intelligence Control Center UI.")
    parser.add_argument("--host", default=os.environ.get("SEARCH_INTELLIGENCE_UI_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SEARCH_INTELLIGENCE_UI_PORT", "8770")))
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--reviewed-by", default="jens")
    parser.add_argument("--allow-write-actions", action="store_true")
    return parser


def run_server(args: argparse.Namespace) -> None:
    state = ControlCenterState(
        reviewed_by=args.reviewed_by,
        target_location=args.target_location,
        allow_write_actions=args.allow_write_actions,
    )
    server = ThreadingHTTPServer((args.host, args.port), ControlCenterHandler)
    server.control_center_state = state  # type: ignore[attr-defined]
    mode = "write-enabled" if args.allow_write_actions else "read-only"
    print(f"Search Intelligence Control Center running at http://{args.host}:{args.port}/ ({mode})")
    print("Boundary: no auto-PR, no source activation, no Bronze writes, no scheduler changes.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSearch Intelligence Control Center stopped by user.")
    finally:
        server.server_close()


def main() -> None:
    run_server(build_parser().parse_args())


if __name__ == "__main__":
    main()
