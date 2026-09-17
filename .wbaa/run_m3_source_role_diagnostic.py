from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psycopg
from psycopg.rows import dict_row

from scripts.product_v1_job_presentation_runtime import (
    MARKET_SENSOR_SOURCE_FAMILIES,
    is_current_product_job,
    is_employer_origin_review_source,
)
from src.config import get_database_config

SOURCE_REPOSITORY = "jenshaberle-dotcom/job-application-pipeline"
SOURCE_SHA = "27a5e78fb3041eee1b1f3964676f62d1db82a067"
SOURCE_RELATION = "silver_jobs"
PRODUCT_READ_MODEL = "gold_product_v1_job_readiness"
TARGET_REPOSITORY = "jenshaberle-dotcom/jap-cloud-based"
TARGET_BASE = "034d234a58f01238299c08369ee095df4cfdeefc"
TARGET_PR = 31
TARGET_CANDIDATE = "e03df393f7de9354b4c37cd33711bd3e04a0879f"
TARGET_MANIFEST_BLOB_SHA = "cf303e5e63c337da1a25fcb896183f1191c5ca23"
CLASSIFIER_PATH = "scripts/product_v1_job_presentation_runtime.py"
CLASSIFIER_BLOB_SHA = "d84d47d7175a16d116a44b1f561b3d7293a06c2a"
AUTHORITY_REFERENCE = "WBAA#134-comment-5712090935"
AUTHORITY_KIND = "WBAA_JAP_CLOUD_M3_SOURCE_ROLE_DIAGNOSTIC_AUTHORIZED_V1"

