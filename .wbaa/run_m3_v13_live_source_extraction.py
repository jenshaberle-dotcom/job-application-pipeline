from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config

SOURCE_REPOSITORY = "jenshaberle-dotcom/job-application-pipeline"
SOURCE_SHA = "27a5e78fb3041eee1b1f3964676f62d1db82a067"
SOURCE_RELATION = "silver_jobs"
PRODUCT_READ_MODEL = "gold_product_v1_job_readiness"
TARGET_REPOSITORY = "jenshaberle-dotcom/jap-cloud-based"
TARGET_BASE = "034d234a58f01238299c08369ee095df4cfdeefc"
TARGET_PR = 31
TARGET_CANDIDATE = "1cf9acdaa8a38e8ecd62f4c7272ea59f33bbe657"
TARGET_QUALIFIER_RUN = 35210189584
TARGET_MANIFEST_BLOB_SHA = "b33b6064fce760a13f482ef890b818cca91a9a9c"
TARGET_SOURCE_QUERY_BLOB_SHA = "72c39aa08274a874a57685fbc95d1950e932e10f"
TARGET_EXPORT_BLOB_SHA = "486ce6ac8055147a200e02c1fcbb7c52d92ae98c"
TARGET_JOB_MODEL_BLOB_SHA = "983fc3d2eda1652af57a2b09ee901d61c1bbbe4c"
SOURCE_SCHEMA_BLOB_SHA = "3197adb4297190f2f96fcf2edc9c4fdb933734a2"
PRODUCT_SCHEMA_BLOB_SHA = "563821ef21beb6f371c90caa209be34807a67be1"
CLASSIFIER_BLOB_SHA = "d84d47d7175a16d116a44b1f561b3d7293a06c2a"
AUTHORITY_REFERENCE = "WBAA#134-comment-5712956258"
AUTHORITY_KIND = "WBAA_JAP_CLOUD_M3_V13_LIVE_SOURCE_EXTRACTION_AUTHORIZED_V1"

