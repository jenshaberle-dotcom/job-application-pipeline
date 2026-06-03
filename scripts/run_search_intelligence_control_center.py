from __future__ import annotations

import argparse
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig
from scripts.search_intelligence_control_center import (
    BUILD_APPROVAL_TOKEN,
    EVIDENCE_REPAIR_TOKEN,
    REGISTRATION_APPROVAL_TOKEN,
    AgentGateReview,
    ControlCenterCandidate,
    GoldMarketCoverageSummary,
    OrchestratorAttentionStep,
    build_approval_command,
    evidence_repair_command,
    registration_approval_command,
    render_control_center,
)


class ControlCenterState:
    def __init__(self, *, reviewed_by: str, target_location: str, allow_write_actions: bool) -> None:
        self.reviewed_by = reviewed_by
        self.target_location = target_location
        self.allow_write_actions = allow_write_actions
        self.flash_message: str | None = None


def _value(row: object, key: str, default: object = None) -> object:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _rows_to_candidates(rows: list[object]) -> list[ControlCenterCandidate]:
    return [
        ControlCenterCandidate(
            candidate_id=int(_value(row, "candidate_id", 0) or 0),
            company_key=str(_value(row, "company_key", "")),
            company_name=str(_value(row, "display_company_name", "")),
            candidate_url=_value(row, "candidate_url"),
            source_name_candidate=str(_value(row, "source_name_candidate", "")),
            source_type_candidate=str(_value(row, "source_type_candidate", "")),
            status=str(_value(row, "candidate_status", "")),
            operational_risk_level=str(_value(row, "candidate_risk_level", "")),
            false_negative_risk_level=_value(row, "fn_pressure_level"),
            reassessment_status=_value(row, "current_stage")
            if _value(row, "current_stage") == "gate_reassessment_required"
            else None,
            reassessment_reason=_value(row, "fn_pressure_reason"),
            generation_status=_value(row, "generation_status"),
            generation_recommendation=_value(row, "generation_recommendation"),
            build_status=_value(row, "build_status"),
            build_recommendation=_value(row, "build_recommendation"),
            build_mode=_value(row, "build_mode"),
            build_next_command=_value(row, "debug_next_command"),
            connector_module_path=_value(row, "connector_module_path"),
            connector_test_path=_value(row, "connector_test_path"),
            connector_docs_path=_value(row, "connector_docs_path"),
            gate_passed_count=int(_value(row, "passed_gate_count", 0) or 0),
            gate_manual_review_count=0,
            gate_blocked_count=int(_value(row, "blocked_gate_count", 0) or 0),
            gate_total_count=int(_value(row, "total_gate_count", 0) or 0),
            latest_blocking_gate=_value(row, "blocking_gate"),
            latest_blocking_reason=_value(row, "blocker_reason"),
            connector_validation_status=None,
            connector_validation_decision=None,
            final_approval_status=None,
            final_approval_decision=None,
        )
        for row in rows
    ]


def _summary_from_row(row: object | None) -> GoldMarketCoverageSummary:
    if row is None:
        return GoldMarketCoverageSummary()
    values = {
        field: _value(row, field)
        for field in GoldMarketCoverageSummary.__dataclass_fields__
    }
    return GoldMarketCoverageSummary(**values)


def _rows_to_orchestrator_steps(rows: list[object]) -> list[OrchestratorAttentionStep]:
    return [
        OrchestratorAttentionStep(
            run_id=int(_value(row, "run_id", 0) or 0),
            step_order=int(_value(row, "step_order", 0) or 0),
            step_name=str(_value(row, "step_name", "")),
            step_status=str(_value(row, "step_status", "")),
            action_mode=str(_value(row, "action_mode", "")),
            recommendation=str(_value(row, "recommendation", "")),
            reason=_value(row, "reason"),
            metrics=_value(row, "metrics") if isinstance(_value(row, "metrics"), dict) else None,
            completed_at=_value(row, "completed_at"),
        )
        for row in rows
    ]


def _db_object_exists(conn: psycopg.Connection[object], name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            select exists (
                select 1
                from information_schema.tables
                where table_schema = 'public'
                  and table_name = %s
            );
            """,
            (name,),
        )
        row = cur.fetchone()
        return bool(row and _value(row, "exists"))


def load_control_center_candidates() -> list[ControlCenterCandidate]:
    with psycopg.connect(DatabaseConfig.from_environment().dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    candidate_id,
                    company_key,
                    display_company_name,
                    candidate_url,
                    source_name_candidate,
                    source_type_candidate,
                    candidate_status,
                    candidate_risk_level,
                    fn_pressure_level,
                    fn_pressure_reason,
                    generation_status,
                    generation_recommendation,
                    build_status,
                    build_recommendation,
                    build_mode,
                    debug_next_command,
                    connector_module_path,
                    connector_test_path,
                    connector_docs_path,
                    passed_gate_count,
                    blocked_gate_count,
                    total_gate_count,
                    blocking_gate,
                    blocker_reason,
                    current_stage,
                    recommended_next_action,
                    last_signal_at
                from gold_candidate_lifecycle_status
                order by
                    case when current_stage = 'build_approval_required' then 0 else 1 end,
                    case when fn_pressure_level = 'critical' then 0 when fn_pressure_level = 'high' then 1 else 2 end,
                    last_signal_at desc nulls last,
                    display_company_name
                """
            )
            rows = cur.fetchall()
    return _rows_to_candidates(rows)


