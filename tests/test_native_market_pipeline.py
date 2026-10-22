from argparse import Namespace
from contextlib import nullcontext
from datetime import datetime, timezone, timedelta
import json
import subprocess
import pytest
from scripts import run_native_market_pipeline as pipeline
from src.connectors.classic_factory_delivery import DeliveryJournal

NOW=datetime(2026,10,22,tzinfo=timezone.utc)


def rows(n):
    return [dict(id=i,company_key=f'firm-{i:03}',company_name=f'Firm {i}',candidate_url=None) for i in range(n)]


def test_budget_retains_backlog_and_rotates_active_sources():
    candidates=rows(100)
    active={r['company_key']:NOW-timedelta(days=r['id']) for r in candidates[:60]}
    queue={r['company_key']:dict(first_seen=NOW,last_attempt=None) for r in candidates[60:]}
    selected,budget=pipeline.select_population(candidates,active,queue,'a'*40,NOW)
    assert len(selected)==70 and budget['discovery_deferred']==20 and budget['active_deferred']==10
    assert selected[0]['company_key']=='firm-059'
    assert len(queue)==40  # selection does not consume or drop the overflow


def test_unchanged_failures_back_off_but_changed_evidence_is_rechecked():
    candidate=rows(1)[0]
    queue={candidate['company_key']:dict(first_seen=NOW,last_attempt=NOW,
        attempted_source_sha='a'*40,attempted_identity_sha256=pipeline.identity(candidate))}
    assert pipeline.select_population([candidate],{},queue,'a'*40,NOW)[0]==[]
    assert pipeline.select_population([candidate],{},queue,'b'*40,NOW)[0]==[candidate]
    assert pipeline.select_population([candidate],{},queue,'a'*40,NOW+timedelta(days=8))[0]==[candidate]
    changed={**candidate,'candidate_url':'https://example.org/jobs'}
    assert pipeline.select_population([changed],{},queue,'a'*40,NOW)[0]==[changed]


def report(journal,count,summary=None):
    return pipeline.finish_report('a'*40,'daily-2026-10-22',dict(population_count=count),summary or {},journal,
        dict(discovery_deferred=0,active_deferred=0),dict(successful_terms=1,failed_terms=0))


def test_zero_jobs_is_explicitly_complete_but_never_ui_success(tmp_path):
    journal=DeliveryJournal(tmp_path/'receipt.json',{})
    journal.stage('qualify:firm',lambda:dict(proof='FAIL'),effect=False)
    result=report(journal,1,dict(qualification_gaps=1,observed_jobs=0))
    assert result['status']=='COMPLETE_WITH_GAPS'
    assert result['phases']['delivery']['state']=='SKIPPED_PROVEN'
    assert result['e2e_accepted'] is False and result['ui_witness_required'] is True


def test_uncertain_write_holds_and_never_replays(tmp_path):
    journal=DeliveryJournal(tmp_path/'receipt.json',{})
    journal.stage('qualify:firm',lambda:{},effect=False)
    calls=[]
    def failed_write():
        calls.append(1)
        raise OSError('reply lost after possible commit')
    with pytest.raises(OSError):journal.stage('ingest:firm',failed_write,effect=True)
    with pytest.raises(RuntimeError):journal.stage('ingest:firm',failed_write,effect=True)
    result=report(journal,1)
    assert calls==[1] and result['status']=='INCOMPLETE' and not result['effects_proven']


def test_missing_factory_result_cannot_complete(tmp_path):
    assert report(DeliveryJournal(tmp_path/'receipt.json',{}),1)['status']=='INCOMPLETE'


def test_qualification_has_hard_timeout_and_exact_identity(tmp_path,monkeypatch):
    candidate=rows(1)[0]
    def worker(command,**kwargs):
        assert kwargs['timeout']==60 and kwargs['check'] is True
        with open(command[-1],'w') as stream:json.dump(dict(candidate_id=999,company_key=candidate['company_key']),stream)
    monkeypatch.setattr(subprocess,'run',worker)
    with pytest.raises(ValueError,match='identity_mismatch'):
        pipeline.bounded_qualify(candidate,Namespace(state_dir=tmp_path))


def test_sensor_factory_ingest_silver_and_quality_order_with_proof_gate(tmp_path,monkeypatch):
    factory=pipeline.factory
    import scripts.run_product_v1_assessment_materialization as materialization
    import scripts.product_v1_delivery_quality as quality
    calls=[]
    monkeypatch.setattr(materialization,'authorized_recurring_employer_origin_sources',lambda _: {'generic_origin:good','generic_origin:unselected'})
    monkeypatch.setattr(factory.activation,'_proof_rows',lambda p:p['results'] if p['results'][0]['company_key']=='good' else [])
    monkeypatch.setattr(factory.activation,'_resolve_projection_origins',lambda *a:[])
    monkeypatch.setattr(factory.activation,'apply_activation',lambda *a,**k:calls.append('activate'))
    monkeypatch.setattr(factory,'verify_activation',lambda *a:None)
    monkeypatch.setattr(factory,'ingest',lambda *a:(calls.append('ingest') or dict(observed_jobs=2,inserted_jobs=1)))
    monkeypatch.setattr(factory,'promote_silver',lambda *a:(calls.append('silver') or dict(selected=1,included=1,skipped=0)))
    monkeypatch.setattr(quality,'maintain_source',lambda s,j:(calls.append('quality:'+s) or dict(checked=1,scored=1,unavailable=0,blocked=[])))
    def qualify(row,args):
        calls.append('factory:'+row['company_key']);return row
    journal=DeliveryJournal(tmp_path/'receipt.json',{})
    journal.stage('pipeline:sensor',lambda:(calls.append('sensor') or {}),effect=True)
    result=factory.execute(Namespace(transaction=nullcontext),[dict(company_key='bad'),dict(company_key='good')],
        journal,Namespace(state_dir=tmp_path),qualifier=qualify,quality_sources={'generic_origin:good'})
    assert calls==['sensor','factory:bad','factory:good','activate','ingest','silver','quality:generic_origin:good']
    assert result['qualified_sources']==1 and result['silver_included']==1
    assert 'activate:bad' not in journal.data['stages']