SELECTED_COLUMNS = (
    "raw_job_id",
    "source_name",
    "external_job_id",
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


def assert_blob(path: Path, expected: str, label: str) -> bytes:
    payload = path.read_bytes()
    require(git_blob_sha(payload) == expected, f"{label}_BLOB_MISMATCH")
    return payload


def load_target_contract(target_root: Path) -> tuple[dict[str, Any], bytes, Any, Any, Any]:
    manifest_path = target_root / "contracts/m3-job-migration-manifest.json"
    source_query_path = target_root / "src/jap_cloud/migration/source_query.py"
    export_path = target_root / "src/jap_cloud/migration/export.py"
    job_model_path = target_root / "src/jap_cloud/domain/models.py"

    manifest_bytes = assert_blob(
        manifest_path, TARGET_MANIFEST_BLOB_SHA, "TARGET_MANIFEST"
    )
    assert_blob(source_query_path, TARGET_SOURCE_QUERY_BLOB_SHA, "TARGET_SOURCE_QUERY")
    assert_blob(export_path, TARGET_EXPORT_BLOB_SHA, "TARGET_EXPORT")
    assert_blob(job_model_path, TARGET_JOB_MODEL_BLOB_SHA, "TARGET_JOB_MODEL")

    manifest = json.loads(manifest_bytes.decode("utf-8"))
    require(manifest.get("contract_version") == "1.3", "MANIFEST_VERSION_MISMATCH")
    require(manifest.get("mission") == "M3_REAL_JAP_MIGRATION", "MANIFEST_MISSION_MISMATCH")
    source = manifest.get("source") or {}
    target = manifest.get("target") or {}
    boundary = source.get("semantic_boundary") or {}
    require(source.get("repository") == SOURCE_REPOSITORY, "SOURCE_REPOSITORY_MISMATCH")
    require(source.get("source_sha") == SOURCE_SHA, "SOURCE_SHA_MISMATCH")
    require(source.get("relation") == SOURCE_RELATION, "SOURCE_RELATION_MISMATCH")
    require(tuple(source.get("selected_columns") or ()) == SELECTED_COLUMNS, "SELECTED_COLUMNS_MISMATCH")
    require(target.get("repository") == TARGET_REPOSITORY, "TARGET_REPOSITORY_MISMATCH")
    require(target.get("base_sha") == TARGET_BASE, "TARGET_BASE_MISMATCH")
    require(boundary.get("required_source_role") == "employer_origin", "SOURCE_ROLE_MISMATCH")
    require(boundary.get("required_lifecycle_status") == "active_confirmed", "LIFECYCLE_MISMATCH")
    require((boundary.get("product_read_model") or {}).get("relation") == PRODUCT_READ_MODEL, "PRODUCT_READ_MODEL_MISMATCH")

    target_src = str(target_root / "src")
    if target_src not in sys.path:
        sys.path.insert(0, target_src)

    from jap_cloud.migration.export import build_export_evidence, build_job_export
    from jap_cloud.migration.source_query import build_source_select_sql

    return manifest, manifest_bytes, build_source_select_sql, build_job_export, build_export_evidence


def runtime_schema_proof(cur: psycopg.Cursor[Any], repo_root: Path) -> tuple[str, dict[str, Any]]:
    assert_blob(
        repo_root / "db/migrations/003_silver_jobs_model.sql",
        SOURCE_SCHEMA_BLOB_SHA,
        "SOURCE_SCHEMA_AUTHORITY",
    )
    assert_blob(
        repo_root / "db/migrations/111_restore_pd051_threshold_and_create_affinity_authority.sql",
        PRODUCT_SCHEMA_BLOB_SHA,
        "PRODUCT_SCHEMA_AUTHORITY",
    )
    assert_blob(
        repo_root / "scripts/product_v1_job_presentation_runtime.py",
        CLASSIFIER_BLOB_SHA,
        "CLASSIFIER_AUTHORITY",
    )

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
          AND column_name IN (
            'id', 'raw_job_id', 'source_name', 'external_job_id', 'source_url',
            'title', 'company_name', 'city', 'publication_date', 'canonical_source_type'
          )
        ORDER BY ordinal_position;
        """
    )
    silver_columns = [dict(row) for row in cur.fetchall()]
    silver_present = {str(row["column_name"]) for row in silver_columns}
    require(
        {
            "id",
            "raw_job_id",
            "source_name",
            "external_job_id",
            "source_url",
            "title",
            "company_name",
            "city",
            "publication_date",
            "canonical_source_type",
        }.issubset(silver_present),
        "SILVER_SCHEMA_REQUIRED_COLUMN_MISSING",
    )

    cur.execute(
        """
        SELECT column_name, data_type, is_nullable, ordinal_position
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'gold_product_v1_job_readiness'
        ORDER BY ordinal_position;
        """
    )
    product_columns = [dict(row) for row in cur.fetchall()]
    product_present = {str(row["column_name"]) for row in product_columns}
    require(
        {"silver_job_id", "lifecycle_status", "canonical_source_type"}.issubset(product_present),
        "PRODUCT_READ_MODEL_REQUIRED_COLUMN_MISSING",
    )

    cur.execute(
        "SELECT pg_get_viewdef('public.gold_product_v1_job_readiness'::regclass, true) AS definition;"
    )
    product_definition = str(cur.fetchone()["definition"])

    cur.execute(
        """
        SELECT c.conname, c.contype, pg_get_constraintdef(c.oid) AS definition
        FROM pg_constraint c
        JOIN pg_class r ON r.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = r.relnamespace
        WHERE n.nspname = 'public' AND r.relname = 'silver_jobs'
        ORDER BY c.conname;
        """
    )
    constraints = [dict(row) for row in cur.fetchall()]
    definitions = [str(row["definition"]) for row in constraints]
    require(
        any("UNIQUE (raw_job_id)" in value for value in definitions),
        "RAW_JOB_ID_UNIQUE_CONSTRAINT_MISSING",
    )
    require(
        any("FOREIGN KEY (raw_job_id) REFERENCES raw_jobs(id)" in value for value in definitions),
        "RAW_JOB_ID_FOREIGN_KEY_MISSING",
    )

    schema_payload = {
        "silver_columns": silver_columns,
        "silver_constraints": constraints,
        "product_columns": product_columns,
        "product_view_definition": product_definition,
    }
    catalog_sha256 = hashlib.sha256(canonical_json_bytes(schema_payload)).hexdigest()
    product_view_sha256 = hashlib.sha256(product_definition.encode("utf-8")).hexdigest()
    revision = (
        f"catalog-sha256:{catalog_sha256};"
        f"product-read-model-sha256:{product_view_sha256};"
        f"source-schema-blob:{SOURCE_SCHEMA_BLOB_SHA};"
        f"product-schema-blob:{PRODUCT_SCHEMA_BLOB_SHA}"
    )
    return revision, {
        "catalog_sha256": catalog_sha256,
        "product_read_model_sha256": product_view_sha256,
        "source_schema_authority_blob_sha": SOURCE_SCHEMA_BLOB_SHA,
        "product_schema_authority_blob_sha": PRODUCT_SCHEMA_BLOB_SHA,
        "classifier_authority_blob_sha": CLASSIFIER_BLOB_SHA,
    }


def adapt_database_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    adapted: list[dict[str, Any]] = []
    for row in rows:
        require(set(row) == set(SELECTED_COLUMNS), "SOURCE_SCOPE_MISMATCH")
        converted = dict(row)
        value = converted["publication_date"]
        require(not isinstance(value, datetime), "PUBLICATION_DATE_UNEXPECTED_DATETIME")
        if isinstance(value, date):
            converted["publication_date"] = value.isoformat()
        elif isinstance(value, str):
            converted["publication_date"] = value
        else:
            raise RuntimeError("PUBLICATION_DATE_UNEXPECTED_TYPE")
        adapted.append(converted)
    return adapted


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temp.write_bytes(data)
    os.replace(temp, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--target-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--evidence-output", required=True, type=Path)
    args = parser.parse_args()

    require(args.output.resolve() != args.evidence_output.resolve(), "OUTPUT_PATH_COLLISION")
    manifest, manifest_bytes, build_source_select_sql, build_job_export, build_export_evidence = load_target_contract(args.target_root)
    source_sql = build_source_select_sql(manifest)
    source_query_sha256 = hashlib.sha256(source_sql.encode("utf-8")).hexdigest()
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    config = get_database_config()
    required_db_keys = ("host", "port", "dbname", "user", "password")
    require(
        all(config.get(key) not in (None, "") for key in required_db_keys),
        "DATABASE_CONFIG_INCOMPLETE",
    )
    config["application_name"] = "wbaa-m3-v13-live-source-extraction"

    conn = psycopg.connect(**config, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute("BEGIN READ ONLY")
            cur.execute("SHOW transaction_read_only")
            read_only = str(cur.fetchone()["transaction_read_only"])
            require(read_only == "on", "TRANSACTION_NOT_READ_ONLY")
            cur.execute("SET LOCAL statement_timeout = '5min'")
            schema_revision, schema_detail = runtime_schema_proof(cur, args.repo_root)
            cur.execute(source_sql)
            database_rows = [dict(row) for row in cur.fetchall()]
        conn.rollback()
    finally:
        conn.close()

    rows = adapt_database_rows(database_rows)
    result = build_job_export(rows, manifest=manifest)
    require(result.row_count == len(rows), "SELECTED_EXPORT_COUNT_MISMATCH")
    completed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    evidence = build_export_evidence(
        result,
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        source_database_schema_revision=schema_revision,
        extraction_started_at=started_at,
        extraction_completed_at=completed_at,
        data_origin="AUTHORIZED_SOURCE_EXPORT",
        authority_reference=AUTHORITY_REFERENCE,
    )
    evidence["authority"] = {
        "kind": AUTHORITY_KIND,
        "reference": AUTHORITY_REFERENCE,
        "single_use": True,
    }
    evidence["target_binding"] = {
        "repository": TARGET_REPOSITORY,
        "base_sha": TARGET_BASE,
        "pr": TARGET_PR,
        "candidate_sha": TARGET_CANDIDATE,
        "qualifier_run": TARGET_QUALIFIER_RUN,
        "manifest_blob_sha": TARGET_MANIFEST_BLOB_SHA,
        "source_query_blob_sha": TARGET_SOURCE_QUERY_BLOB_SHA,
        "export_blob_sha": TARGET_EXPORT_BLOB_SHA,
        "job_model_blob_sha": TARGET_JOB_MODEL_BLOB_SHA,
    }
    evidence["source"]["product_read_model"] = PRODUCT_READ_MODEL
    evidence["source"]["schema_detail"] = schema_detail
    evidence["extraction"].update(
        {
            "transaction_read_only": read_only,
            "selected_columns": list(SELECTED_COLUMNS),
            "semantic_role": "employer_origin",
            "semantic_lifecycle": "active_confirmed",
            "source_query_sha256": source_query_sha256,
            "database_rows_selected": len(database_rows),
        }
    )
    evidence["effects"].update(
        {
            "database_write": False,
            "source_repair": False,
            "provider_transport": False,
            "azure_effect": False,
            "runtime_activation": False,
            "region_change": False,
            "target_mutation": False,
            "merge": False,
        }
    )

    evidence_bytes = (
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    atomic_write(args.output, result.artifact)
    atomic_write(args.evidence_output, evidence_bytes)

    print(
        "M3_V13_LIVE_SOURCE_EXTRACTION=PASS "
        f"rows={result.row_count} sha256={result.sha256} "
        f"read_only={read_only} authority={AUTHORITY_REFERENCE}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
