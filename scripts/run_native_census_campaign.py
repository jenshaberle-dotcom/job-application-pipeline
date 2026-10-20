"""Pinned RCC recipe: whole Census to Bronze, then bounded factory diagnosis batches.

No new scheduler, source activation or blind replay. Each RCC workload has one
fixed purpose and all business outcomes are retained, including technical gaps.
"""
import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import ssl
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import psycopg
from psycopg.types.json import Jsonb

from src.config import get_database_config
from src.connectors.classic_factory_delivery import atomic_json
from src.search_intelligence.native_census import BATCH_SIZE, digest, population

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ("hochschule_hannover_career_center", "hannover", []),
    ("munich_startup", "munich", []),
    ("region_stuttgart_technology_directory", "stuttgart", []),
    ("berlin_startup_map", "configured_directory", ["--config", "config/census/berlin-startup-map.json"]),
    ("wolfsburg_innovation_ecosystem", "configured_directory", ["--config", "config/census/wolfsburg-innovations.json"]),
    ("ingolstadt_digital_ecosystem", "brigk", []),
)

class Progress:
    """Atomic, bounded progress evidence; heartbeat is separate from useful progress."""
    def __init__(self, state):
        self.path = state / "native-progress.json"
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.data = {"phase": "STARTING", "completed": 0, "total": 0,
                     "started_at": time.time(), "last_progress_at": time.time()}
        self.thread = threading.Thread(target=self.heartbeat, daemon=True)

    def update(self, **changes):
        with self.lock:
            self.data.update(changes, last_progress_at=time.time())
            self.write()

    def write(self):
        atomic_json(self.path, dict(self.data, updated_at=time.time()))

    def heartbeat(self):
        while not self.stop.wait(5):
            with self.lock:
                self.write()

    def __enter__(self):
        self.update()
        self.thread.start()
        return self

    def __exit__(self, kind, error, traceback):
        self.stop.set()
        self.thread.join(timeout=6)
        if kind:
            self.update(phase="FAILED", error_code=type(error).__name__)


def update(progress, **values):
    if progress:
        progress.update(**values)


def source_error(log):
    text = log.read_bytes()[-16000:].decode(errors="replace") if log.exists() else ""
    if "CERTIFICATE_VERIFY_FAILED" in text:
        return "TLS_CERTIFICATE_INVALID"
    if "HTTP Error 403" in text:
        return "HTTP_ACCESS_DENIED"
    if "timed out" in text:
        return "SOURCE_TIMEOUT"
    return "SOURCE_PROCESS_FAILED"


def verify_tls():
    """HEAD probes verify the real urllib path and hostname; no Census import."""
    context = ssl.create_default_context()
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise RuntimeError("TLS_VERIFICATION_REQUIRED")
    urls = ["https://firmen.cc.hs-hannover.de/", "https://www.munich-startup.de/",
            "https://www.region-stuttgart.de/"]
    urls += [json.loads((ROOT / "config/census" / name).read_text())["start_url"]
             for name in ("berlin-startup-map.json", "wolfsburg-innovations.json", "ingolstadt-digital.json")]
    for url in urls:
        try:
            with urlopen(Request(url, method="HEAD"), timeout=5, context=context):
                pass
        except HTTPError:
            pass  # HTTP rejection still proves the authenticated TLS connection.
    return len(urls)

def connect():
    return psycopg.connect(**get_database_config(), connect_timeout=10, autocommit=True)


def checked_source():
    value = json.loads((ROOT / "rcc-source-manifest.json").read_text())["source_sha"]
    if not re.fullmatch("[0-9a-f]{40}", value):
        raise ValueError("PINNED_SOURCE_REQUIRED")
    return value


