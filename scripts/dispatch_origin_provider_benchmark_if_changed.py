"""Dispatch the private origin-provider runtime only when relevant DB truth changed.

This command is intended to run after a successful local pipeline/data refresh.
It sends metadata and a SHA-256 fingerprint only. Candidate names, URLs and
other database rows never leave the local machine through repository_dispatch.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from scripts.run_origin_source_discovery_agent import load_local_env_file
from src.config import get_database_config
from src.search_intelligence.origin_provider_event_runtime import (
    ProviderBudget,
    build_dispatch_payload,
    load_origin_benchmark_projection,
    normalize_company_keys,
    projection_fingerprint,
)

DEFAULT_STATE_FILE = Path(".runtime/origin-provider-dispatch-state.json")
DEFAULT_PIPELINE_REPOSITORY = "jenshaberle-dotcom/job-application-pipeline"
EVENT_TYPE = "origin-provider-benchmark-requested"


def _run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def resolve_pipeline_ref(explicit_ref: str | None, *, allow_dirty: bool) -> str:
    if not allow_dirty and _run_git("status", "--porcelain"):
        raise SystemExit(
            "Refusing dispatch from a dirty worktree. Commit/stash changes or pass --allow-dirty."
        )
    return explicit_ref or _run_git("rev-parse", "HEAD")


def verify_remote_ref(repository: str, pipeline_ref: str) -> None:
    subprocess.run(
        ["gh", "api", f"repos/{repository}/commits/{pipeline_ref}", "--silent"],
        check=True,
    )


def dispatch_event(runtime_repository: str, payload: dict[str, object]) -> None:
    body = json.dumps(
        {"event_type": EVENT_TYPE, "client_payload": payload},
        ensure_ascii=False,
        sort_keys=True,
    )
    subprocess.run(
        [
            "gh",
            "api",
            "--method",
            "POST",
            f"repos/{runtime_repository}/dispatches",
            "--input",
            "-",
        ],
        input=body,
        text=True,
        check=True,
    )


def load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_state(
    path: Path,
    *,
    runtime_repository: str,
    payload: dict[str, object],
    projection_count: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "schema_version": "origin_provider_dispatch_state.v1",
        "runtime_repository": runtime_repository,
        "projection_count": projection_count,
        "last_dispatched_payload": payload,
        "dispatched_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def comparable_payload(payload: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in payload.items() if key != "requested_at"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fingerprint the bounded origin-candidate projection and dispatch the private "
            "GitHub runtime only when it changed."
        )
    )
    parser.add_argument(
        "--runtime-repository",
        default=os.getenv("ORIGIN_RUNTIME_REPOSITORY"),
        help="Private owner/repository receiving repository_dispatch.",
    )
    parser.add_argument(
        "--pipeline-repository",
        default=DEFAULT_PIPELINE_REPOSITORY,
    )
    parser.add_argument("--pipeline-ref", help="Committed pipeline ref; defaults to HEAD.")
    parser.add_argument("--company-key", action="append")
    parser.add_argument("--max-candidates", type=int, default=6)
    parser.add_argument("--search-query-limit", type=int, default=2)
    parser.add_argument("--search-max-results", type=int, default=5)
    parser.add_argument("--max-provider-requests", type=int, default=12)
    parser.add_argument("--market-evidence-limit", type=int, default=10)
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument(
        "--retry-unchanged-after-hours",
        type=float,
        default=12.0,
        help=(
            "Redispatch unchanged truth after this recovery window. The private runtime "
            "uses a success cache, so completed fingerprints do not call Tavily again."
        ),
    )
    parser.add_argument(
        "--dispatch",
        action="store_true",
        help="Send repository_dispatch. Without this flag the command is a dry-run.",
    )
    parser.add_argument("--force", action="store_true", help="Dispatch even if unchanged.")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow a dirty worktree; the dispatched ref still resolves to a committed SHA.",
    )
    return parser


def main() -> int:
    load_local_env_file()
    args = build_parser().parse_args()
    runtime_repository = str(args.runtime_repository or "").strip()
    if "/" not in runtime_repository:
        raise SystemExit(
            "Set --runtime-repository or ORIGIN_RUNTIME_REPOSITORY to private owner/repository."
        )

    budget = ProviderBudget(
        max_candidates=args.max_candidates,
        search_query_limit=args.search_query_limit,
        search_max_results=args.search_max_results,
        max_provider_requests=args.max_provider_requests,
    ).validate()
    pipeline_ref = resolve_pipeline_ref(args.pipeline_ref, allow_dirty=args.allow_dirty)

    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        projection = load_origin_benchmark_projection(
            conn,
            limit=budget.effective_candidate_limit,
            market_evidence_limit=args.market_evidence_limit,
            company_keys=normalize_company_keys(args.company_key),
            include_active_controlled=False,
        )

    if not projection:
        print("origin_provider_dispatch: no eligible candidates; no event sent")
        return 0

    fingerprint = projection_fingerprint(projection)
    payload = build_dispatch_payload(
        pipeline_repository=args.pipeline_repository,
        pipeline_ref=pipeline_ref,
        fingerprint=fingerprint,
        budget=budget,
        target_location=args.target_location,
        requested_at=datetime.now(timezone.utc).isoformat(),
    )
    previous = load_state(args.state_file)
    previous_payload = previous.get("last_dispatched_payload")
    unchanged = (
        previous.get("runtime_repository") == runtime_repository
        and isinstance(previous_payload, dict)
        and comparable_payload(previous_payload) == comparable_payload(payload)
    )
    if args.retry_unchanged_after_hours < 0:
        raise SystemExit("--retry-unchanged-after-hours must not be negative")
    retry_due = False
    if unchanged:
        try:
            dispatched_at = datetime.fromisoformat(str(previous["dispatched_at"]))
            if dispatched_at.tzinfo is None:
                dispatched_at = dispatched_at.replace(tzinfo=timezone.utc)
            retry_due = datetime.now(timezone.utc) >= dispatched_at + timedelta(
                hours=args.retry_unchanged_after_hours
            )
        except (KeyError, TypeError, ValueError):
            retry_due = True

    print(
        "origin_provider_dispatch_plan: "
        f"projection_count={len(projection)} "
        f"fingerprint={fingerprint} "
        f"planned_provider_requests={budget.planned_provider_requests} "
        f"runtime_repository={runtime_repository} "
        f"pipeline_ref={pipeline_ref} "
        f"changed={not unchanged} "
        f"recovery_retry_due={retry_due}"
    )

    if unchanged and not args.force and not retry_due:
        print("origin_provider_dispatch: unchanged projection inside recovery window; no event sent")
        return 0
    if unchanged and retry_due and not args.force:
        print("origin_provider_dispatch: recovery retry for unchanged projection")
    if not args.dispatch:
        print("origin_provider_dispatch: dry-run only; pass --dispatch after review")
        return 0

    verify_remote_ref(args.pipeline_repository, pipeline_ref)
    dispatch_event(runtime_repository, payload)
    write_state(
        args.state_file,
        runtime_repository=runtime_repository,
        payload=payload,
        projection_count=len(projection),
    )
    print("origin_provider_dispatch: event accepted by GitHub")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
