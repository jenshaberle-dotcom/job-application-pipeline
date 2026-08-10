from __future__ import annotations

import argparse
import json

from src.job_lifecycle_health import (
    APPROVAL_TOKEN,
    REQUEST_TIMEOUT_SECONDS,
    build_health_probe_manifest,
)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Probe one exact employer-origin vacancy and classify current "
            "lifecycle health. Default mode is dry-run/no DB write."
        )
    )
    parser.add_argument("--silver-job-id", type=positive_int, required=True)
    parser.add_argument("--expected-source-name", required=True)
    parser.add_argument("--expected-source-url", required=True)
    parser.add_argument(
        "--timeout-seconds",
        type=positive_float,
        default=REQUEST_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Append exactly one reviewed job_health_observations row.",
    )
    parser.add_argument(
        "--approval-token",
        help=f"Required with --apply; exact token: {APPROVAL_TOKEN}",
    )
    parser.add_argument(
        "--observed-by",
        help="Required with --apply; operator/reviewer identity for audit evidence.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        manifest = build_health_probe_manifest(
            silver_job_id=args.silver_job_id,
            expected_source_name=args.expected_source_name,
            expected_source_url=args.expected_source_url,
            apply=args.apply,
            approval_token=args.approval_token,
            observed_by=args.observed_by,
            timeout_seconds=args.timeout_seconds,
        )
    except ValueError as exc:
        print(
            json.dumps(
                {
                    "status": "job_lifecycle_health_probe_blocked",
                    "error": str(exc),
                    "database_write": False,
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2

    print(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
