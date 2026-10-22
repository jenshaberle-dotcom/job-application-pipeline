"""One RCC occurrence: sensor evidence -> bounded Factory -> delivery -> Silver.

No scheduler, geographic filter, guessed activation or automatic replay lives here.
The separate RCC UI witness must still verify the resulting projection.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from scripts import run_classic_connector_factory as factory
from scripts import run_native_market_sensors as sensors
from scripts.run_native_census_campaign import checked_source, assess_one
from src.connectors.classic_factory_delivery import DeliveryJournal, atomic_json, fingerprint
from src.ingestion.repository import JobIngestionRepository

NEW_LIMIT = 20
ACTIVE_LIMIT = 50
QUALIFICATION_SECONDS = 60
WORKLOAD = 'market-factory-job-delivery'


def identity(row):
    return fingerprint({key: row.get(key) for key in ('id', 'company_key', 'company_name', 'candidate_url')})


def select_population(candidates, active, queue, sha, now):
    """Rotate active sources and retained backlog; never drop a budget overflow."""
    by_key = {row['company_key']: row for row in candidates}
    if len(by_key) != len(candidates):
        raise ValueError('candidate_identity_not_unique')
    active_keys = sorted((key for key in active if key in by_key),
                         key=lambda key: (active[key] or datetime.min.replace(tzinfo=timezone.utc), key))
    eligible = []
    for key, item in queue.items():
        if key not in by_key or key in active:
            continue
        if (item.get('last_attempt') is None or item.get('attempted_source_sha') != sha
                or item.get('attempted_identity_sha256') != identity(by_key[key])
                or item['last_attempt'] <= now - timedelta(days=7)):
            eligible.append(key)
    eligible.sort(key=lambda key: (queue[key].get('last_attempt') or datetime.min.replace(tzinfo=timezone.utc),
                                   queue[key]['first_seen'], key))
    keys = active_keys[:ACTIVE_LIMIT] + eligible[:NEW_LIMIT]
    return [by_key[key] for key in keys], dict(
        active_selected=min(len(active_keys), ACTIVE_LIMIT),
        discovery_selected=min(len(eligible), NEW_LIMIT),
        active_deferred=max(0, len(active_keys)-ACTIVE_LIMIT),
        discovery_deferred=max(0, len(eligible)-NEW_LIMIT),
        retained_backlog=len(queue), daily_new_limit=NEW_LIMIT, daily_active_limit=ACTIVE_LIMIT)


def snapshot(conn, sensor_proof, sha):
    """Queue only firms observed by this exact sensor execution, retaining older backlog."""
    with conn.transaction():
        conn.execute("INSERT INTO rcc_market_pipeline_candidates(company_key) "
            "SELECT DISTINCT e.normalized_company_key FROM market_evidence e "
            "JOIN ingestion_runs r ON r.id=e.ingestion_run_id "
            "JOIN employer_origin_source_candidates c ON c.company_key=e.normalized_company_key "
            "WHERE r.execution_id=%s ON CONFLICT(company_key) DO UPDATE SET last_seen=now()",
            (sensor_proof['execution_id'],))
        candidates = factory.product.layer_core._load_candidates(conn)
        active = {r['company_key']: r['last_delivery'] for r in conn.execute(
            "SELECT a.company_key,max(i.finished_at) AS last_delivery "
            "FROM generic_employer_origin_active_sources a JOIN search_profiles p ON p.source_name=a.source_name "
            "LEFT JOIN ingestion_runs i ON i.source_name=a.source_name AND i.status='success' "
            "WHERE a.proof_state='pass' AND p.is_active AND p.recurring_ingestion_enabled GROUP BY a.company_key"
        ).fetchall()}
        queue = {r['company_key']:r for r in conn.execute('SELECT * FROM rcc_market_pipeline_candidates').fetchall()}
        selected, budget = select_population(candidates, active, queue, sha, datetime.now(timezone.utc))
    return dict(candidates=selected, budget=budget)


def bounded_qualify(row, args):
    token = fingerprint(row['company_key'])
    input_path = args.state_dir / (token + '-factory-input.json')
    output_path = args.state_dir / (token + '-factory-result.json')
    atomic_json(input_path, row)
    with (args.state_dir / (token + '-factory.log')).open('xb') as log:
        subprocess.run([sys.executable, '-m', 'scripts.run_native_market_pipeline',
            '--assess', str(input_path), str(output_path)], check=True, timeout=QUALIFICATION_SECONDS,
            stdout=log, stderr=log)
    if output_path.stat().st_size > 1024*1024:
        raise ValueError('factory_result_oversized')
    result = json.loads(output_path.read_text())
    if result.get('candidate_id') != row['id'] or result.get('company_key') != row['company_key']:
        raise ValueError('factory_result_identity_mismatch')
    return result


def finish_report(sha, occurrence, check, summary, journal, budget, sensor_proof):
    stages = journal.data['stages']
    qualifications = [v for k,v in stages.items() if k.startswith('qualify:')]
    terminal = sum(v['state'] in ('SUCCEEDED', 'FAILED') for v in qualifications)
    selected = check['population_count']
    held = sorted(k for k,v in stages.items() if v['state'] in ('RUNNING', 'HELD'))
    complete = not held and terminal == selected and sensor_proof['failed_terms'] == 0
    gaps = summary.get('qualification_gaps', 0) or summary.get('qualification_errors') or budget['discovery_deferred'] or budget['active_deferred']
    phases = {}
    for name,prefix in (('factory','qualify:'),('delivery','ingest:'),('silver','silver:'),('quality','health:')):
        rows=[v for k,v in stages.items() if k.startswith(prefix)]
        phases[name] = dict(state='SUCCEEDED' if rows and complete else 'SKIPPED_PROVEN' if not rows and complete else 'INCOMPLETE',
                            reason='durable_stage_receipts' if rows else 'no_eligible_sources_or_jobs', count=len(rows))
    phases['sensor']=dict(state='SUCCEEDED' if sensor_proof['failed_terms']==0 else 'INCOMPLETE',
                          reason='exact_execution_receipt', count=sensor_proof['successful_terms'])
    return dict(schema='rcc.jap.market_pipeline.v1', source_sha=sha, workload=WORKLOAD,
        occurrence=occurrence, status=('COMPLETE_WITH_GAPS' if gaps else 'COMPLETE') if complete else 'INCOMPLETE',
        effects_proven=complete, held_stages=held, e2e_accepted=False, phases=phases,
        factory=dict(selected_count=selected, terminal_count=terminal, pending_count=selected-terminal),
        preflight=check, delivery=summary, budget=budget, sensors=sensor_proof,
        ui_witness_required=True)


def execute_pipeline(conn, state, sha, occurrence):
    execution_key=fingerprint(dict(source_sha=sha, occurrence=occurrence))
    config=factory.get_database_config()
    database=fingerprint({key:config[key] for key in ('host','port','dbname','user')})
    # Unique occurrence across source upgrades prevents a second daily execution.
    with conn.transaction():
        conn.execute("INSERT INTO rcc_market_pipeline_runs(execution_key,occurrence,source_sha,state) VALUES (%s,%s,%s,'RUNNING')",
                     (execution_key,occurrence,sha))
    journal=DeliveryJournal(state/'receipt.json',dict(source_sha=sha, occurrence=occurrence, database=database, delivery_scope='market_pipeline'))
    repository=JobIngestionRepository()
    sensor_proof=journal.stage('pipeline:sensor', lambda:sensors.execute(repository,sensors.plan(repository),state),effect=True)
    if sensor_proof['failed_terms']:
        raise RuntimeError('SENSOR_PARTIAL_EFFECTS_REQUIRE_REVIEW')
    population=journal.stage('pipeline:population',lambda:snapshot(conn,sensor_proof,sha),effect=True)
    candidates,budget=population['candidates'],population['budget']
    with conn.transaction():
        conn.execute('UPDATE rcc_market_pipeline_runs SET population=%s::jsonb WHERE execution_key=%s',
                     (json.dumps(candidates,default=str),execution_key))
    check=dict(binding=dict(source_sha=sha,delivery_scope='market_pipeline',database=database,population=fingerprint(candidates),
                            occurrence=occurrence),population_count=len(candidates))
    args=argparse.Namespace(state_dir=state,target_location='',origin_max_candidates=12,
                           origin_timeout_seconds=5.0,http_timeout_seconds=10.0)
    selected_sources={'generic_origin:'+row['company_key'] for row in candidates}
    summary=factory.execute(conn,candidates,journal,args,qualifier=bounded_qualify,quality_sources=selected_sources)
    def save_results():
        with conn.transaction():
            for row in candidates:
                result=journal.data['stages'].get('qualify:'+row['company_key'],{})
                conn.execute("UPDATE rcc_market_pipeline_candidates SET last_attempt=now(),attempted_source_sha=%s,"
                    "attempted_identity_sha256=%s,last_result=%s::jsonb WHERE company_key=%s",
                    (sha,identity(row),json.dumps(result,default=str),row['company_key']))
        return dict(recorded=len(candidates))
    journal.stage('pipeline:results',save_results,effect=True)
    report=finish_report(sha,occurrence,check,summary,journal,budget,sensor_proof)
    acceptance=dict(summary,preflight=check,status=report['status'],schema='jap.classic_factory_acceptance.v1',
                    e2e_accepted=False)
    atomic_json(state/'acceptance.json',acceptance)
    with conn.transaction():
        conn.execute('UPDATE rcc_market_pipeline_runs SET state=%s,result=%s::jsonb,finished_at=now() WHERE execution_key=%s',
                     (report['status'],json.dumps(report,default=str),execution_key))
    atomic_json(state/'native-market-pipeline-result.json',report)
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--state-dir',type=Path)
    parser.add_argument('--assess',nargs=2,type=Path)
    args=parser.parse_args()
    if args.assess:
        assess_one(*args.assess);return 0
    occurrence=os.environ.get('RCC_PIPELINE_OCCURRENCE','')
    if not re.fullmatch(r'daily-\d{4}-\d{2}-\d{2}',occurrence) or args.state_dir is None:
        raise ValueError('ATTESTED_OCCURRENCE_AND_STATE_REQUIRED')
    args.state_dir.mkdir(parents=True,exist_ok=True)
    sha=checked_source()
    try:
        policy=json.loads((factory.ROOT/'config/classic_connector_factory_policy.json').read_text())
        if policy.get('authorized') is not True or policy.get('scope')!='classic_full_population_job_delivery':
            raise ValueError('CLASSIC_FACTORY_NOT_AUTHORIZED')
        with factory.database_session() as conn:
            if not conn.execute('SELECT pg_try_advisory_lock(%s) AS acquired',(factory.LOCK_ID,)).fetchone()['acquired']:
                raise RuntimeError('FACTORY_ALREADY_RUNNING')
            report=execute_pipeline(conn,args.state_dir,sha,occurrence)
        return 0 if report['effects_proven'] else 2
    except Exception as exc:
        atomic_json(args.state_dir/'native-market-pipeline-result.json',dict(schema='rcc.jap.market_pipeline.v1',
            source_sha=sha,workload=WORKLOAD,occurrence=occurrence,status='INCOMPLETE',effects_proven=False,
            error_type=type(exc).__name__,e2e_accepted=False))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
