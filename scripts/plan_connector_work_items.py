from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import subprocess

from src.connectors.registry import SourceRole, source_role
from src.ingest_jobs import select_profiles
from src.ingestion.connector_work_item import build_connector_work_item
from src.ingestion.repository import JobIngestionRepository


def _current_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        text=True,
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Plan portable connector work items without executing connectors or "
            "mutating ingestion state."
        )
    )
    parser.add_argument("--pipeline-sha", required=True)
    parser.add_argument(
        "--scheduled-for",
        required=True,
        help="Explicit scheduler slot as ISO-8601 UTC timestamp.",
    )
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--profile")
    selector.add_argument(
        "--role",
        choices=[role.value for role in SourceRole],
    )
    args = parser.parse_args()

    requested_sha = args.pipeline_sha.strip().lower()
    observed_sha = _current_head()
    if observed_sha != requested_sha:
        raise SystemExit(
            f"Pipeline SHA mismatch requested={requested_sha} observed={observed_sha}"
        )

    scheduled_for = datetime.fromisoformat(
        args.scheduled_for.strip().replace("Z", "+00:00")
    )
    if scheduled_for.tzinfo is None or scheduled_for.utcoffset() is None:
        raise SystemExit("scheduled-for must include a timezone")
    scheduled_for = scheduled_for.astimezone(UTC)

    repository = JobIngestionRepository()
    selected = select_profiles(
        repository,
        profile_name=args.profile,
        source_filter=None,
        role_filter=SourceRole(args.role) if args.role else None,
    )

    items = [
        build_connector_work_item(
            profile,
            source_role=source_role(profile.source_name).value,
            pipeline_sha=requested_sha,
            scheduled_for=scheduled_for,
        ).to_dict()
        for profile in selected
    ]
    payload = {
        "schema_version": "jap.connector_work_batch.v1",
        "pipeline_sha": requested_sha,
        "scheduled_for_utc": scheduled_for.replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "item_count": len(items),
        "items": items,
        "boundary": {
            "connector_execution": False,
            "database_mutation": False,
            "source_activation": False,
            "provider_requests": 0,
        },
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
