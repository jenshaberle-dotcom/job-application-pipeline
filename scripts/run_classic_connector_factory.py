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


def preflight(conn, sha: str, delivery_scope: str = 'active') -> tuple[dict, list[dict]]:
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        missing = [name for name in REQUIRED_RELATIONS if not conn.execute(
            "SELECT to_regclass(%s) AS relation", ("public." + name,),
        ).fetchone()["relation"]]
        if missing:
            raise RuntimeError("HOST_SCHEMA_MISSING:" + ",".join(missing))
        candidates = product.layer_core._load_candidates(conn)
        if delivery_scope == 'active':
            active = {row['company_key'] for row in conn.execute(
                "SELECT a.company_key FROM generic_employer_origin_active_sources a "
                "JOIN search_profiles p ON p.source_name=a.source_name "
                "WHERE a.proof_state='pass' AND p.is_active AND p.recurring_ingestion_enabled"
            ).fetchall()}
            candidates = [row for row in candidates if row['company_key'] in active]
        elif delivery_scope != 'full':
            raise ValueError('unknown_delivery_scope')
        if not candidates:
            raise ValueError("candidate_population_empty")
        identity = [{key: row[key] for key in ("id", "company_key", "candidate_url")}
                    for row in candidates]
        config = get_database_config()
        binding = {
            "source_sha": sha,
            "database": fingerprint({key: config[key] for key in ("host", "port", "dbname", "user")}),
            "population": fingerprint(identity),
            "delivery_scope": delivery_scope,
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
    terms = repository.load_active_search_terms(profile.profile_name)
    if len(terms) != 1 or terms[0][1].search_term != "*" or terms[0][0].id != profile.id:
        raise ValueError("canonical_ingestion_term_changed")
    expected = {"profile_id": profile.id, "term_ids": [terms[0][1].id]}
    journal.data["stages"][repository.stage]["expected_ingestion"] = expected
    journal.save(repository.stage)
    run_profile(repository, profile, recurring_health_enabled=True)
    with repository.get_connection() as conn:
        result = verify_ingestion_receipt(conn, repository.run_ids, company_key, expected)
        from src.connectors.generic_employer_origin_product import BROAD_INVENTORY_REPORTS
        result["inventory_coverage"] = BROAD_INVENTORY_REPORTS.get(profile.source_name)
        return result


def verify_ingestion_receipt(conn, run_ids: list[int], company_key: str, expected: dict) -> dict:
    """Read exact run/source/profile and physical job lineage; never infer from totals alone."""
    if not run_ids or any(type(value) is not int or value <= 0 for value in run_ids) or len(set(run_ids)) != len(run_ids):
        raise ValueError("ingestion_run_identity_missing_or_invalid")
    term_ids = expected.get("term_ids", [])
    if len(term_ids) != 1 or type(term_ids[0]) is not int or term_ids[0] <= 0 or type(expected.get("profile_id")) is not int:
        raise ValueError("expected_ingestion_identity_missing")
    source = "generic_origin:" + company_key
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT r.id, r.status, r.finished_at, r.total_loaded, r.inserted_count, r.duplicate_count, "
            "r.source_name, r.search_profile_id, r.search_term_id, r.search_term, p.profile_name FROM ingestion_runs r "
            "JOIN search_profiles p ON p.id = r.search_profile_id "
            "WHERE r.id = ANY(%s) ORDER BY r.id", (run_ids,),
        )
        rows = cur.fetchall()
        if len(rows) != len(term_ids) or {row["search_term_id"] for row in rows} != set(term_ids) or {row["id"] for row in rows} != set(run_ids) or any(
            row["status"] != "success" or row["finished_at"] is None
            or row["source_name"] != source
            or row["search_profile_id"] != expected["profile_id"] or row["search_term"] != "*"
            or row["profile_name"] != activation.PROFILE_PREFIX + company_key
            for row in rows
        ):
            raise RuntimeError("ingestion_receipt_not_successful_or_wrong_identity")
        for row in rows:
            counts = [row[name] for name in ("total_loaded", "inserted_count", "duplicate_count")]
            if any(type(value) is not int or value < 0 for value in counts) or counts[0] != counts[1] + counts[2]:
                raise RuntimeError("ingestion_counter_mismatch")
        cur.execute(
            "SELECT o.ingestion_run_id, count(*) AS observations, "
            "count(*) FILTER (WHERE o.is_seen AND o.source_name = %s "
            "AND j.source_name = o.source_name AND j.external_job_id = o.external_job_id) AS verified "
            "FROM job_observations o LEFT JOIN raw_jobs j ON j.id = o.raw_job_id "
            "WHERE o.ingestion_run_id = ANY(%s) GROUP BY o.ingestion_run_id", (source, run_ids),
        )
        observed = {row["ingestion_run_id"]: row for row in cur.fetchall()}
        for row in rows:
            evidence = observed.get(row["id"], {"observations": 0, "verified": 0})
            if evidence["observations"] != row["total_loaded"] or evidence["verified"] != row["total_loaded"]:
                raise RuntimeError("bronze_observation_receipt_mismatch")
        return {"ingestion_run_ids": run_ids,
                "observed_jobs": sum(row["total_loaded"] for row in rows),
                "inserted_jobs": sum(row["inserted_count"] for row in rows)}


