"""Prepare DEMO-001 local DB and operator-test execution without broad mutation authority.

Default mode is read-only. It reports local repository identity plus the existing
Product V1 demo schema-readiness projection. The only database mutation this helper
can request is the already-qualified exact migration
``104_create_product_v1_ranking_score_reviews.sql`` and only when it is the sole
pending migration with clean tracking/checksum prerequisites.

The helper does not reimplement demo readiness. ``--run-preflight`` delegates to the
canonical ``scripts/run_product_v1_live_demo.py --preflight-only`` path.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from scripts.run_product_v1_demo_preflight import _database_schema_readiness


ROOT = Path(__file__).resolve().parents[1]
EXACT_104 = "104_create_product_v1_ranking_score_reviews.sql"
PREREQUISITE_REQUIRED_MIGRATIONS = (
    "102_create_product_v1_hard_filter_operator_reviews.sql",
    "103_create_product_v1_capability_fit_reviews.sql",
)


@dataclass(frozen=True)
class RepositoryState:
    head: str
    branch: str
    origin_main: str | None
    dirty: bool

    @property
    def exact_main(self) -> bool:
        return (
            self.branch == "main"
            and self.origin_main is not None
            and self.head == self.origin_main
            and not self.dirty
        )


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def repository_state() -> RepositoryState:
    head = _git("rev-parse", "HEAD")
    branch = _git("branch", "--show-current") or "DETACHED"
    dirty = bool(_git("status", "--porcelain"))
    try:
        origin_main = _git("rev-parse", "origin/main")
    except subprocess.CalledProcessError:
        origin_main = None
    return RepositoryState(
        head=head,
        branch=branch,
        origin_main=origin_main,
        dirty=dirty,
    )


def qualifies_exact_104(schema: Mapping[str, object]) -> bool:
    """Return whether exact migration 104 is the only safe schema action available."""
    if schema.get("tracking_table_exists") is not True:
        return False
    if list(schema.get("pending_migrations") or []) != [EXACT_104]:
        return False
    if list(schema.get("checksum_mismatches") or []):
        return False
    if dict(schema.get("failed_required_tracking") or {}):
        return False
    if list(schema.get("missing_repo_migration_files") or []):
        return False

    tracking = dict(schema.get("required_migration_tracking") or {})
    if any(tracking.get(key) is not True for key in PREREQUISITE_REQUIRED_MIGRATIONS):
        return False
    if tracking.get(EXACT_104) is True:
        return False
    return True


def _print_list(name: str, values: object) -> None:
    items = list(values or []) if not isinstance(values, dict) else list(values)
    print(f"{name}={','.join(str(item) for item in items) if items else 'none'}")


def print_plan(repo: RepositoryState, schema: Mapping[str, object]) -> str:
    schema_ready = schema.get("ready") is True
    exact_104 = qualifies_exact_104(schema)

    print("=== DEMO-001 OPERATOR TEST PREPARATION ===")
    print(f"REPO_HEAD={repo.head}")
    print(f"REPO_BRANCH={repo.branch}")
    print(f"REPO_ORIGIN_MAIN={repo.origin_main or 'unresolved'}")
    print(f"REPO_DIRTY={str(repo.dirty).lower()}")
    print(f"REPO_EXACT_MAIN={str(repo.exact_main).lower()}")
    print(f"DB_SCHEMA_READY={str(schema_ready).lower()}")
    _print_list("DB_PENDING", schema.get("pending_migrations"))
    _print_list("DB_CHECKSUM_MISMATCHES", schema.get("checksum_mismatches"))
    _print_list("DB_FAILED_REQUIRED_TRACKING", schema.get("failed_required_tracking"))

    if schema_ready:
        state = "READY_FOR_PREFLIGHT" if repo.exact_main else "REPO_SYNC_REQUIRED"
        print("DB_ACTION=NONE")
    elif exact_104:
        state = "QUALIFIED_EXACT_104" if repo.exact_main else "REPO_SYNC_REQUIRED"
        print(f"DB_ACTION=QUALIFIED_EXACT_104:{EXACT_104}")
    else:
        state = "BLOCKED"
        print("DB_ACTION=BLOCKED_NO_AUTOMATIC_REPAIR")

    print(f"OPERATOR_PREP={state}")
    if not repo.exact_main:
        print("NEXT=git fetch origin main && git switch main && git pull --ff-only origin main")
    elif state == "QUALIFIED_EXACT_104":
        print("NEXT=rerun with --apply-qualified-104, optionally together with --run-preflight")
    elif state == "READY_FOR_PREFLIGHT":
        print("NEXT=rerun with --run-preflight")
    else:
        print("NEXT=inspect the exact DB blocker; do not use broad migration apply")
    return state


def apply_qualified_104() -> int:
    command = [
        sys.executable,
        "scripts/apply_db_migrations.py",
        "--apply-exact",
        EXACT_104,
        "--require-sole-pending",
        "--applied-by",
        "demo-001",
    ]
    print("+ " + " ".join(command))
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def run_canonical_preflight() -> int:
    command = [
        sys.executable,
        "scripts/run_product_v1_live_demo.py",
        "--preflight-only",
    ]
    print("+ " + " ".join(command))
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply-qualified-104",
        action="store_true",
        help="Apply exact migration 104 only after a fresh live qualification check.",
    )
    parser.add_argument(
        "--run-preflight",
        action="store_true",
        help="Run the canonical full DEMO-001 preflight after schema readiness is proven.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        repo = repository_state()
        schema = _database_schema_readiness()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"OPERATOR_PREP=BLOCKED_INSPECTION_ERROR:{exc}", file=sys.stderr)
        return 2

    state = print_plan(repo, schema)
    if args.apply_qualified_104 or args.run_preflight:
        if not repo.exact_main:
            print("OPERATOR_ACTION_BLOCKED=repository_not_exact_clean_main", file=sys.stderr)
            return 2

    if args.apply_qualified_104:
        if state != "QUALIFIED_EXACT_104":
            print("OPERATOR_ACTION_BLOCKED=exact_104_not_qualified", file=sys.stderr)
            return 2
        if apply_qualified_104() != 0:
            print("OPERATOR_ACTION_BLOCKED=exact_104_apply_failed", file=sys.stderr)
            return 2
        try:
            schema = _database_schema_readiness()
        except (OSError, RuntimeError) as exc:
            print(f"OPERATOR_ACTION_BLOCKED=post_apply_inspection:{exc}", file=sys.stderr)
            return 2
        state = print_plan(repo, schema)
        if state != "READY_FOR_PREFLIGHT":
            print("OPERATOR_ACTION_BLOCKED=schema_not_ready_after_exact_104", file=sys.stderr)
            return 2

    if args.run_preflight:
        if state != "READY_FOR_PREFLIGHT":
            print("OPERATOR_ACTION_BLOCKED=schema_not_ready_for_preflight", file=sys.stderr)
            return 2
        return run_canonical_preflight()

    return 0 if state in {"READY_FOR_PREFLIGHT", "QUALIFIED_EXACT_104", "REPO_SYNC_REQUIRED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
