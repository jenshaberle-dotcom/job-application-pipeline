from __future__ import annotations

import argparse
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from typing import Any

import psycopg

from scripts.employer_origin_approval_workspace import (
    WorkspaceFalseNegativeRisk,
    WorkspaceReassessmentItem,
    WorkspaceSearchTermConfidence,
    WorkspaceSearchStrategyRecommendation,
    evaluate_workspace_action,
    render_workspace_html,
)
from src.search_intelligence.false_negative_risk import (
    CandidateMarketEvidenceSummary,
    assess_many,
)
from scripts.run_employer_origin_candidate_queue_agent import (
    DatabaseConfig,
    QueueRepository,
    build_queue,
)


class WorkspaceState:
    def __init__(
        self,
        *,
        target_location: str,
        reviewed_by: str,
        allow_repair: bool,
        allow_write_actions: bool,
    ) -> None:
        self.target_location = target_location
        self.reviewed_by = reviewed_by
        self.allow_repair = allow_repair
        self.allow_write_actions = allow_write_actions
        self.flash_message: str | None = None


def load_queue_state(state: WorkspaceState) -> tuple[list[Any], dict[int, dict[str, Any]]]:
    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        repo = QueueRepository(conn)
        candidates = repo.load_candidates()
        gates_by_candidate_id = {
            candidate.candidate_id: repo.load_gate_reviews(candidate.candidate_id)
            for candidate in candidates
        }

    queue_items = build_queue(
        candidates,
        gates_by_candidate_id,
        target_location=state.target_location,
        reviewed_by=state.reviewed_by,
        allow_repair=state.allow_repair,
    )
    return queue_items, gates_by_candidate_id


def load_false_negative_risks() -> list[WorkspaceFalseNegativeRisk]:
    try:
        with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                        candidate_id,
                        company_key,
                        company_name,
                        candidate_status,
                        candidate_risk_level,
                        sighting_count,
                        recent_sighting_count,
                        last_observed_at::text as last_observed_at,
                        coalesce(evidence_sources, array[]::text[]) as evidence_sources,
                        coalesce(evidence_titles, array[]::text[]) as evidence_titles
                    from candidate_market_evidence_summary
                    order by recent_sighting_count desc, sighting_count desc, company_name
                    """
                )
                rows = cur.fetchall()
    except Exception:
        return []

    summaries = [
        CandidateMarketEvidenceSummary(
            candidate_id=int(row[0]),
            company_key=str(row[1]),
            company_name=str(row[2]),
            candidate_status=str(row[3]),
            candidate_risk_level=str(row[4]),
            sighting_count=int(row[5] or 0),
            recent_sighting_count=int(row[6] or 0),
            last_observed_at=row[7],
            evidence_sources=tuple(row[8] or ()),
            evidence_titles=tuple(row[9] or ()),
        )
        for row in rows
    ]
    return [
        WorkspaceFalseNegativeRisk(
            candidate_id=item.candidate_id,
            company_key=item.company_key,
            company_name=item.company_name,
            risk_level=item.risk_level,
            sighting_count=item.sighting_count,
            recent_sighting_count=item.recent_sighting_count,
            last_observed_at=item.last_observed_at,
            suggested_search_terms=item.suggested_search_terms,
            reason=item.reason,
        )
        for item in assess_many(summaries)
    ]


def load_reassessment_items() -> list[WorkspaceReassessmentItem]:
    try:
        with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                        rq.id,
                        rq.candidate_id,
                        rq.company_key,
                        coalesce(c.company_name, rq.company_key) as company_name,
                        rq.risk_level,
                        rq.priority,
                        rq.trigger_reason,
                        rq.suggested_search_terms,
                        rq.status,
                        rq.updated_at::text as updated_at
                    from candidate_reassessment_queue rq
                    left join employer_origin_source_candidates c on c.id = rq.candidate_id
                    where rq.status = 'open'
                    order by rq.priority desc, rq.updated_at desc, company_name
                    """
                )
                rows = cur.fetchall()
    except Exception:
        return []

    return [
        WorkspaceReassessmentItem(
            queue_id=int(row[0]),
            candidate_id=int(row[1]),
            company_key=str(row[2]),
            company_name=str(row[3]),
            risk_level=str(row[4]),
            priority=int(row[5]),
            trigger_reason=str(row[6]),
            suggested_search_terms=tuple(row[7] or ()),
            status=str(row[8]),
            updated_at=row[9],
        )
        for row in rows
    ]

