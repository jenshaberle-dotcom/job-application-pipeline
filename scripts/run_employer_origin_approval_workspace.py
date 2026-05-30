from __future__ import annotations

import argparse
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs
from typing import Any

import psycopg

from scripts.employer_origin_approval_workspace import (
    evaluate_workspace_action,
    render_workspace_html,
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


def find_queue_item(queue_items: list[Any], company_key: str) -> Any | None:
    for item in queue_items:
        if item.candidate.company_key == company_key:
            return item
    return None


def run_approved_command(command: tuple[str, ...]) -> str:
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout_tail = completed.stdout[-3000:]
    stderr_tail = completed.stderr[-3000:]
    return (
        f"command: {' '.join(command)}\n"
        f"returncode: {completed.returncode}\n"
        f"--- stdout tail ---\n{stdout_tail}\n"
        f"--- stderr tail ---\n{stderr_tail}"
    )


class ApprovalWorkspaceHandler(BaseHTTPRequestHandler):
    server_version = "EmployerOriginApprovalWorkspace/0.1"

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
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        if self.path not in {"/", "/index.html"}:
            self.send_error(404)
            return

        queue_items, gates_by_candidate_id = load_queue_state(self.workspace_state)
        html = render_workspace_html(
            queue_items,
            gates_by_candidate_id,
            target_location=self.workspace_state.target_location,
            reviewed_by=self.workspace_state.reviewed_by,
            write_actions_enabled=self.workspace_state.allow_write_actions,
            flash_message=self.workspace_state.flash_message,
        )
        self.workspace_state.flash_message = None
        self.send_html(html)

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        if self.path == "/actions/shutdown":
            self.workspace_state.flash_message = "Workspace shutdown requested from browser."
            self.send_html(
                "<!doctype html><html><head><meta charset='utf-8'><title>Workspace stopped</title></head>"
                "<body><main><h1>Employer-Origin Approval Workspace stopped</h1>"
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
    print(f"Job-Pipeline Approval Workspace running at http://{args.host}:{args.port}/ ({mode})")
    print("Boundary: no source activation, no Bronze writes, no scheduler changes.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nJob-Pipeline Approval Workspace stopped by user.")
    finally:
        server.server_close()
        print("Job-Pipeline Approval Workspace stopped.")


def main() -> None:
    run_server(build_parser().parse_args())


if __name__ == "__main__":
    main()
