from __future__ import annotations

import argparse
import json

from src.run_silver_jobs import positive_integer, resolve_source_patterns
from src.silver.relevance import (
    get_accessibility_matches,
    get_role_matches,
    get_skill_matches,
    get_silver_decision_reason,
    is_relevant_for_silver,
)
from src.silver.repository import SilverJobRepository
from src.silver.transformer import transform_raw_job_to_silver


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Review the exact Bronze-to-Silver selection in a DB-enforced "
            "read-only transaction."
        )
    )
    parser.add_argument(
        "--source",
        help="Optional exact source name or source-family filter.",
    )
    parser.add_argument(
        "--ingestion-run-id",
        type=positive_integer,
        help="Optional exact ingestion run id to bind Bronze selection.",
    )
    parser.add_argument("--limit", type=positive_integer, default=100)
    return parser


def review_raw_job(raw_job: dict) -> dict:
    role_matches = get_role_matches(raw_job)
    skill_matches = get_skill_matches(raw_job)
    accessibility_matches = get_accessibility_matches(raw_job)
    relevant = is_relevant_for_silver(raw_job)
    decision_reason = get_silver_decision_reason(raw_job)

    transformed: dict | None = None
    if relevant:
        silver_job = transform_raw_job_to_silver(raw_job)
        transformed = {
            "raw_job_id": silver_job.get("raw_job_id"),
            "source_url": silver_job.get("source_url"),
            "title": silver_job.get("title"),
            "company_name": silver_job.get("company_name"),
            "city": silver_job.get("city"),
            "postal_code": silver_job.get("postal_code"),
            "country": silver_job.get("country"),
            "canonical_source_type": silver_job.get("canonical_source_type"),
            "canonical_key_candidate": silver_job.get("canonical_key_candidate"),
        }

    return {
        "raw_job_id": raw_job["id"],
        "source_name": raw_job["source_name"],
        "external_job_id": raw_job.get("external_job_id"),
        "source_url": raw_job.get("source_url"),
        "source_type": (raw_job.get("raw_data") or {}).get("source_type"),
        "relevant": relevant,
        "decision_reason": decision_reason,
        "role_matches": role_matches,
        "skill_matches": skill_matches,
        "accessibility_matches": accessibility_matches,
        "transformed_if_relevant": transformed,
    }


def build_manifest(
    *,
    source: str | None,
    ingestion_run_id: int | None,
    limit: int,
    rows: list[dict],
    transaction_read_only: str,
) -> dict:
    if transaction_read_only != "on":
        raise RuntimeError("Silver preflight transaction is not read-only")

    reviewed_rows = [review_raw_job(row) for row in rows]

    return {
        "status": "silver_selection_preflight",
        "transaction_read_only": transaction_read_only,
        "selection": {
            "source": source,
            "source_patterns": resolve_source_patterns(source),
            "ingestion_run_id": ingestion_run_id,
            "limit": limit,
            "selected_count": len(reviewed_rows),
            "selected_raw_job_ids": [row["raw_job_id"] for row in reviewed_rows],
        },
        "rows": reviewed_rows,
        "summary": {
            "relevant_count": sum(1 for row in reviewed_rows if row["relevant"]),
            "non_relevant_count": sum(
                1 for row in reviewed_rows if not row["relevant"]
            ),
        },
        "boundary": {
            "database_writes": False,
            "silver_writes": False,
            "processing_decision_writes": False,
            "bronze_writes": False,
            "network_requests": False,
            "provider_or_llm": False,
            "ranking_or_application_writes": False,
        },
    }


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    source_patterns = resolve_source_patterns(args.source)
    repository = SilverJobRepository()
    rows, transaction_read_only = repository.preview_unprocessed_raw_jobs(
        limit=args.limit,
        source_patterns=source_patterns,
        ingestion_run_id=args.ingestion_run_id,
    )

    manifest = build_manifest(
        source=args.source,
        ingestion_run_id=args.ingestion_run_id,
        limit=args.limit,
        rows=rows,
        transaction_read_only=transaction_read_only,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