def load_search_term_confidence_items() -> list[WorkspaceSearchTermConfidence]:
    try:
        with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select distinct on (suggested_term, coalesce(source_family_candidate, ''))
                        suggested_term,
                        source_family_candidate,
                        sample_size,
                        success_count,
                        failure_count,
                        noise_count,
                        confidence_score::text,
                        confidence_level,
                        created_at::text
                    from search_term_confidence_snapshots
                    order by suggested_term, coalesce(source_family_candidate, ''), created_at desc
                    """
                )
                rows = cur.fetchall()
    except Exception:
        return []

    return [
        WorkspaceSearchTermConfidence(
            suggested_term=str(row[0]),
            source_family_candidate=row[1],
            sample_size=int(row[2]),
            success_count=int(row[3]),
            failure_count=int(row[4]),
            noise_count=int(row[5]),
            confidence_score=str(row[6]),
            confidence_level=str(row[7]),
            created_at=row[8],
        )
        for row in rows
    ]

def load_search_strategy_recommendations() -> list[WorkspaceSearchStrategyRecommendation]:
    try:
        with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                        id,
                        company_key,
                        source_family_candidate,
                        suggested_term,
                        recommendation_type,
                        recommendation_status,
                        autonomy_level,
                        confidence_score::text,
                        confidence_level,
                        sample_size,
                        false_negative_risk_level,
                        false_negative_sighting_count,
                        guardrail_decision,
                        reason,
                        updated_at::text
                    from search_strategy_recommendations
                    order by
                        case recommendation_status
                            when 'auto_eligible' then 1
                            when 'pending_review' then 2
                            else 3
                        end,
                        confidence_score desc,
                        sample_size desc,
                        updated_at desc
                    """
                )
                rows = cur.fetchall()
    except Exception:
        return []

    return [
        WorkspaceSearchStrategyRecommendation(
            recommendation_id=int(row[0]),
            company_key=str(row[1]),
            source_family_candidate=row[2],
            suggested_term=str(row[3]),
            recommendation_type=str(row[4]),
            recommendation_status=str(row[5]),
            autonomy_level=str(row[6]),
            confidence_score=str(row[7]),
            confidence_level=str(row[8]),
            sample_size=int(row[9]),
            false_negative_risk_level=row[10],
            false_negative_sighting_count=int(row[11] or 0),
            guardrail_decision=str(row[12]),
            reason=str(row[13]),
            updated_at=row[14],
        )
        for row in rows
    ]



class ApprovalWorkspaceHandler(BaseHTTPRequestHandler):
    server_version = "EmployerOriginApprovalWorkspace/0.2"

    @property
    def workspace_state(self) -> WorkspaceState:
        return self.server.workspace_state  # type: ignore[attr-defined]

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

        fields = parse_qs(parsed.query)
        selected_view = fields.get("view", ["all"])[0]
        search_query = fields.get("q", [""])[0]

        queue_items, gates_by_candidate_id = load_queue_state(self.workspace_state)
        html = render_workspace_html(
            queue_items,
            gates_by_candidate_id,
            target_location=self.workspace_state.target_location,
            reviewed_by=self.workspace_state.reviewed_by,
            write_actions_enabled=self.workspace_state.allow_write_actions,
            flash_message=self.workspace_state.flash_message,
            selected_view=selected_view,
            search_query=search_query,
            false_negative_risks=load_false_negative_risks(),
            reassessment_items=load_reassessment_items(),
            confidence_items=load_search_term_confidence_items(),
            strategy_recommendations=load_search_strategy_recommendations(),
        )
        self.workspace_state.flash_message = None
        self.send_html(html)

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        if self.path == "/actions/shutdown":
            self.workspace_state.flash_message = "Workspace shutdown requested from browser."
            self.send_html(
                "<!doctype html><html><head><meta charset='utf-8'><title>Workspace stopped</title></head>"
                "<body style='font-family: system-ui; background: #07111f; color: #e6f3ff; padding: 2rem;'>"
                "<main><h1>Employer-Origin Approval Workspace stopped</h1>"
                "<p>You can close this browser tab now.</p></main></body></html>"
            )
            threading.Thread(target=self.server.shutdown, daemon=True).start()  # type: ignore[attr-defined]
            return

        if self.path != "/actions/run":
            self.send_error(404)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")
        fields = {key: values[0] for key, values in parse_qs(body).items() if values}
        company_key = fields.get("company_key", "")
        requested_action = fields.get("requested_action", "")
        approval_token = fields.get("approval_token")
        reviewed_by = fields.get("reviewed_by") or self.workspace_state.reviewed_by

        queue_items, _ = load_queue_state(self.workspace_state)
        item = find_queue_item(queue_items, company_key)
        if item is None:
            self.workspace_state.flash_message = f"No queue item found for company_key={company_key!r}."
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return

        decision = evaluate_workspace_action(
            item,
            requested_action=requested_action,
            approval_token=approval_token,
            write_actions_enabled=self.workspace_state.allow_write_actions,
            target_location=self.workspace_state.target_location,
            reviewed_by=reviewed_by,
        )

        if not decision.allowed or decision.action_plan is None:
            self.workspace_state.flash_message = f"Action blocked: {decision.reason}"
        else:
            result = run_approved_command(decision.action_plan.command)
            self.workspace_state.flash_message = f"Action executed. {result}"

        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Start a local browser workspace for employer-origin candidate review and explicit approvals. "
            "The workspace reads DB-backed gate state and can run only bounded approval actions when "
            "--allow-write-actions is provided."
        )
    )
    parser.add_argument("--host", default=os.environ.get("APPROVAL_WORKSPACE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("APPROVAL_WORKSPACE_PORT", "8765")))
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--reviewed-by", default="jens")
    parser.add_argument("--allow-repair", action="store_true")
    parser.add_argument("--allow-write-actions", action="store_true")
    return parser


def run_server(args: argparse.Namespace) -> None:
    state = WorkspaceState(
        target_location=args.target_location,
        reviewed_by=args.reviewed_by,
        allow_repair=args.allow_repair,
        allow_write_actions=args.allow_write_actions,
    )
    server = ThreadingHTTPServer((args.host, args.port), ApprovalWorkspaceHandler)
    server.workspace_state = state  # type: ignore[attr-defined]
    mode = "write-enabled" if args.allow_write_actions else "read-only"
    print(f"Employer-Origin Approval Workspace running at http://{args.host}:{args.port}/ ({mode})")
    print("Boundary: no source activation, no Bronze writes, no scheduler changes.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEmployer-Origin Approval Workspace stopped by user.")
    finally:
        server.server_close()
        print("Employer-Origin Approval Workspace stopped.")


def main() -> None:
    run_server(build_parser().parse_args())


if __name__ == "__main__":
    main()