REQUIRED_NON_NULL = (
    "raw_job_id",
    "source_name",
    "source_url",
    "title",
    "company_name",
    "city",
    "publication_date",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def load_and_bind_manifest(path: Path) -> str:
    raw = path.read_bytes()
    require(git_blob_sha(raw) == TARGET_MANIFEST_BLOB_SHA, "TARGET_MANIFEST_BLOB_MISMATCH")
    manifest = json.loads(raw.decode("utf-8"))
    require(manifest.get("contract_version") == "1.2", "MANIFEST_VERSION_MISMATCH")
    source = manifest.get("source") or {}
    target = manifest.get("target") or {}
    eligibility = manifest.get("eligibility") or {}
    require(source.get("repository") == SOURCE_REPOSITORY, "SOURCE_REPOSITORY_MISMATCH")
    require(source.get("source_sha") == SOURCE_SHA, "SOURCE_SHA_MISMATCH")
    require(source.get("relation") == SOURCE_RELATION, "SOURCE_RELATION_MISMATCH")
    require(
        tuple(eligibility.get("required_non_null_source_columns") or ()) == REQUIRED_NON_NULL,
        "M3_ELIGIBILITY_BINDING_MISMATCH",
    )
    require(target.get("repository") == TARGET_REPOSITORY, "TARGET_REPOSITORY_MISMATCH")
    require(target.get("base_sha") == TARGET_BASE, "TARGET_BASE_MISMATCH")
    return hashlib.sha256(raw).hexdigest()


def absolute_http(value: object) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip()
    if not normalized:
        return False
    parsed = urlsplit(normalized)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def architecture_class(row: dict[str, Any]) -> str:
    source_name = str(row.get("source_name") or "").strip().casefold()
    source_family = source_name.split(":", 1)[0]
    if source_family in MARKET_SENSOR_SOURCE_FAMILIES:
        return "market_sensor"
    if is_employer_origin_review_source(row):
        return "employer_origin"
    return "other_or_unknown"


def candidate_where(alias: str = "silver") -> str:
    return " AND ".join(f"{alias}.{column} IS NOT NULL" for column in REQUIRED_NON_NULL)


def query_rows(cur: psycopg.Cursor[Any]) -> tuple[int, list[dict[str, Any]]]:
    where = candidate_where()
    cur.execute(f"SELECT count(*) AS n FROM {SOURCE_RELATION} silver WHERE {where};")
    candidate_count = int(cur.fetchone()["n"])
    cur.execute(
        f"""
        SELECT
            silver.source_name,
            silver.source_url,
            silver.canonical_source_type,
            readiness.lifecycle_status
        FROM {SOURCE_RELATION} silver
        LEFT JOIN {PRODUCT_READ_MODEL} readiness
          ON readiness.silver_job_id = silver.id
        WHERE {where}
        ORDER BY silver.id;
        """
    )
    rows = [dict(row) for row in cur.fetchall()]
    require(len(rows) == candidate_count, "PRODUCT_READ_MODEL_JOIN_CARDINALITY_DRIFT")
    return candidate_count, rows


def runtime_schema_proof(cur: psycopg.Cursor[Any]) -> dict[str, Any]:
    cur.execute(
        "SELECT to_regclass('public.silver_jobs') AS silver, "
        "to_regclass('public.gold_product_v1_job_readiness') AS product;"
    )
    relations = cur.fetchone()
    require(relations["silver"] is not None, "SILVER_JOBS_RELATION_MISSING")
    require(relations["product"] is not None, "PRODUCT_READ_MODEL_MISSING")

    cur.execute(
        """
        SELECT column_name, data_type, is_nullable, ordinal_position
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'silver_jobs'
          AND column_name IN ('id', 'source_name', 'source_url', 'canonical_source_type',
                              'raw_job_id', 'title', 'company_name', 'city', 'publication_date')
        ORDER BY ordinal_position;
        """
    )
    silver_columns = [dict(row) for row in cur.fetchall()]
    present = {str(row["column_name"]) for row in silver_columns}
    require(
        {
            "id",
            "source_name",
            "source_url",
            "canonical_source_type",
            "raw_job_id",
            "title",
            "company_name",
            "city",
            "publication_date",
        }.issubset(present),
        "SOURCE_ROLE_DIAGNOSTIC_SCHEMA_MISSING",
    )

    cur.execute(
        "SELECT pg_get_viewdef('public.gold_product_v1_job_readiness'::regclass, true) AS definition;"
    )
    view_definition = str(cur.fetchone()["definition"])
    return {
        "silver_columns_sha256": hashlib.sha256(canonical_json_bytes(silver_columns)).hexdigest(),
        "product_read_model_sha256": hashlib.sha256(view_definition.encode("utf-8")).hexdigest(),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    class_counts: dict[str, dict[str, int]] = {
        name: {"rows": 0, "absolute_http_valid": 0, "absolute_http_invalid": 0}
        for name in ("market_sensor", "employer_origin", "other_or_unknown")
    }
    class_sources: dict[str, set[str]] = {name: set() for name in class_counts}
    invalid_by_source: Counter[str] = Counter()
    employer_current = {
        "current_product_rows": 0,
        "non_current_product_rows": 0,
        "current_product_absolute_http_valid": 0,
        "current_product_absolute_http_invalid": 0,
    }

    for row in rows:
        role = architecture_class(row)
        source_name = str(row.get("source_name") or "").strip()
        valid = absolute_http(row.get("source_url"))
        class_counts[role]["rows"] += 1
        class_counts[role]["absolute_http_valid" if valid else "absolute_http_invalid"] += 1
        class_sources[role].add(source_name or "<blank>")
        if not valid:
            invalid_by_source[source_name or "<blank>"] += 1

        if role == "employer_origin":
            current = is_current_product_job(row)
            if current:
                employer_current["current_product_rows"] += 1
                employer_current[
                    "current_product_absolute_http_valid"
                    if valid
                    else "current_product_absolute_http_invalid"
                ] += 1
            else:
                employer_current["non_current_product_rows"] += 1

    for role, values in class_counts.items():
        values["source_count"] = len(class_sources[role])

    return {
        "architecture_classes": class_counts,
        "employer_origin_product_boundary": employer_current,
        "invalid_absolute_http_by_source_name": dict(sorted(invalid_by_source.items())),
    }


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_bytes(data)
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--repo-root", default=Path.cwd(), type=Path)
    args = parser.parse_args()

    manifest_sha256 = load_and_bind_manifest(args.manifest)
    classifier_bytes = (args.repo_root / CLASSIFIER_PATH).read_bytes()
    require(git_blob_sha(classifier_bytes) == CLASSIFIER_BLOB_SHA, "CLASSIFIER_BLOB_MISMATCH")

    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    config = get_database_config()
    required_db_keys = ("host", "port", "dbname", "user", "password")
    require(all(config.get(key) not in (None, "") for key in required_db_keys), "DATABASE_CONFIG_INCOMPLETE")
    config["application_name"] = "wbaa-m3-source-role-diagnostic"

    with psycopg.connect(**config, row_factory=dict_row) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SHOW transaction_read_only")
                read_only = str(cur.fetchone()["transaction_read_only"])
                require(read_only == "on", "TRANSACTION_NOT_READ_ONLY")
                cur.execute("SET LOCAL statement_timeout = '5min'")
                schema_proof = runtime_schema_proof(cur)
                candidate_count, rows = query_rows(cur)
        conn.rollback()

    aggregates = aggregate(rows)
    require(
        sum(group["rows"] for group in aggregates["architecture_classes"].values())
        == candidate_count,
        "ARCHITECTURE_CLASS_COUNT_MISMATCH",
    )
    completed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    evidence = {
        "evidence_version": "1.0",
        "mission": "M3_REAL_JAP_MIGRATION",
        "diagnostic": "source_role_product_boundary",
        "authority": {"kind": AUTHORITY_KIND, "reference": AUTHORITY_REFERENCE},
        "source_binding": {
            "repository": SOURCE_REPOSITORY,
            "source_sha": SOURCE_SHA,
            "candidate_relation": SOURCE_RELATION,
            "product_read_model": PRODUCT_READ_MODEL,
            "classifier_path": CLASSIFIER_PATH,
            "classifier_blob_sha": CLASSIFIER_BLOB_SHA,
        },
        "target_binding": {
            "repository": TARGET_REPOSITORY,
            "base_sha": TARGET_BASE,
            "pr": TARGET_PR,
            "candidate_sha": TARGET_CANDIDATE,
            "manifest_blob_sha": TARGET_MANIFEST_BLOB_SHA,
            "manifest_sha256": manifest_sha256,
        },
        "read": {
            "started_at": started_at,
            "completed_at": completed_at,
            "transaction_read_only": "on",
            "m3_current_predicate_row_count": candidate_count,
            "runtime_schema_proof": schema_proof,
        },
        "aggregates": aggregates,
        "effects": {
            "database_write": False,
            "source_activation": False,
            "connector_mutation": False,
            "provider_transport": False,
            "azure_effect": False,
            "target_mutation": False,
            "merge": False,
        },
    }
    payload = canonical_json_bytes(evidence)
    atomic_write(args.evidence_output, payload)

    classes = aggregates["architecture_classes"]
    boundary = aggregates["employer_origin_product_boundary"]
    print(
        "M3_SOURCE_ROLE_DIAGNOSTIC=PASS "
        f"selected={candidate_count} "
        f"sensor={classes['market_sensor']['rows']} "
        f"origin={classes['employer_origin']['rows']} "
        f"other={classes['other_or_unknown']['rows']} "
        f"sensor_invalid_url={classes['market_sensor']['absolute_http_invalid']} "
        f"origin_invalid_url={classes['employer_origin']['absolute_http_invalid']} "
        f"origin_current={boundary['current_product_rows']} "
        f"origin_current_invalid_url={boundary['current_product_absolute_http_invalid']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
