#!/usr/bin/env python3
"""Read-only live-DB persistence preflight for a bounded normalized F5 mailbox batch."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_f5_candidate_supersession_schema_qualification import (  # noqa: E402
    current as qualify_candidate_schema_current,
)
from scripts.run_product_v1_f5_mailbox_persistence_apply import (  # noqa: E402
    PersistenceApplyError,
    _assert_plan_is_safe,
    _checkout_sha,
    _load_live_state,
    _plan_sha256,
    _sha256_file,
    _validate_sha256,
    _validate_source_sha,
)
from scripts.run_product_v1_f5_mailbox_persistence_preflight import (  # noqa: E402
    load_jsonl,
    plan_rows,
)


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO date: {value}") from exc


def live_preflight(
    *,
    input_path: Path,
    expected_input_sha256: str,
    expected_plan_sha256: str,
    source_sha: str,
    since: date | None,
    until: date | None,
) -> dict[str, object]:
    expected_input_sha256 = _validate_sha256(
        expected_input_sha256, name="expected_input_sha256"
    )
    expected_plan_sha256 = _validate_sha256(
        expected_plan_sha256, name="expected_plan_sha256"
    )
    source_sha = _validate_source_sha(source_sha)

    actual_source_sha = _checkout_sha()
    if actual_source_sha != source_sha:
        raise PersistenceApplyError(
            f"checkout_source_mismatch:expected={source_sha}:actual={actual_source_sha}"
        )

    actual_input_sha256 = _sha256_file(input_path)
    if actual_input_sha256 != expected_input_sha256:
        raise PersistenceApplyError(
            "input_sha256_mismatch:"
            f"expected={expected_input_sha256}:actual={actual_input_sha256}"
        )

    rows = load_jsonl(input_path)
    qualify_candidate_schema_current(source_sha=source_sha)

    import psycopg
    from psycopg.rows import dict_row

    from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig

    with psycopg.connect(
        DatabaseConfig.from_environment().dsn(),
        row_factory=dict_row,
    ) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            application_keys, active = _load_live_state(conn)
            plan = plan_rows(
                rows,
                existing_application_keys=application_keys,
                active_candidates=active,
                since=since,
                until=until,
            )
            _assert_plan_is_safe(plan)
            actual_plan_sha256 = _plan_sha256(plan)

    if actual_plan_sha256 != expected_plan_sha256:
        raise PersistenceApplyError(
            "plan_sha256_mismatch:"
            f"expected={expected_plan_sha256}:actual={actual_plan_sha256}"
        )

    return {
        "schema": "jap.f5.mailbox_persistence_live_preflight.v1",
        "source_sha": source_sha,
        "input_sha256": actual_input_sha256,
        "plan_sha256": actual_plan_sha256,
        **asdict(plan),
        "gmail_network_requests": 0,
        "database_connections": 1,
        "database_writes": 0,
        "email_actions": 0,
        "application_submission_actions": 0,
        "authoritative_lifecycle_mutations": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only live-DB F5 mailbox persistence preflight"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--expected-input-sha256", required=True)
    parser.add_argument("--expected-plan-sha256", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--since", type=_parse_iso_date)
    parser.add_argument("--until", type=_parse_iso_date)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.since is not None and args.until is not None and args.until < args.since:
        print("F5_MAILBOX_PERSISTENCE_LIVE_PREFLIGHT_ERROR=until_before_since")
        return 2

    try:
        report = live_preflight(
            input_path=args.input.expanduser(),
            expected_input_sha256=args.expected_input_sha256,
            expected_plan_sha256=args.expected_plan_sha256,
            source_sha=args.source_sha,
            since=args.since,
            until=args.until,
        )
    except (PersistenceApplyError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"F5_MAILBOX_PERSISTENCE_LIVE_PREFLIGHT_ERROR={exc}")
        return 2

    output = args.output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("F5_MAILBOX_PERSISTENCE_LIVE_PREFLIGHT=PASS")
    for key in (
        "source_sha",
        "input_sha256",
        "plan_sha256",
        "input_rows",
        "window_rows",
        "valid_rows",
        "invalid_rows",
        "persistence_candidate_rows",
        "skipped_other_rows",
        "application_inserts",
        "candidate_inserts",
        "candidate_noops",
        "candidate_supersessions",
        "unique_source_messages",
    ):
        print(f"{key.upper()}={report[key]}")
    for candidate_class, count in report["class_counts"].items():
        print(f"CLASS_{candidate_class.upper()}={count}")
    print("GMAIL_NETWORK_REQUESTS=0")
    print("DATABASE_CONNECTIONS=1")
    print("DATABASE_WRITES=0")
    print("EMAIL_ACTIONS=0")
    print("APPLICATION_SUBMISSION_ACTIONS=0")
    print("AUTHORITATIVE_LIFECYCLE_MUTATIONS=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