def reconcile_ingestion(conn, journal: DeliveryJournal) -> dict:
    resolved, unresolved = [], []
    with conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        for key, stage in journal.data["stages"].items():
            if stage.get("state") not in {"RUNNING", "HELD"} or not stage.get("effect"):
                continue
            if not key.startswith("ingest:"):
                unresolved.append(key)
                continue
            try:
                result = verify_ingestion_receipt(
                    conn, stage.get("ingestion_run_ids", []), key.removeprefix("ingest:"),
                    stage.get("expected_ingestion", {}),
                )
            except (ValueError, RuntimeError):
                unresolved.append(key)
                continue
            stage["reconciliation"] = {
                "previous_state": stage["state"],
                "verified_at": datetime.now(UTC).isoformat(),
                "method": "exact_database_run_and_observation_lineage",
                "database_writes": False, "source_requests": 0,
            }
            stage.update(state="SUCCEEDED", result=result)
            journal.save(key)
            resolved.append(key)
    return {"resolved_stages": resolved, "unresolved_stages": unresolved,
            "database_writes": False, "source_requests": 0}


def qualify(row: dict, args) -> dict:
    result = product.assess_candidate(row, args).to_json()
    if result.get("company_key") != row["company_key"] or result.get("candidate_id") != row["id"]:
        raise ValueError("factory_result_identity_mismatch")
    return result


def promote_silver(company_key: str) -> dict:
    """Only the freshly admitted employer's backlog; no repeat source requests."""
    from src.run_silver_jobs import main as silver_main
    from contextlib import redirect_stdout
    import io
    counts = dict(selected=0, included=0, skipped=0)
    for _ in range(100):
        with redirect_stdout(io.StringIO()):
            batch = silver_main(['--source', 'generic_origin:' + company_key, '--limit', '500', '--broad-corpus'])
        for key in counts:
            counts[key] += batch[key]
        if batch['selected'] < 500:
            return dict(counts, source='generic_origin:' + company_key, completed=True)
    raise RuntimeError('SILVER_BACKLOG_NOT_DRAINED')


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


