"""Finite discovery-only sensor recipe. Executed exclusively by native RCC."""
import argparse
import json
from pathlib import Path

from src.connectors.registry import SourceRole, create_connector, source_role
from src.ingest_jobs import configure_ingestion_execution_application_name, load_recurring_profile_names
from src.ingestion.repository import JobIngestionRepository
from src.ingestion.runner import JobIngestionRunner
from src.connectors.classic_factory_delivery import atomic_json
from scripts.run_native_census_campaign import Progress, checked_source
from src.search_intelligence.market_sensor_candidate_promotion_batch import (
    source_family_for_company_key, source_name_candidate_for_company_key,
)

SOURCES = {"bundesagentur_fuer_arbeit", "stepstone"}


def plan(repository):
    profiles = repository.load_active_search_profiles()
    recurring = load_recurring_profile_names(repository, profiles)
    selected = [p for p in profiles if p.source_name in SOURCES and p.profile_name in recurring
                and source_role(p.source_name) == SourceRole.SENSOR]
    tasks = [(p, pair) for p in selected for pair in repository.load_active_search_terms(p.profile_name)]
    if not tasks or len(tasks) > 100:
        raise RuntimeError("SENSOR_PROFILE_BUDGET_INVALID")
    return tasks


def execute(repository, tasks, state):
    execution = configure_ingestion_execution_application_name().split(":")[-1]
    outcomes = []
    with repository.get_connection() as db:
        known = {r[0] for r in db.execute("SELECT DISTINCT normalized_company_key FROM market_evidence").fetchall()}
    with Progress(state) as progress:
        for index, (profile, pair) in enumerate(tasks):
            progress.update(phase="MARKET_SENSORS", completed=index, total=len(tasks),
                            current=profile.profile_name, errors=sum(not r["ok"] for r in outcomes))
            try:
                runner = JobIngestionRunner(repository, create_connector(profile.source_name),
                                            source_role=SourceRole.SENSOR)
                runner.run_market_sensor_observation([pair])
                outcomes.append(dict(profile=profile.profile_name, ok=True))
            except Exception as error:
                outcomes.append(dict(profile=profile.profile_name, ok=False, error=type(error).__name__))
        with repository.get_connection() as db:
            rows = db.execute("""SELECT DISTINCT e.normalized_company_key,e.company_name
                 FROM market_evidence e JOIN ingestion_runs r ON r.id=e.ingestion_run_id
                 WHERE r.execution_id=%s""", (execution,)).fetchall()
            # Candidate metadata only. No guessed employer URL, connector activation
            # or Product job writes. Serialize with other candidate creation runs.
            db.execute("SELECT pg_advisory_xact_lock(hashtext('rcc-market-candidate-discovery'))")
            created = 0
            for key, name in rows:
                if not key or not name:
                    continue
                if db.execute("SELECT 1 FROM employer_origin_source_candidates WHERE company_key=%s", (key,)).fetchone():
                    continue
                db.execute("""INSERT INTO employer_origin_source_candidates
                    (company_key,company_name,source_name_candidate,source_family_candidate,
                     status,risk_level,source_type_candidate,notes,updated_at)
                    VALUES (%s,%s,%s,%s,'discovery','unknown','employer_origin_career_site',%s,now())""",
                           (key, name, source_name_candidate_for_company_key(key), source_family_for_company_key(key),
                            "RCC market sensor observation; employer origin not verified; execution=" + execution))
                created += 1
        result = dict(status="MARKET_SENSORS_OBSERVED", source_sha=checked_source(), execution_id=execution,
                      terms=len(tasks), successful_terms=sum(r["ok"] for r in outcomes),
                      failed_terms=sum(not r["ok"] for r in outcomes), companies_observed=len({r[0] for r in rows}),
                      new_market_companies=len({r[0] for r in rows} - known),
                      discovery_candidates_created=created, product_jobs_written=0,
                      sources_activated=0, outcomes=outcomes)
        atomic_json(state / "native-sensor-result.json", result)
        progress.update(phase="COMPLETE", completed=len(tasks), errors=result["failed_terms"])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--workload")
    args = parser.parse_args()
    repo = JobIngestionRepository()
    tasks = plan(repo)
    if args.preflight:
        print(json.dumps(dict(status="SENSOR_PREFLIGHT_READY", source_sha=checked_source(), terms=len(tasks))))
        return
    if args.workload != "market-sensor-discovery" or args.state_dir is None:
        raise RuntimeError("FIXED_SENSOR_WORKLOAD_REQUIRED")
    args.state_dir.mkdir(parents=True, exist_ok=True)
    intent = args.state_dir / "sensor-intent.json"
    with intent.open("x") as stream:
        json.dump({"source_sha": checked_source()}, stream)
    execute(repo, tasks, args.state_dir)


if __name__ == "__main__":
    main()


