from datetime import UTC, datetime

import pytest

from scripts.run_classic_connector_factory import reconcile_ingestion, verify_ingestion_receipt
from src.connectors.classic_factory_delivery import DeliveryJournal


class Database:
    def __init__(self, *, loaded=2):
        self.runs = [{'id': 71, 'status': 'success', 'finished_at': datetime.now(UTC),
                      'total_loaded': loaded, 'inserted_count': loaded, 'duplicate_count': 0,
                      'source_name': 'generic_origin:acme', 'profile_name': 'generic_origin__acme',
                      'search_profile_id': 17, 'search_term_id': 18, 'search_term': '*'}]
        self.observations = [{'ingestion_run_id': 71, 'observations': loaded, 'verified': loaded}]
        self.queries = []

    def transaction(self):
        return self

    def cursor(self, **kw):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        assert sql.startswith(('SELECT ', 'SET TRANSACTION '))
        self.queries.append(sql)
        return self

    def fetchall(self):
        return self.observations if 'job_observations' in self.queries[-1] else self.runs


EXPECTED = {'profile_id': 17, 'term_ids': [18]}


@pytest.mark.parametrize('loaded', [0, 2])
def test_exact_success_with_matching_physical_observations_is_recoverable(loaded):
    assert verify_ingestion_receipt(Database(loaded=loaded), [71], 'acme', EXPECTED) == {
        'ingestion_run_ids': [71], 'observed_jobs': loaded, 'inserted_jobs': loaded,
    }


@pytest.mark.parametrize('field,value', [
    ('id', 72), ('status', 'running'), ('status', 'failed'), ('finished_at', None),
    ('source_name', 'generic_origin:other'), ('profile_name', 'generic_origin__other'),
    ('search_profile_id', 19), ('search_term_id', 19), ('search_term', 'changed'),
    ('inserted_count', 1), ('duplicate_count', -1), ('total_loaded', None),
])
def test_incomplete_foreign_or_inconsistent_run_cannot_be_reconciled(field, value):
    db = Database()
    db.runs[0][field] = value
    with pytest.raises(RuntimeError):
        verify_ingestion_receipt(db, [71], 'acme', EXPECTED)


@pytest.mark.parametrize('ids', [[], [71, 71], [True], [-1]])
def test_missing_or_duplicate_receipt_ids_remain_unresolved(ids):
    with pytest.raises(ValueError):
        verify_ingestion_receipt(Database(), ids, 'acme', EXPECTED)


@pytest.mark.parametrize('field', ['observations', 'verified'])
def test_raw_job_lineage_or_observation_count_mismatch_is_not_success(field):
    db = Database()
    db.observations[0][field] = 1
    with pytest.raises(RuntimeError, match='observation_receipt_mismatch'):
        verify_ingestion_receipt(db, [71], 'acme', EXPECTED)


def test_exact_reconciliation_preserves_audit_and_resume_never_calls_acquisition(tmp_path):
    journal = DeliveryJournal(tmp_path / 'receipt.json', {})
    journal.data['stages']['ingest:acme'] = {
        'state': 'HELD', 'effect': True, 'ingestion_run_ids': [71],
        'expected_ingestion': EXPECTED, 'error_type': 'TimeoutError',
    }
    journal.data['stages']['activate'] = {'state': 'HELD', 'effect': True}
    journal.save()
    result = reconcile_ingestion(Database(), journal)
    assert result['resolved_stages'] == ['ingest:acme']
    assert result['unresolved_stages'] == ['activate']
    restored = DeliveryJournal(journal.path, {})
    stage = restored.data['stages']['ingest:acme']
    assert stage['error_type'] == 'TimeoutError'
    assert stage['reconciliation']['previous_state'] == 'HELD'
    assert restored.stage('ingest:acme', lambda: pytest.fail('replayed'), effect=True)['observed_jobs'] == 2


def test_old_receipt_without_expected_term_scope_is_not_guessed(tmp_path):
    journal = DeliveryJournal(tmp_path / 'receipt.json', {})
    journal.data['stages']['ingest:acme'] = {'state': 'HELD', 'effect': True, 'ingestion_run_ids': [71]}
    assert reconcile_ingestion(Database(), journal)['unresolved_stages'] == ['ingest:acme']
    assert journal.data['stages']['ingest:acme']['state'] == 'HELD'
