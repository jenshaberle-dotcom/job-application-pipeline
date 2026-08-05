from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from scripts.import_private_candidate_fact_profile import ensure_schema
from src.config import get_database_config
from src.search_intelligence.candidate_fact_profile import PROFILE_KEY
from src.search_intelligence.candidate_fact_profile_readiness import (
    REPORT_SCHEMA,
    CandidateFactProfileReadiness,
    evaluate_candidate_fact_profile_readiness,
)


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def load_profile_row(conn: psycopg.Connection[Any]) -> Mapping[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                profile_key,
                schema_version,
                profile_version,
                status,
                payload,
                payload_sha256,
                source_type,
                approved_by,
                approved_at
            FROM candidate_fact_profiles
            WHERE profile_key = %s
            """,
            (PROFILE_KEY,),
        )
        return cur.fetchone()


def load_fact_rows(conn: psycopg.Connection[Any]) -> tuple[Mapping[str, Any], ...]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT fact_key, fact_payload
            FROM candidate_facts
            WHERE profile_key = %s
            ORDER BY fact_key
            """,
            (PROFILE_KEY,),
        )
        return tuple(cur.fetchall())


def load_revision_count(conn: psycopg.Connection[Any]) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*)::integer AS revision_count
            FROM candidate_fact_profile_revisions
            WHERE profile_key = %s
            """,
            (PROFILE_KEY,),
        )
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("candidate fact revision count query returned no row")
    return int(row["revision_count"])


def write_report(
    *,
    output_dir: Path,
    readiness: CandidateFactProfileReadiness,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_dir / f"candidate_fact_profile_readiness_{stamp}.json"
    payload: Mapping[str, Any] = {
        "schema_version": REPORT_SCHEMA,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "review_output_only_not_pipeline_input": True,
        "mode": "read_only",
        "readiness": readiness.canonical_payload(),
        "redaction": {
            "personal_statements_emitted": False,
            "provenance_references_emitted": False,
            "capability_tag_values_emitted": False,
            "fact_keys_emitted": False,
            "approver_identity_emitted": False,
        },
        "boundaries": {
            "database_writes": 0,
            "candidate_fact_writes": 0,
            "eon_requirement_comparison_created": False,
            "capability_fit_decision_created": False,
            "assessment_mutation": False,
            "readiness_mutation": False,
            "ranking_scores_created": False,
            "weekly_hours_inferred": False,
            "network_requests": 0,
            "provider_requests": 0,
            "source_or_scheduler_activation": False,
            "application_action_performed": False,
        },
    }
    path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit whether the private default Candidate Fact profile is an eligible "
            "input to a later comparison without emitting personal facts or deciding fit."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    conn = connect()
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
            ensure_schema(conn)
            profile_row = load_profile_row(conn)
            fact_rows = load_fact_rows(conn) if profile_row is not None else ()
            revision_count = load_revision_count(conn) if profile_row is not None else 0
            readiness = evaluate_candidate_fact_profile_readiness(
                profile_row=profile_row,
                fact_rows=fact_rows,
                revision_count=revision_count,
            )
        conn.rollback()
    finally:
        conn.close()

    report_path = write_report(output_dir=args.output_dir, readiness=readiness)

    print("Candidate Fact profile readiness audit")
    print("mode: read_only")
    print(f"audit_key: {readiness.audit_key}")
    print(f"profile_state: {readiness.profile_state}")
    print(f"profile_version: {readiness.profile_version or 'none'}")
    print(f"payload_sha256: {readiness.payload_sha256 or 'none'}")
    print(f"payload_valid: {str(readiness.payload_valid).lower()}")
    print(f"payload_hash_matches: {str(readiness.payload_hash_matches).lower()}")
    print(f"normalized_rows_match: {str(readiness.normalized_rows_match).lower()}")
    print(
        "approval_metadata_present: "
        f"{str(readiness.approval_metadata_present).lower()}"
    )
    print(f"revision_count: {readiness.revision_count}")
    print(f"fact_count: {readiness.fact_count}")
    print(f"approved_fact_count: {readiness.approved_fact_count}")
    print(
        "capability_evidence_fact_count: "
        f"{readiness.capability_evidence_fact_count}"
    )
    print(
        "production_evidence_fact_count: "
        f"{readiness.production_evidence_fact_count}"
    )
    print(
        "distinct_capability_tag_count: "
        f"{readiness.distinct_capability_tag_count}"
    )
    print(
        "category_counts: "
        + ",".join(
            f"{key}={value}" for key, value in readiness.category_counts.items()
        )
    )
    print(
        "evidence_class_counts: "
        + ",".join(
            f"{key}={value}"
            for key, value in readiness.evidence_class_counts.items()
        )
    )
    print(
        "approval_status_counts: "
        + ",".join(
            f"{key}={value}"
            for key, value in readiness.approval_status_counts.items()
        )
    )
    print(
        "comparison_input_ready: "
        f"{str(readiness.comparison_input_ready).lower()}"
    )
    print(
        "blockers: "
        + (",".join(readiness.blockers) if readiness.blockers else "none")
    )
    print("personal_statements_emitted: false")
    print("provenance_references_emitted: false")
    print("capability_tag_values_emitted: false")
    print("database_writes: 0")
    print("candidate_fact_writes: 0")
    print("capability_fit_decision_created: false")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