def execute(conn, candidates: list[dict], journal: DeliveryJournal, args, *, qualifier=None, quality_sources=None) -> dict:
    __import__("os").environ["JAP_BROAD_CORPUS"] = "1"
    product.layer_core.run_origin_discovery = product.run_origin_discovery
    product.layer_core.discover_navigation_candidates = product.discover_navigation_candidates
    results = []
    qualified_rows = []
    failures = []
    for row in candidates:
        try:
            result = journal.stage(
                "qualify:" + row["company_key"], lambda row=row: (qualifier or qualify)(row, args), effect=False,
            )
            results.append(result)
        except Exception:
            failures.append(row["company_key"])
            continue
        payload = {"authority": {"sole_connector_truth": activation.GENERIC_AUTHORITY,
                                 "source_validity_gate": "proof=PASS"}, "results": [result]}
        rows = activation._proof_rows(payload)
        if not rows:
            continue
        qualified_rows.extend(rows)
        key = row['company_key']

        def activate(rows=rows):
            with conn.transaction():
                origins = activation._resolve_projection_origins(conn, rows)
                activation.apply_activation(conn, rows, origins, preserve_existing=True)
                verify_activation(conn, rows)
            return {"qualified_sources": len(rows)}

        try:
            # Deliver each proven employer before exploring the next candidate.
            # Separate durable keys preserve no-replay semantics for every effect.
            journal.stage("activate:" + key, activate, effect=True)
            journal.stage("ingest:" + key, lambda key=key: ingest(key, journal), effect=True)
            journal.stage("silver:" + key, lambda key=key: promote_silver(key), effect=True)
        except Exception:
            # Preserve ambiguous effects and continue the remaining admitted population.
            # No automatic retry, no silently successful zero-job conversion.
            continue
    # Independent of ingestion success: existing approved vacancies also need a
    # current check when a source import failed or delivered no new rows.
    from scripts.product_v1_delivery_quality import maintain_source
    from scripts.run_product_v1_assessment_materialization import authorized_recurring_employer_origin_sources
    quality_results = []
    authorized = authorized_recurring_employer_origin_sources(JobIngestionRepository())
    for source in sorted(authorized if quality_sources is None else authorized.intersection(quality_sources)):
        key = source.removeprefix('generic_origin:')
        if source.startswith('generic_origin:'):
            try:
                journal.stage('silver:' + key, lambda key=key: promote_silver(key), effect=True)
            except Exception:
                pass  # A held stage stays held; never replay an ambiguous write.
        quality = maintain_source(source, journal)
        quality_results.append(quality)
        atomic_json(args.state_dir / ('quality-' + fingerprint(source) + '.json'), quality)
    atomic_json(args.state_dir / "proof.json", {
        "authority": {"sole_connector_truth": activation.GENERIC_AUTHORITY,
                      "source_validity_gate": "proof=PASS"}, "results": results,
    })
    summary = delivery_summary(journal.data["stages"], len(candidates))
    summary['inventory_coverage'] = {k.removeprefix('ingest:'): v['result'].get('inventory_coverage')
        for k,v in journal.data['stages'].items() if k.startswith('ingest:') and v.get('state') == 'SUCCEEDED'}
    summary['corpus_mode'] = 'broad_inventory_without_personal_filters'
    summary['quality_checked'] = sum(r['checked'] for r in quality_results)
    summary['quality_scored'] = sum(r['scored'] for r in quality_results)
    summary['quality_unavailable'] = sum(r['unavailable'] for r in quality_results)
    summary['quality_blocked'] = sum(len(r['blocked']) for r in quality_results)
    summary["qualified_sources"] = len(qualified_rows)
    summary["qualification_gaps"] = len(candidates) - len(qualified_rows)
    summary["qualification_errors"] = failures
    silver = [v['result'] for k,v in journal.data['stages'].items()
              if k.startswith('silver:') and v.get('state') == 'SUCCEEDED']
    summary['silver_sources_completed'] = len(silver)
    summary['silver_selected'] = sum(v['selected'] for v in silver)
    summary['silver_included'] = sum(v['included'] for v in silver)
    summary['silver_skipped'] = sum(v['skipped'] for v in silver)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--reconcile-sha", help="Exact clean SHA; reconcile held ingestion from read-only DB evidence")
    parser.add_argument("--execute-sha", help="Explicit effect gate; exact clean checkout SHA")
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument('--delivery-scope', choices=('active', 'full'), default='active',
                        help='Routine delivery refreshes approved sources; a full discovery campaign must be explicit.')
    parser.add_argument("--origin-max-candidates", type=int, default=12,
                        help="URL discovery budget per company, never a population limit")
    parser.add_argument("--origin-timeout-seconds", type=float, default=5.0)
    parser.add_argument("--http-timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    report = {"schema": "jap.classic_factory_acceptance.v1", "e2e_accepted": False,
              "created_at": datetime.now(UTC).isoformat()}
    try:
        if args.execute_sha and args.reconcile_sha:
            raise ValueError("choose_execution_or_reconciliation")
        sha = source_sha(args.execute_sha or args.reconcile_sha)
        policy = json.loads((ROOT / "config/classic_connector_factory_policy.json").read_text())
        if policy.get("authorized") is not True or policy.get("scope") != "classic_full_population_job_delivery":
            raise ValueError("CLASSIC_FACTORY_NOT_AUTHORIZED")
        with database_session() as conn:
            # Lock also covers receipt files; separate invocations cannot replace receipts.
            locked = conn.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (LOCK_ID,)).fetchone()["acquired"]
            if not locked:
                raise RuntimeError("FACTORY_ALREADY_RUNNING")
            check, candidates = preflight(conn, sha, args.delivery_scope)
            report["preflight"] = check
            if not args.execute_sha and not args.reconcile_sha:
                report["status"] = "PREFLIGHT_READY"
            else:
                binding = dict(check["binding"], target_location=args.target_location,
                               origin_max_candidates=args.origin_max_candidates,
                               origin_timeout_seconds=args.origin_timeout_seconds,
                               http_timeout_seconds=args.http_timeout_seconds)
                journal = DeliveryJournal(args.state_dir / "receipt.json", binding)
                if args.reconcile_sha:
                    if not journal.path.exists():
                        raise ValueError("reconciliation_receipt_missing")
                    report["reconciliation"] = reconcile_ingestion(conn, journal)
                    report["status"] = "RECONCILED" if not report["reconciliation"]["unresolved_stages"] else "INCOMPLETE"
                else:
                    report.update(execute(conn, candidates, journal, args))
                    report["status"] = "BRONZE_DELIVERED" if report["bronze_delivery_proven"] and not report["held_stages"] and not report["qualification_errors"] else "INCOMPLETE"
            report_file = "reconciliation.json" if args.reconcile_sha else (
                "acceptance.json" if args.execute_sha else "preflight.json"
            )
            atomic_json(args.state_dir / report_file, report)
    except Exception as exc:
        report.update(status="BLOCKED", error_type=type(exc).__name__)
        safe_codes = {
            "HOST_DATABASE_CONFIGURATION_MISSING", "FACTORY_ALREADY_RUNNING", "CLASSIC_FACTORY_NOT_AUTHORIZED",
            "FACTORY_QUALIFICATION_ERRORS", "NO_QUALIFIED_SOURCES",
            "source_sha_mismatch", "execution_requires_clean_checkout",
            "receipt_binding_changed", "candidate_population_empty",
            "choose_execution_or_reconciliation", "reconciliation_receipt_missing",
        }
        report["error_code"] = str(exc) if str(exc) in safe_codes else "HOST_OR_EXECUTION_GATE"
        # Do not include exception text: database errors may contain credentials.
        print(json.dumps(report, sort_keys=True))
        # Unique failure file cannot overwrite a concurrent execution's acceptance.
        atomic_json(args.state_dir / ("blocked-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f") + ".json"), report)
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] in {"PREFLIGHT_READY", "BRONZE_DELIVERED", "RECONCILED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