def load_market_coverage_summary() -> GoldMarketCoverageSummary:
    with psycopg.connect(DatabaseConfig.from_environment().dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("select * from gold_market_coverage_summary")
            row = cur.fetchone()
    return _summary_from_row(row)


def load_orchestrator_attention_steps() -> list[OrchestratorAttentionStep]:
    with psycopg.connect(DatabaseConfig.from_environment().dsn(), row_factory=dict_row) as conn:
        if not _db_object_exists(conn, "gold_search_intelligence_orchestrator_attention_steps"):
            return []
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    run_id,
                    step_order,
                    step_name,
                    step_status,
                    action_mode,
                    recommendation,
                    reason,
                    metrics,
                    completed_at
                from gold_search_intelligence_orchestrator_attention_steps
                order by attention_priority, step_order
                limit 20;
                """
            )
            rows = cur.fetchall()
    return _rows_to_orchestrator_steps(rows)


def _rows_to_agent_gate_reviews(rows: list[object]) -> list[AgentGateReview]:
    return [
        AgentGateReview(
            candidate_id=int(_value(row, "candidate_id", 0) or 0),
            company_key=str(_value(row, "company_key", "")),
            company_name=str(_value(row, "company_name", "")),
            source_name_candidate=str(_value(row, "source_name_candidate", "")),
            gate_name=str(_value(row, "gate_name", "")),
            gate_status=str(_value(row, "gate_status", "")),
            decision=_value(row, "decision"),
            stop_reason=_value(row, "stop_reason"),
            reviewed_by=_value(row, "reviewed_by"),
            created_at=_value(row, "created_at"),
        )
        for row in rows
    ]


def load_agent_gate_reviews() -> list[AgentGateReview]:
    with psycopg.connect(DatabaseConfig.from_environment().dsn(), row_factory=dict_row) as conn:
        if not _db_object_exists(conn, "employer_origin_candidate_gate_reviews"):
            return []
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    r.candidate_id,
                    coalesce(l.company_key, c.company_key, '') as company_key,
                    coalesce(l.display_company_name, c.company_key, '') as company_name,
                    coalesce(l.source_name_candidate, c.source_name_candidate, '') as source_name_candidate,
                    r.gate_name,
                    r.gate_status,
                    r.decision,
                    r.stop_reason,
                    r.reviewed_by,
                    r.created_at
                from employer_origin_candidate_gate_reviews r
                left join gold_candidate_lifecycle_status l
                  on l.candidate_id = r.candidate_id
                left join employer_origin_source_candidates c
                  on c.id = r.candidate_id
                where r.gate_name in (
                    'detail_evidence_gate',
                    'connector_candidate_gate',
                    'connector_validation_gate',
                    'final_approval_gate',
                    'controlled_activation_gate',
                    'bronze_validation',
                    'silver_validation',
                    'source_lifecycle_tracking'
                )
                order by r.created_at desc, r.gate_order desc
                limit 80;
                """
            )
            rows = cur.fetchall()
    return _rows_to_agent_gate_reviews(rows)


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
            market_summary = load_market_coverage_summary()
            orchestrator_steps = load_orchestrator_attention_steps()
            gate_reviews = load_agent_gate_reviews()
            body = render_control_center(
                candidates,
                reviewed_by=self.state.reviewed_by,
                target_location=self.state.target_location,
                write_actions_enabled=self.state.allow_write_actions,
                flash_message=self.state.flash_message,
                active_tab=active_tab,
                market_summary=market_summary,
                orchestrator_steps=orchestrator_steps,
                gate_reviews=gate_reviews,
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
        if self.path not in {"/actions/rerun-evidence-repair", "/actions/approve-build", "/actions/approve-registration"}:
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
        elif self.path == "/actions/rerun-evidence-repair":
            if approval_token != EVIDENCE_REPAIR_TOKEN:
                self.state.flash_message = f"Action blocked: exact token {EVIDENCE_REPAIR_TOKEN!r} required."
            else:
                self.state.flash_message = run_command(
                    evidence_repair_command(company_key, self.state.target_location, reviewed_by)
                )
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
        self.send_header("Location", "/?tab=review-queue")
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
