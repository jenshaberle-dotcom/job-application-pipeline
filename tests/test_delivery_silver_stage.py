from argparse import Namespace
import pytest
from scripts import run_classic_connector_factory as factory
from src import run_silver_jobs
from src.connectors.classic_factory_delivery import DeliveryJournal


def test_silver_drains_only_authorized_employer(monkeypatch):
    calls=[]
    batches=iter([dict(selected=500,included=400,skipped=100),dict(selected=3,included=1,skipped=2)])
    def run(args):
        calls.append(args)
        return next(batches)
    monkeypatch.setattr(run_silver_jobs,'main',run)
    result=factory.promote_silver('acme')
    assert result==dict(source='generic_origin:acme',selected=503,included=401,skipped=102,completed=True)
    assert calls==[['--source','generic_origin:acme','--limit','500']]*2


def test_failed_silver_is_held_and_never_replays_ingestion(tmp_path):
    journal=DeliveryJournal(tmp_path/'receipt.json',{})
    journal.stage('ingest:acme',lambda:dict(observed_jobs=2,inserted_jobs=2),effect=True)
    with pytest.raises(ValueError):
        journal.stage('silver:acme',lambda: (_ for _ in ()).throw(ValueError('failed')),effect=True)
    assert journal.data['stages']['ingest:acme']['state']=='SUCCEEDED'
    assert journal.data['stages']['silver:acme']['state']=='HELD'
    assert journal.stage('ingest:acme',lambda: pytest.fail('replayed'),effect=True)['observed_jobs']==2