def collect(db, run_id, sha, state, progress=None):
    # Commit intent before any request. A repeated workload never recrawls.
    with db.transaction():
        db.execute("INSERT INTO bronze_native_census_runs(run_id,source_sha,state) VALUES (%s,%s,'DISCOVERING')",
                   (run_id, sha))
    snapshots, source_states, source_errors = {}, {}, {}
    for source_id, module, options in SOURCES:
        update(progress, phase="COLLECTING", completed=len(source_states), total=len(SOURCES),
               current=source_id, errors=sum(v == "SOURCE_FAILED" for v in source_states.values()))
        target = state / (source_id + ".json")
        evidence_dir = state / (source_id + "-http")
        evidence_dir.mkdir(exist_ok=False)
        command = [sys.executable, "-m", "src.census_sources." + module,
                   *options, "--output", str(target)]
        payload, source_state = {}, "SOURCE_FAILED"
        try:
            # Explicit trusted paths propagate to subprocesses; never inherit host credentials.
            with (state / (source_id + ".log")).open("xb") as log:
                completed = subprocess.run(command, cwd=ROOT, stdout=log, stderr=log,
                                           timeout=900, check=False,
                                           env={**os.environ, "JAP_CENSUS_EVIDENCE_DIR": str(evidence_dir)})
            if completed.returncode == 0 and target.stat().st_size <= 32_000_000:
                payload = json.loads(target.read_text())
                if not isinstance(payload.get("companies"), list):
                    raise ValueError("SOURCE_ROWS_INVALID")
                snapshots[source_id] = payload
                source_state = "OBSERVED" if payload.get("complete") is True and payload["companies"] else "PARTIAL"
            else:
                payload = {"error": source_error(state / (source_id + ".log")), "returncode": completed.returncode}
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            payload = {"error": type(error).__name__, "source_id": source_id}
        if source_state == "SOURCE_FAILED" and target.is_file() and target.stat().st_size <= 32_000_000:
            # Atomic pagination checkpoints retain successful pages after a later
            # transport failure. They never count as complete source coverage.
            try:
                checkpoint = json.loads(target.read_text())
                if isinstance(checkpoint.get("companies"), list) and checkpoint["companies"]:
                    payload = dict(checkpoint, complete=False, error=payload.get("error", "SOURCE_INCOMPLETE"))
                    snapshots[source_id] = payload
                    source_state = "PARTIAL"
            except (OSError, ValueError):
                pass
        source_states[source_id] = source_state
        if source_state != "OBSERVED":
            source_errors[source_id] = payload.get("error") or payload.get("coverage_issue") or "SOURCE_INCOMPLETE"
        update(progress, completed=len(source_states), error_code=payload.get("error"),
               errors=sum(v == "SOURCE_FAILED" for v in source_states.values()))
        with db.transaction():
            for meta in sorted(evidence_dir.glob("*.json")):
                evidence = json.loads(meta.read_text())
                body = meta.with_suffix(".body").read_bytes()
                if hashlib.sha256(body).hexdigest() != evidence["sha256"]:
                    raise RuntimeError("PUBLIC_EVIDENCE_CHANGED")
                db.execute("INSERT INTO bronze_native_census_http VALUES (%s,%s,%s,%s,%s,%s)",
                           (run_id, source_id, meta.stem, evidence["url"], evidence["sha256"], body))
            db.execute("INSERT INTO bronze_native_census_sources VALUES (%s,%s,%s,%s,%s)",
                       (run_id, source_id, source_state, Jsonb(payload), digest(payload)))
    # Preserve the existing Classic population too, without changing its activation state.
    previous = db.execute("""SELECT DISTINCT ON (company_key) company_key,company_name,candidate_url
                             FROM employer_origin_source_candidates
                             ORDER BY company_key,updated_at DESC NULLS LAST,id DESC""").fetchall()
    baseline = {"companies": [{"company_key": key, "company_name": name, "website": url}
                             for key, name, url in previous]}
    snapshots["classic_existing_candidates"] = baseline
    # Keep all prior public observations, including incomplete-source records.
    # New campaign IDs never overwrite an earlier population or its assessments.
    prior = db.execute("""SELECT observation FROM bronze_native_census_candidates
                          WHERE run_id != %s ORDER BY id""", (run_id,)).fetchall()
    inherited = []
    for (observation,) in prior:
        inherited.extend(item["row"] for item in observation.get("observations", [])
                         if isinstance(item.get("row"), dict))
    snapshots["prior_bronze_observations"] = {"companies": inherited}
    result = population(snapshots)
    summary = {k: v for k, v in result.items() if k != "candidates"}
    summary["sources"] = source_states
    summary["source_errors"] = source_errors
    summary["coverage_complete"] = all(v == "OBSERVED" for v in source_states.values())
    summary["coverage_scope"] = "configured_public_directories_not_historical_cloud_parity"
    summary["population_digest"] = digest(result["candidates"])
    summary["new_census_observed"] = any(p.get("companies") for k, p in snapshots.items()
                                        if k not in ("classic_existing_candidates", "prior_bronze_observations"))
    terminal = "BRONZE_READY" if summary["new_census_observed"] and not result["factory_budget_exceeded"] else "REVIEW_REQUIRED"
    update(progress, phase="SAVING_BRONZE", completed=0, total=result["candidate_count"], current="")
    with db.transaction():
        db.execute("INSERT INTO bronze_native_census_sources VALUES (%s,%s,%s,%s,%s)",
                   (run_id, "classic_existing_candidates", "OBSERVED", Jsonb(baseline), digest(baseline)))
        for index, row in enumerate(result["candidates"]):
            db.execute("""INSERT INTO bronze_native_census_candidates
                          (run_id,company_key,observation,batch_index) VALUES (%s,%s,%s,%s)""",
                       (run_id, row["company_key"], Jsonb(row), index // BATCH_SIZE))
        db.execute("""UPDATE bronze_native_census_runs SET state=%s,summary=%s,completed_at=now()
                      WHERE run_id=%s""", (terminal, Jsonb(summary), run_id))
    if db.execute("SELECT count(*) FROM bronze_native_census_candidates WHERE run_id=%s",
                  (run_id,)).fetchone()[0] != result["candidate_count"]:
        raise RuntimeError("BRONZE_READBACK_MISMATCH")
    return {"status": terminal, "candidate_count": result["candidate_count"],
            "factory_batch_count": result["factory_batch_count"], "sources": source_states, "source_errors": source_errors,
            "coverage_complete": summary["coverage_complete"],
            "population_digest": summary["population_digest"],
            "retained_in_bronze": True, "sources_activated": 0}


def prepare_recheck(db, run_id, sha, parent, progress=None):
    """Freeze a completed population into a new run; never recrawl or overwrite."""
    with db.transaction():
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        old = db.execute("SELECT state,summary FROM bronze_native_census_runs WHERE run_id=%s",
                         (parent,)).fetchone()
        if not old or old[0] != "BRONZE_READY" or parent == run_id:
            raise RuntimeError("RECHECK_PARENT_NOT_READY")
        rows = db.execute("""SELECT c.company_key,c.observation,c.batch_index,f.state
            FROM bronze_native_census_candidates c LEFT JOIN native_census_factory_results f
            ON f.candidate_id=c.id WHERE c.run_id=%s ORDER BY c.id""", (parent,)).fetchall()
        if (len(rows) != old[1]["candidate_count"] or not rows
                or any(r[3] is None or r[3] == "ASSESSING" for r in rows)):
            raise RuntimeError("RECHECK_PARENT_NOT_COMPLETE")
        summary = dict(old[1], recheck_parent=parent, source_recrawled=False)
        db.execute("""INSERT INTO bronze_native_census_runs(run_id,source_sha,state,summary,completed_at)
            VALUES (%s,%s,'BRONZE_READY',%s,now())""", (run_id, sha, Jsonb(summary)))
        db.execute("""INSERT INTO bronze_native_census_sources
            SELECT %s,source_id,state,payload,payload_digest FROM bronze_native_census_sources
            WHERE run_id=%s""", (run_id, parent))
        for key, observation, batch, _ in rows:
            db.execute("""INSERT INTO bronze_native_census_candidates
                (run_id,company_key,observation,batch_index) VALUES (%s,%s,%s,%s)""",
                       (run_id, key, Jsonb(observation), batch))
    update(progress, phase="BRONZE_READY", completed=len(rows), total=len(rows), current="")
    return dict(status="BRONZE_READY", candidate_count=len(rows),
                factory_batch_count=summary["factory_batch_count"], sources=summary["sources"],
                source_errors=summary["source_errors"], coverage_complete=summary["coverage_complete"],
                population_digest=summary["population_digest"], retained_in_bronze=True,
                sources_activated=0, recheck_parent=parent, source_recrawled=False)


def assess_one(input_path, output_path):
    from scripts import run_generic_employer_origin_product as product
    row = json.loads(input_path.read_text())
    # The same deterministic factory used by the existing productive recipe.
    args = argparse.Namespace(target_location="", origin_max_candidates=12,
                              origin_timeout_seconds=5.0, http_timeout_seconds=10.0,
                              acquisition_get_cap=12, navigation_hops=6)
    product.layer_core.run_origin_discovery = product.run_origin_discovery
    product.layer_core.discover_navigation_candidates = product.discover_navigation_candidates
    result = product.assess_candidate(row, args).to_json()
    atomic_json(output_path, result)


def factory_batch(db, run_id, index, state, progress=None):
    run = db.execute("SELECT state,summary FROM bronze_native_census_runs WHERE run_id=%s", (run_id,)).fetchone()
    if not run or run[0] != "BRONZE_READY" or not 0 <= index < run[1]["factory_batch_count"]:
        raise ValueError("CENSUS_BATCH_NOT_READY")
    rows = db.execute("""SELECT id,observation FROM bronze_native_census_candidates
                         WHERE run_id=%s AND batch_index=%s ORDER BY company_key""", (run_id, index)).fetchall()
    outcomes = {}
    for candidate_id, observation in rows:
        update(progress, phase="ASSESSING", total=len(rows), completed=sum(outcomes.values()),
               current=observation["company_name"][:160], batch_index=index)
        existing = db.execute("SELECT state FROM native_census_factory_results WHERE candidate_id=%s",
                              (candidate_id,)).fetchone()
        if existing:
            # Proven completed rows can be read; an uncertain intent cannot be retried.
            if existing[0] == "ASSESSING":
                raise RuntimeError("FACTORY_INTENT_REQUIRES_RECONCILIATION")
            outcomes[existing[0]] = outcomes.get(existing[0], 0) + 1
            continue
        db.execute("INSERT INTO native_census_factory_results(candidate_id,state,result) VALUES (%s,'ASSESSING','{}')",
                   (candidate_id,))
        websites = observation["websites"]
        row = {"id": candidate_id, "company_key": observation["company_key"],
               "company_name": observation["company_name"],
               "candidate_url": websites[0] if len(websites) == 1 else None}
        input_path, output_path = state / f"{candidate_id}-input.json", state / f"{candidate_id}-result.json"
        atomic_json(input_path, row)
        result = {}
        if len(websites) > 1:
            outcome, result = "IDENTITY_REVIEW", {"reason": "MULTIPLE_OBSERVED_WEBSITES"}
        else:
            try:
                with (state / f"{candidate_id}.log").open("xb") as log:
                    completed = subprocess.run([sys.executable, "-m", "scripts.run_native_census_campaign",
                                                "--assess", str(input_path), "--output", str(output_path)],
                                               cwd=ROOT, stdout=log, stderr=log, timeout=45)
                if completed.returncode == 0 and output_path.stat().st_size <= 2_000_000:
                    result = json.loads(output_path.read_text())
                    if result.get("candidate_id") != candidate_id or result.get("company_key") != row["company_key"]:
                        raise ValueError("ASSESSMENT_IDENTITY_MISMATCH")
                    outcome = "QUALIFIED" if result.get("recipe_ready") is True else "TECHNICAL_GAP"
                else:
                    outcome = "ASSESSMENT_FAILED"
            except subprocess.TimeoutExpired:
                outcome = "TIME_LIMIT"
            except (OSError, ValueError):
                outcome = "ASSESSMENT_FAILED"
        # No job writes or activation occur in assess_one; diagnosed gaps are terminal outcomes.
        db.execute("""UPDATE native_census_factory_results SET state=%s,result=%s,completed_at=now()
                      WHERE candidate_id=%s AND state='ASSESSING'""",
                   (outcome, Jsonb(result), candidate_id))
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        update(progress, completed=sum(outcomes.values()),
               errors=sum(v for k, v in outcomes.items() if k != "QUALIFIED"))
    verified = db.execute("""SELECT count(*) FROM native_census_factory_results f
                            JOIN bronze_native_census_candidates c ON c.id=f.candidate_id
                            WHERE c.run_id=%s AND c.batch_index=%s AND f.state!='ASSESSING'""",
                          (run_id, index)).fetchone()[0]
    if verified != len(rows):
        raise RuntimeError("FACTORY_BATCH_READBACK_MISMATCH")
    return {"status": "FACTORY_BATCH_ASSESSED", "batch_index": index, "candidates": verified,
            "outcomes": outcomes, "sources_activated": 0, "jobs_ingested": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload")
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--assess", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        from scripts import run_generic_employer_origin_product  # noqa: F401
        with connect() as db:
            for table in ("bronze_native_census_runs", "bronze_native_census_sources",
                          "bronze_native_census_candidates", "bronze_native_census_http",
                          "native_census_factory_results"):
                if not db.execute("SELECT to_regclass(%s)", (table,)).fetchone()[0]:
                    raise ValueError("CENSUS_SCHEMA_MISSING")
        print(json.dumps({"status": "CENSUS_PREFLIGHT_READY", "source_sha": checked_source(),
                          "verified_tls_sources": verify_tls()}))
        return
    if args.assess:
        assess_one(args.assess, args.output)
        return
    sha = checked_source()
    run_id = "classic-native-census:" + sha
    state = args.state_dir
    state.mkdir(parents=True, exist_ok=True)
    with Progress(state) as progress, connect() as db:
        if args.workload == "classic-census-v1":
            recheck = ROOT / "config/census/factory-recheck.json"
            if recheck.exists():
                parent = json.loads(recheck.read_text())["parent_run"]
                proof = prepare_recheck(db, run_id, sha, parent, progress)
            else:
                proof = collect(db, run_id, sha, state, progress)
        elif re.fullmatch(r"classic-census-factory-[0-9]{2}", args.workload or ""):
            proof = factory_batch(db, run_id, int(args.workload[-2:]), state, progress)
        else:
            raise ValueError("UNAPPROVED_WORKLOAD")
        progress.update(phase=proof["status"], current="")
    proof.update(source_sha=sha, run_id=run_id, workload=args.workload,
                 completed_at=datetime.now(UTC).isoformat())
    atomic_json(state / "native-census-result.json", proof)


if __name__ == "__main__":
    main()
