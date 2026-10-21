import json
from src.connectors.workload_progress import WorkloadProgress
from src.connectors.classic_factory_delivery import DeliveryJournal

def test_heartbeat_does_not_claim_progress(tmp_path, monkeypatch):
    clock = iter([10, 11, 20])
    monkeypatch.setattr('src.connectors.workload_progress.time.time', lambda: next(clock))
    p = WorkloadProgress(tmp_path/'progress.json')
    p.publish('WORKING','ingest:test',changed=True)
    p.publish('WORKING','ingest:test')
    data = json.loads(p.path.read_text())
    assert data['updated_at'] == 20
    assert data['last_progress_at'] == 11
    assert data['completed'] == 0

def test_missing_telemetry_directory_does_not_fail_work(tmp_path):
    p = WorkloadProgress(tmp_path/'missing'/'progress.json')
    worker = p.begin('ingest:test')
    p.end('ingest:test', worker)
    assert not worker[1].is_alive()

def test_completion_published_after_durable_receipt(tmp_path, monkeypatch):
    journal = DeliveryJournal(tmp_path/'receipt.json', {})
    original = journal.progress.end
    def end(key, worker, failed=False):
        assert DeliveryJournal(journal.path, {}).data['stages'][key]['state'] == 'SUCCEEDED'
        original(key, worker, failed)
    monkeypatch.setattr(journal.progress, 'end', end)
    journal.stage('silver:test', lambda: {'included':1}, effect=True)
    assert json.loads(journal.progress.path.read_text())['completed'] == 1
