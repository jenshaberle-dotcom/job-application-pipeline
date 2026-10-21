from contextlib import nullcontext
from argparse import Namespace
from scripts import run_classic_connector_factory as factory
from src.connectors.classic_factory_delivery import DeliveryJournal


def test_delivery_finishes_before_next_employer_qualification(tmp_path, monkeypatch):
    calls=[]
    def qualify(row,args):
        calls.append('qualify:'+row['company_key'])
        return row
    monkeypatch.setattr(factory,'qualify',qualify)
    monkeypatch.setattr(factory.activation,'_proof_rows',lambda p:p['results'])
    monkeypatch.setattr(factory.activation,'_resolve_projection_origins',lambda *a:[])
    monkeypatch.setattr(factory.activation,'apply_activation',lambda *a,**k:None)
    monkeypatch.setattr(factory,'verify_activation',lambda *a:None)
    def ingest(key,journal):
        calls.append('ingest:'+key)
        return dict(observed_jobs=1,inserted_jobs=1)
    def silver(key):
        calls.append('silver:'+key)
        return dict(selected=1,included=1,skipped=0)
    monkeypatch.setattr(factory,'ingest',ingest)
    monkeypatch.setattr(factory,'promote_silver',silver)
    journal=DeliveryJournal(tmp_path/'receipt.json',{})
    conn=Namespace(transaction=nullcontext)
    rows=[dict(company_key='first'),dict(company_key='second')]
    result=factory.execute(conn,rows,journal,Namespace(state_dir=tmp_path))
    assert calls==['qualify:first','ingest:first','silver:first','qualify:second','ingest:second','silver:second']
    assert result['silver_included']==2
    calls.clear()
    factory.execute(conn,rows,journal,Namespace(state_dir=tmp_path))
    assert calls==[]  # durable receipts suppress all completed effects

