"""Host entry point: full Classic population -> generic proof -> activation -> Bronze.

Default is a read-only preflight. Execution is bound to an exact clean Git SHA.
RCC remains the only CI/workload runner authority; this command adds no scheduler.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess

import psycopg
from psycopg.rows import dict_row

from scripts import run_generic_employer_origin_product as product
from scripts import apply_generic_employer_origin_activation as activation
from src.config import get_database_config
from src.connectors.classic_factory_delivery import (
    DeliveryJournal, atomic_json, delivery_summary, fingerprint,
)
from src.ingest_jobs import run_profile
from src.ingestion.repository import JobIngestionRepository

ROOT = Path(__file__).resolve().parents[1]
LOCK_ID = 736103194  # dedicated, session-scoped factory orchestration lock
REQUIRED_RELATIONS = (
    "employer_origin_source_candidates", "generic_employer_origin_active_sources",
    "search_profiles", "search_terms", "ingestion_runs", "raw_jobs", "job_observations",
)


def source_sha(expected: str | None) -> str:
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if expected is not None:
        if expected != actual:
            raise ValueError("source_sha_mismatch")
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT, text=True,
        )
        if dirty.strip():
            raise ValueError("execution_requires_clean_checkout")
    return actual


@contextmanager
def database_session():
    config = get_database_config()
    if any(not config.get(key) for key in ("host", "dbname", "user")):
        raise RuntimeError("HOST_DATABASE_CONFIGURATION_MISSING")
    with psycopg.connect(**config, connect_timeout=10, row_factory=dict_row, autocommit=True) as conn:
        yield conn


def preflight(conn, sha: str) -> tuple[dict, list[dict]]:
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        missing = [name for name in REQUIRED_RELATIONS if not conn.execute(
            "SELECT to_regclass(%s) AS relation", ("public." + name,),
        ).fetchone()["relation"]]
        if missing:
            raise RuntimeError("HOST_SCHEMA_MISSING:" + ",".join(missing))
        candidates = product.layer_core._load_candidates(conn)
        if not candidates:
            raise ValueError("candidate_population_empty")
        identity = [{key: row[key] for key in ("id", "company_key", "candidate_url")}
                    for row in candidates]
        config = get_database_config()
        binding = {
            "source_sha": sha,
            "database": fingerprint({key: config[key] for key in ("host", "port", "dbname", "user")}),
            "population": fingerprint(identity),
        }
        # Preflight never performs source requests or changes activation.
        return {"binding": binding, "population_count": len(candidates),
                "database_writes": False, "source_requests": 0}, candidates


class ReceiptRepository(JobIngestionRepository):
    def __init__(self, journal: DeliveryJournal, stage: str):
        super().__init__()
        self.journal, self.stage, self.run_ids = journal, stage, []

    def create_ingestion_run(self, **kwargs):
        run_id = super().create_ingestion_run(**kwargs)
        self.run_ids.append(run_id)
        self.journal.data["stages"][self.stage]["ingestion_run_ids"] = self.run_ids
        self.journal.save(self.stage)
        return run_id


def ingest(company_key: str, journal: DeliveryJournal) -> dict:
    repository = ReceiptRepository(journal, "ingest:" + company_key)
    profile = repository.load_search_profile(activation.PROFILE_PREFIX + company_key)
    if profile.source_name != "generic_origin:" + company_key:
        raise ValueError("profile_source_identity_changed")
    run_profile(repository, profile, recurring_health_enabled=True)
    with repository.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, status, total_loaded, inserted_count, duplicate_count "
            "FROM ingestion_runs WHERE id = ANY(%s) ORDER BY id", (repository.run_ids,),
        )
        rows = cur.fetchall()
        if not rows or len(rows) != len(repository.run_ids) or any(row["status"] != "success" for row in rows):
            raise RuntimeError("ingestion_receipt_not_successful")
        cur.execute(
            "SELECT count(*) AS n FROM job_observations "
            "WHERE ingestion_run_id = ANY(%s) AND raw_job_id IS NOT NULL", (repository.run_ids,),
        )
        observations = int(cur.fetchone()["n"])
        loaded = sum(row["total_loaded"] for row in rows)
        if observations != loaded:
            raise RuntimeError("bronze_observation_receipt_mismatch")
        return {"ingestion_run_ids": repository.run_ids, "observed_jobs": observations,
                "inserted_jobs": sum(row["inserted_count"] for row in rows)}


def qualify(row: dict, args) -> dict:
    result = product.assess_candidate(row, args).to_json()
    if result.get("company_key") != row["company_key"] or result.get("candidate_id") != row["id"]:
        raise ValueError("factory_result_identity_mismatch")
    return result


def verify_activation(conn, rows: list[dict]) -> None:
    keys = [row["company_key"] for row in rows]
    count = conn.execute(
        "SELECT count(*) AS n FROM generic_employer_origin_active_sources a "
        "JOIN search_profiles p ON p.source_name = a.source_name "
        "WHERE a.company_key = ANY(%s) AND p.profile_name = 'generic_origin__' || a.company_key "
        "AND p.is_active AND p.recurring_ingestion_enabled AND a.proof_state = 'pass'",
        (keys,),
    ).fetchone()["n"]
    if count != len(keys):
        raise RuntimeError("activation_receipt_mismatch")


def execute(conn, candidates: list[dict], journal: DeliveryJournal, args) -> dict:
    product.layer_core.run_origin_discovery = product.run_origin_discovery
    product.layer_core.discover_navigation_candidates = product.discover_navigation_candidates
    results = []
    failures = []
    for row in candidates:
        try:
            results.append(journal.stage(
                "qualify:" + row["company_key"], lambda row=row: qualify(row, args), effect=False,
            ))
        except Exception:
            failures.append(row["company_key"])
    if failures:
        raise RuntimeError("FACTORY_QUALIFICATION_ERRORS")
    payload = {"authority": {"sole_connector_truth": activation.GENERIC_AUTHORITY,
                             "source_validity_gate": "proof=PASS"}, "results": results}
    atomic_json(args.state_dir / "proof.json", payload)
    rows = activation._proof_rows(payload)
    if not rows:
        raise RuntimeError("NO_QUALIFIED_SOURCES")

    def activate():
        with conn.transaction():
            origins = activation._resolve_projection_origins(conn, rows)
            activation.apply_activation(conn, rows, origins, preserve_existing=True)
            verify_activation(conn, rows)
        return {"qualified_sources": len(rows)}

    journal.stage("activate", activate, effect=True)
    for row in rows:
        key = row["company_key"]
        try:
            journal.stage("ingest:" + key, lambda key=key: ingest(key, journal), effect=True)
        except Exception:
            # Preserve ambiguous effects and continue the remaining admitted population.
            # No automatic retry, no silently successful zero-job conversion.
            continue
    summary = delivery_summary(journal.data["stages"], len(candidates))
    summary["qualified_sources"] = len(rows)
    summary["qualification_gaps"] = len(candidates) - len(rows)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--execute-sha", help="Explicit effect gate; exact clean checkout SHA")
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--origin-max-candidates", type=int, default=12,
                        help="URL discovery budget per company, never a population limit")
    parser.add_argument("--origin-timeout-seconds", type=float, default=5.0)
    parser.add_argument("--http-timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    report = {"schema": "jap.classic_factory_acceptance.v1", "e2e_accepted": False,
              "created_at": datetime.now(UTC).isoformat()}
    try:
        sha = source_sha(args.execute_sha)
        policy = json.loads((ROOT / "config/classic_connector_factory_policy.json").read_text())
        if policy.get("authorized") is not True or policy.get("scope") != "classic_full_population_job_delivery":
            raise ValueError("CLASSIC_FACTORY_NOT_AUTHORIZED")
        with database_session() as conn:
            # Lock also covers receipt files; separate invocations cannot replace receipts.
            locked = conn.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (LOCK_ID,)).fetchone()["acquired"]
            if not locked:
                raise RuntimeError("FACTORY_ALREADY_RUNNING")
            check, candidates = preflight(conn, sha)
            report["preflight"] = check
            if not args.execute_sha:
                report["status"] = "PREFLIGHT_READY"
            else:
                binding = dict(check["binding"], target_location=args.target_location,
                               origin_max_candidates=args.origin_max_candidates,
                               origin_timeout_seconds=args.origin_timeout_seconds,
                               http_timeout_seconds=args.http_timeout_seconds)
                journal = DeliveryJournal(args.state_dir / "receipt.json", binding)
                report.update(execute(conn, candidates, journal, args))
                report["status"] = "BRONZE_DELIVERED" if report["bronze_delivery_proven"] and not report["held_stages"] else "INCOMPLETE"
            atomic_json(args.state_dir / "acceptance.json", report)
    except Exception as exc:
        report.update(status="BLOCKED", error_type=type(exc).__name__)
        safe_codes = {
            "HOST_DATABASE_CONFIGURATION_MISSING", "FACTORY_ALREADY_RUNNING", "CLASSIC_FACTORY_NOT_AUTHORIZED",
            "FACTORY_QUALIFICATION_ERRORS", "NO_QUALIFIED_SOURCES",
            "source_sha_mismatch", "execution_requires_clean_checkout",
            "receipt_binding_changed", "candidate_population_empty",
        }
        report["error_code"] = str(exc) if str(exc) in safe_codes else "HOST_OR_EXECUTION_GATE"
        # Do not include exception text: database errors may contain credentials.
        print(json.dumps(report, sort_keys=True))
        # Unique failure file cannot overwrite a concurrent execution's acceptance.
        atomic_json(args.state_dir / ("blocked-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f") + ".json"), report)
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] in {"PREFLIGHT_READY", "BRONZE_DELIVERED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
