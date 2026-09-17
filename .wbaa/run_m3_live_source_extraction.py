from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config

SOURCE_REPOSITORY = "jenshaberle-dotcom/job-application-pipeline"
SOURCE_SHA = "27a5e78fb3041eee1b1f3964676f62d1db82a067"
SOURCE_RELATION = "silver_jobs"
TARGET_REPOSITORY = "jenshaberle-dotcom/jap-cloud-based"
TARGET_BASE = "034d234a58f01238299c08369ee095df4cfdeefc"
TARGET_PR = 31
TARGET_CANDIDATE = "e03df393f7de9354b4c37cd33711bd3e04a0879f"
TARGET_MANIFEST_BLOB_SHA = "cf303e5e63c337da1a25fcb896183f1191c5ca23"
AUTHORITY_REFERENCE = "WBAA#134-comment-5711751027"
AUTHORITY_KIND = "WBAA_JAP_CLOUD_M3_LIVE_SOURCE_EXTRACTION_AUTHORIZED_V1"

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
REQUIRED_NON_NULL = (
    "raw_job_id",
    "source_name",
    "source_url",
    "title",
    "company_name",
    "city",
    "publication_date",
)
ROW_ORDER = (
    "publication_date DESC",
    "source_name ASC",
    "external_job_id ASC NULLS LAST",
    "raw_job_id ASC",
)
TARGET_FIELDS = (
    "job_id",
    "title",
    "employer",
    "location",
    "posted_at",
    "source_url",
)
INVARIANTS = (
    "scope_columns_exact",
    "job_id_unique",
    "required_text_non_empty",
    "source_url_absolute_http",
    "posted_at_date_precision",
    "source_traceable",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def load_manifest(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    require(git_blob_sha(raw) == TARGET_MANIFEST_BLOB_SHA, "TARGET_MANIFEST_BLOB_MISMATCH")
    manifest = json.loads(raw.decode("utf-8"))
    require(manifest.get("contract_version") == "1.2", "MANIFEST_VERSION_MISMATCH")
    require(manifest.get("mission") == "M3_REAL_JAP_MIGRATION", "MANIFEST_MISSION_MISMATCH")
    source = manifest.get("source") or {}
    target = manifest.get("target") or {}
    eligibility = manifest.get("eligibility") or {}
    export_contract = manifest.get("export_contract") or {}
    require(source.get("repository") == SOURCE_REPOSITORY, "SOURCE_REPOSITORY_MISMATCH")
    require(source.get("source_sha") == SOURCE_SHA, "SOURCE_SHA_MISMATCH")
    require(source.get("relation") == SOURCE_RELATION, "SOURCE_RELATION_MISMATCH")
    require(tuple(source.get("selected_columns") or ()) == SELECTED_COLUMNS, "SELECTED_COLUMNS_MISMATCH")
    require(tuple(eligibility.get("required_non_null_source_columns") or ()) == REQUIRED_NON_NULL, "NON_NULL_CONTRACT_MISMATCH")
    require(tuple(eligibility.get("row_order") or ()) == ROW_ORDER, "ROW_ORDER_MISMATCH")
    require(target.get("repository") == TARGET_REPOSITORY, "TARGET_REPOSITORY_MISMATCH")
    require(target.get("base_sha") == TARGET_BASE, "TARGET_BASE_MISMATCH")
    require(tuple(target.get("fields") or ()) == TARGET_FIELDS, "TARGET_FIELDS_MISMATCH")
    require(export_contract.get("format") == "ndjson", "EXPORT_FORMAT_MISMATCH")
    require(export_contract.get("encoding") == "utf-8", "EXPORT_ENCODING_MISMATCH")
    require(export_contract.get("line_ending") == "LF", "EXPORT_LINE_ENDING_MISMATCH")
    require(export_contract.get("checksum") == "sha256", "EXPORT_CHECKSUM_MISMATCH")
    require(tuple(export_contract.get("field_order") or ()) == TARGET_FIELDS, "EXPORT_FIELD_ORDER_MISMATCH")
    return manifest, raw


def build_source_sql() -> str:
    selected = ",\n    ".join(SELECTED_COLUMNS)
    predicates = "\n  AND ".join(f"{column} IS NOT NULL" for column in REQUIRED_NON_NULL)
    order_by = ",\n    ".join(ROW_ORDER)
    return (
        "SELECT\n"
        f"    {selected}\n"
        f"FROM {SOURCE_RELATION}\n"
        f"WHERE {predicates}\n"
        "ORDER BY\n"
        f"    {order_by};\n"
    )


def required_text(value: Any, field: str) -> str:
    require(isinstance(value, str), f"{field}_NOT_TEXT")
    normalized = value.strip()
    require(bool(normalized), f"{field}_EMPTY_AFTER_TRIM")
    return normalized


def optional_external_id(value: Any) -> str | None:
    if value is None:
        return None
    require(isinstance(value, str), "external_job_id_NOT_TEXT_OR_NULL")
    normalized = value.strip()
    return normalized or None


def canonical_date(value: Any) -> str:
    if isinstance(value, datetime):
        raise RuntimeError("publication_date_HAS_INVENTED_TIME_PRECISION")
    if isinstance(value, date):
        return value.isoformat()
    require(isinstance(value, str), "publication_date_NOT_DATE")
    parsed = date.fromisoformat(value)
    canonical = parsed.isoformat()
    require(value == canonical, "publication_date_NOT_CANONICAL")
    return canonical


def absolute_http_url(value: Any) -> str:
    normalized = required_text(value, "source_url")
    parsed = urlsplit(normalized)
    require(parsed.scheme in {"http", "https"} and bool(parsed.netloc), "source_url_NOT_ABSOLUTE_HTTP")
    return normalized


def normalize_source_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    require(set(row) == set(SELECTED_COLUMNS), f"ROW_{index}_SOURCE_SCOPE_MISMATCH")
    raw_job_id = row["raw_job_id"]
    require(isinstance(raw_job_id, int) and not isinstance(raw_job_id, bool) and raw_job_id > 0, "raw_job_id_INVALID")
    return {
        "raw_job_id": raw_job_id,
        "source_name": required_text(row["source_name"], "source_name"),
        "external_job_id": optional_external_id(row["external_job_id"]),
        "source_url": absolute_http_url(row["source_url"]),
        "title": required_text(row["title"], "title"),
        "company_name": required_text(row["company_name"], "company_name"),
        "city": required_text(row["city"], "city"),
        "publication_date": canonical_date(row["publication_date"]),
    }


def source_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    external = row["external_job_id"]
    external_key = (1, "") if external is None else (0, external)
    return (-date.fromisoformat(row["publication_date"]).toordinal(), row["source_name"], external_key, row["raw_job_id"])


def build_export(rows: list[dict[str, Any]]) -> tuple[bytes, str]:
    require(bool(rows), "EXPORT_EMPTY")
    normalized = [normalize_source_row(row, index) for index, row in enumerate(rows, start=1)]
    normalized.sort(key=source_sort_key)
    jobs: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in normalized:
        external = row["external_job_id"]
        job_id = f"{row['source_name']}:{external}" if external is not None else f"{row['source_name']}:raw-{row['raw_job_id']}"
        require(job_id not in seen, "DUPLICATE_JOB_ID")
        seen.add(job_id)
        jobs.append(
            {
                "job_id": job_id,
                "title": row["title"],
                "employer": row["company_name"],
                "location": row["city"],
                "posted_at": row["publication_date"],
                "source_url": row["source_url"],
            }
        )
    lines = [json.dumps(job, ensure_ascii=False, separators=(",", ":"), sort_keys=False) for job in jobs]
    artifact = ("\n".join(lines) + "\n").encode("utf-8")
    return artifact, hashlib.sha256(artifact).hexdigest()


def schema_proof(cur: psycopg.Cursor[Any], manifest: dict[str, Any], repo_root: Path) -> tuple[str, dict[str, Any]]:
    cur.execute(
        """
        SELECT column_name, data_type, is_nullable, ordinal_position
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'silver_jobs'
        ORDER BY ordinal_position;
        """
    )
    columns = [dict(row) for row in cur.fetchall()]
    by_name = {row["column_name"]: row for row in columns}
    for name in SELECTED_COLUMNS:
        require(name in by_name, f"SOURCE_COLUMN_MISSING:{name}")
    require(by_name["raw_job_id"]["is_nullable"] == "NO", "raw_job_id_SCHEMA_NULLABLE")

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
    require(any("UNIQUE (raw_job_id)" in value for value in definitions), "RAW_JOB_ID_UNIQUE_CONSTRAINT_MISSING")
    require(any("FOREIGN KEY (raw_job_id) REFERENCES raw_jobs(id)" in value for value in definitions), "RAW_JOB_ID_FOREIGN_KEY_MISSING")

    authority = manifest["source"]["relation_schema_authority"]
    migration_path = repo_root / authority["path"]
    migration_bytes = migration_path.read_bytes()
    require(git_blob_sha(migration_bytes) == authority["blob_sha"], "RELATION_SCHEMA_AUTHORITY_BLOB_MISMATCH")
    migration_sha256 = hashlib.sha256(migration_bytes).hexdigest()

    catalog_payload = {"columns": columns, "constraints": constraints}
    catalog_sha256 = hashlib.sha256(canonical_json_bytes(catalog_payload)).hexdigest()

    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'schema_migrations'
        ) AS exists;
        """
    )
    tracking_exists = bool(cur.fetchone()["exists"])
    tracked: list[dict[str, Any]] = []
    tracking_sha256: str | None = None
    max_version: int | None = None
    if tracking_exists:
        cur.execute(
            """
            SELECT migration_key, version_number, filename, checksum_sha256, execution_status, execution_mode
            FROM schema_migrations
            ORDER BY version_number, filename;
            """
        )
        tracked = [dict(row) for row in cur.fetchall()]
        tracking_sha256 = hashlib.sha256(canonical_json_bytes(tracked)).hexdigest()
        versions = [int(row["version_number"]) for row in tracked]
        max_version = max(versions) if versions else None
        authority_rows = [row for row in tracked if row["migration_key"] == Path(authority["path"]).name]
        if authority_rows:
            require(len(authority_rows) == 1, "RELATION_SCHEMA_TRACKING_DUPLICATE")
            require(authority_rows[0]["checksum_sha256"] == migration_sha256, "RELATION_SCHEMA_TRACKED_CHECKSUM_MISMATCH")

    revision_parts = [f"catalog-sha256:{catalog_sha256}"]
    if tracking_sha256 is None:
        revision_parts.append("schema-migrations:absent")
    else:
        revision_parts.append(f"schema-migrations-sha256:{tracking_sha256}")
        revision_parts.append(f"schema-migrations-count:{len(tracked)}")
        revision_parts.append(f"schema-migrations-max-version:{max_version}")
    revision = ";".join(revision_parts)
    return revision, {
        "catalog_sha256": catalog_sha256,
        "tracked_migrations_sha256": tracking_sha256,
        "tracked_migration_count": len(tracked),
        "tracked_migration_max_version": max_version,
        "relation_schema_authority_blob_sha": authority["blob_sha"],
        "relation_schema_authority_sha256": migration_sha256,
    }


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_bytes(data)
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--repo-root", default=Path.cwd(), type=Path)
    args = parser.parse_args()

    manifest, manifest_bytes = load_manifest(args.manifest)
    require(args.output.resolve() != args.evidence_output.resolve(), "OUTPUT_PATH_COLLISION")
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    config = get_database_config()
    required_db_keys = ("host", "port", "dbname", "user", "password")
    require(all(config.get(key) not in (None, "") for key in required_db_keys), "DATABASE_CONFIG_INCOMPLETE")
    config["application_name"] = "wbaa-m3-live-source-extraction"

    with psycopg.connect(**config, row_factory=dict_row) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SHOW transaction_read_only")
                read_only = str(cur.fetchone()["transaction_read_only"])
                require(read_only == "on", "TRANSACTION_NOT_READ_ONLY")
                cur.execute("SET LOCAL statement_timeout = '5min'")
                schema_revision, schema_detail = schema_proof(cur, manifest, args.repo_root)
                cur.execute(build_source_sql())
                rows = [dict(row) for row in cur.fetchall()]

    artifact, artifact_sha256 = build_export(rows)
    completed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    invariants = {key: "PASS" for key in INVARIANTS}
    evidence = {
        "evidence_version": "1.0",
        "mission": "M3_REAL_JAP_MIGRATION",
        "data_origin": "AUTHORIZED_SOURCE_EXPORT",
        "authority": {"kind": AUTHORITY_KIND, "reference": AUTHORITY_REFERENCE},
        "source": {
            "repository": SOURCE_REPOSITORY,
            "source_sha": SOURCE_SHA,
            "relation": SOURCE_RELATION,
            "database_schema_revision": schema_revision,
            "schema_detail": schema_detail,
        },
        "target_binding": {
            "repository": TARGET_REPOSITORY,
            "base_sha": TARGET_BASE,
            "pr": TARGET_PR,
            "candidate_sha": TARGET_CANDIDATE,
        },
        "extraction": {
            "started_at": started_at,
            "completed_at": completed_at,
            "transaction_read_only": "on",
            "selected_columns": list(SELECTED_COLUMNS),
            "selected_source_rows": len(rows),
            "source_write_performed": False,
        },
        "migration_manifest": {
            "contract_version": manifest["contract_version"],
            "git_blob_sha": TARGET_MANIFEST_BLOB_SHA,
            "sha256": manifest_sha256,
        },
        "export": {
            "format": "ndjson",
            "encoding": "utf-8",
            "checksum": "sha256",
            "artifact_sha256": artifact_sha256,
            "selected_row_count": len(rows),
            "pre_import_invariant_results": invariants,
        },
        "effects": {
            "source_write_performed": False,
            "provider_transport_performed": False,
            "azure_import_performed": False,
            "azure_effect_performed": False,
            "application_data_mode_changed": False,
            "merge_performed": False,
        },
    }
    require(len(rows) > 0, "SELECTED_ROW_COUNT_NOT_POSITIVE")
    require(evidence["export"]["selected_row_count"] == evidence["extraction"]["selected_source_rows"], "COUNT_MISMATCH")
    atomic_write(args.output, artifact)
    atomic_write(args.evidence_output, (json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(f"M3_LIVE_SOURCE_EXTRACTION=PASS rows={len(rows)} sha256={artifact_sha256} schema_revision={schema_revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
