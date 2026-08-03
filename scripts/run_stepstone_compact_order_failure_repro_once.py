"""Authorize exactly one early execution of the compact StepStone experiment.

This wrapper does not weaken the normal compact runner. It is locked to the
persisted review-4 baseline observation, requires both existing operator
approval and an additional exact override token, and atomically consumes a
local marker before the compact runner can issue its first request.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import scripts.run_stepstone_compact_order_failure_repro as compact
from scripts.run_stepstone_order_failure_repro_probe import APPROVAL_TOKEN

ONE_TIME_OVERRIDE_TOKEN = (
    "run_stepstone_compact_order_failure_repro_once_review4_20260803"
)
LOCKED_BASELINE_OBSERVED_AT = datetime.fromisoformat(
    "2026-08-03T07:01:28.906225+00:00"
)
LOCKED_COOLDOWN_HOURS = 24
DEFAULT_MARKER_PATH = (
    Path.home()
    / ".local"
    / "state"
    / "job-application-pipeline"
    / "stepstone_compact_review4_early_override.used.json"
)


def authorize_one_time_early_override(
    *,
    execute: bool,
    approval_token: str | None,
    override_token: str | None,
    baseline_observed_at: datetime,
    cooldown_hours: int,
    marker_path: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    reference = (now or datetime.now(UTC)).astimezone(UTC)
    observed = baseline_observed_at.astimezone(UTC)
    not_before = observed + timedelta(hours=cooldown_hours)

    if not execute:
        raise SystemExit("One-time override requires --execute.")
    if approval_token != APPROVAL_TOKEN:
        raise SystemExit("One-time override blocked: exact --approval-token is required.")
    if override_token != ONE_TIME_OVERRIDE_TOKEN:
        raise SystemExit(
            "One-time override blocked: exact --one-time-cooldown-override-token "
            "is required."
        )
    if observed != LOCKED_BASELINE_OBSERVED_AT:
        raise SystemExit(
            "One-time override blocked: persisted baseline observation does not "
            "match the locked review-4 baseline."
        )
    if cooldown_hours != LOCKED_COOLDOWN_HOURS:
        raise SystemExit("One-time override blocked: cooldown contract changed.")
    if reference >= not_before:
        raise SystemExit(
            "One-time override is no longer applicable; use the normal compact "
            "runner because the regular cooldown has elapsed."
        )
    if marker_path.exists():
        raise SystemExit(
            "One-time override already consumed: " + str(marker_path)
        )

    return {
        "execute": True,
        "now": reference,
        "not_before": not_before,
        "execution_allowed_now": True,
        "execution_mode": "operator_approved_one_time_early_override",
        "locked_baseline_observed_at": LOCKED_BASELINE_OBSERVED_AT,
        "one_time_override_marker": marker_path,
        "one_time_override_consumed": False,
        "explicit_analog_required": True,
        "explicit_hypothesis_required": True,
    }


def consume_one_time_override(
    *,
    authorization: dict[str, Any],
    marker_path: Path,
) -> dict[str, Any]:
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "pipeline.stepstone.one_time_early_override.v1",
        "consumed_at": datetime.now(UTC).isoformat(),
        "execution_mode": authorization["execution_mode"],
        "locked_baseline_observed_at": str(
            authorization["locked_baseline_observed_at"]
        ),
        "not_before": str(authorization["not_before"]),
        "marker_path": str(marker_path),
    }
    try:
        descriptor = os.open(
            marker_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
    except FileExistsError as exc:
        raise SystemExit(
            "One-time override already consumed: " + str(marker_path)
        ) from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return {
        **authorization,
        "one_time_override_consumed": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--one-time-cooldown-override-token")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    marker_path = DEFAULT_MARKER_PATH
    original_gate = compact.enforce_execution_gate

    def one_time_gate(
        *,
        execute: bool,
        approval_token: str | None,
        baseline_observed_at: datetime,
        cooldown_hours: int,
        analog: dict[str, Any] | None,
        hypothesis: str | None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if analog is None or hypothesis is None:
            raise SystemExit(
                "One-time override blocked: compact experiment contract is incomplete."
            )
        authorization = authorize_one_time_early_override(
            execute=execute,
            approval_token=approval_token,
            override_token=args.one_time_cooldown_override_token,
            baseline_observed_at=baseline_observed_at,
            cooldown_hours=cooldown_hours,
            marker_path=marker_path,
            now=now,
        )
        return consume_one_time_override(
            authorization=authorization,
            marker_path=marker_path,
        )

    compact.enforce_execution_gate = one_time_gate
    sys.argv = [
        "run_stepstone_compact_order_failure_repro",
        "--execute",
        "--approval-token",
        str(args.approval_token or ""),
    ]
    try:
        compact.main()
    finally:
        compact.enforce_execution_gate = original_gate


if __name__ == "__main__":
    main()
