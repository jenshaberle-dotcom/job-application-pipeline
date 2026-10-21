from argparse import Namespace

import pytest

from src.connectors.classic_factory_delivery import (
    DeliveryJournal, ReconciliationRequired, delivery_summary,
)
from scripts import run_classic_connector_factory as runner


def test_effect_intent_is_durable_before_call_and_completed_stage_is_not_repeated(tmp_path):
    journal = DeliveryJournal(tmp_path / 'receipt.json', {'sha': 'a'})
    calls = []

    def operation():
        assert DeliveryJournal(journal.path, {'sha': 'a'}).data['stages']['activate']['state'] == 'RUNNING'
        calls.append(1)
        return {'qualified_sources': 3}

    journal.stage('activate', operation, effect=True)
    restored = DeliveryJournal(journal.path, {'sha': 'a'})
    assert restored.stage('activate', operation, effect=True) == {'qualified_sources': 3}
    assert calls == [1]


@pytest.mark.parametrize('state', ['RUNNING', 'HELD'])
def test_restart_preserves_uncertain_effect_without_call(tmp_path, state):
    journal = DeliveryJournal(tmp_path / 'receipt.json', {})
    journal.data['stages']['activate'] = {'state': state, 'effect': True}
    journal.save()
    with pytest.raises(ReconciliationRequired):
        DeliveryJournal(journal.path, {}).stage('activate', lambda: pytest.fail('replay'), effect=True)


def test_post_effect_timeout_is_held_and_secret_text_is_not_persisted(tmp_path):
    journal = DeliveryJournal(tmp_path / 'receipt.json', {})

    def timeout():
        raise TimeoutError('password=secret')

    with pytest.raises(TimeoutError):
        journal.stage('ingest:acme', timeout, effect=True)
    assert journal.data['stages']['ingest:acme']['state'] == 'HELD'
    assert all('secret' not in p.read_text() for p in journal.stage_dir.glob('*.json'))


def test_interrupted_read_only_qualification_can_resume(tmp_path):
    journal = DeliveryJournal(tmp_path / 'receipt.json', {})
    journal.data['stages']['qualify:a'] = {'state': 'RUNNING', 'effect': False}
    journal.save()
    assert journal.stage('qualify:a', lambda: {'ok': True}, effect=False) == {'ok': True}


def test_changed_source_population_or_database_binding_fails_closed(tmp_path):
    journal = DeliveryJournal(tmp_path / 'receipt.json', {'database': 'a'})
    journal.save()
    with pytest.raises(ValueError, match='binding_changed'):
        DeliveryJournal(journal.path, {'database': 'b'})


@pytest.mark.parametrize('loaded', [0, 7])
def test_bronze_is_not_profile_relevance_or_end_to_end_acceptance(loaded):
    summary = delivery_summary({'ingest:a': {'state': 'SUCCEEDED', 'result': {
        'observed_jobs': loaded, 'inserted_jobs': 0,
    }}}, 1735)
    assert summary['bronze_delivery_proven'] is bool(loaded)
    assert summary['e2e_accepted'] is False
    assert summary['profile_relevance_proven'] is False


class FakeConnection:
    def transaction(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def prepare(monkeypatch, tmp_path, count):
    monkeypatch.setattr(runner, 'promote_silver', lambda key: dict(selected=0,included=0,skipped=0,completed=True))
    rows = [{'id': i + 1, 'company_key': f'company-{i}'} for i in range(count)]
    monkeypatch.setattr(runner, 'qualify', lambda row, args: {
        'candidate_id': row['id'], 'company_key': row['company_key'],
        'layers': [{'layer': 'proof', 'state': 'pass'}],
    })
    monkeypatch.setattr(runner.activation, '_resolve_projection_origins', lambda *a: {})
    monkeypatch.setattr(runner.activation, 'apply_activation', lambda *a, **kw: None)
    monkeypatch.setattr(runner, 'verify_activation', lambda *a: None)
    monkeypatch.setattr(runner.activation, '_current_generic_profile_count', lambda *a: count)
    monkeypatch.setattr(runner.activation, '_current_projection_count', lambda *a: count)
    journal = DeliveryJournal(tmp_path / 'receipt.json', {})
    return rows, journal, Namespace(state_dir=tmp_path)


def test_entire_population_runs_without_small_pilot_and_resume_skips_effects(monkeypatch, tmp_path):
    rows, journal, args = prepare(monkeypatch, tmp_path, 1735)
    # Persistence semantics are tested separately above; avoid quadratic disk IO here.
    monkeypatch.setattr(journal, 'save', lambda *a: None)
    seen = []

    def ingest(key, journal):
        seen.append(key)
        return {'observed_jobs': 1, 'inserted_jobs': 1}

    monkeypatch.setattr(runner, 'ingest', ingest)
    report = runner.execute(FakeConnection(), rows, journal, args)
    assert len(seen) == report['sources_ingested'] == report['population_count'] == 1735
    runner.execute(FakeConnection(), rows, journal, args)
    assert len(seen) == 1735


def test_failed_source_is_held_remaining_sources_continue(monkeypatch, tmp_path):
    rows, journal, args = prepare(monkeypatch, tmp_path, 3)

    def ingest(key, journal):
        if key == 'company-1':
            raise TimeoutError()
        return {'observed_jobs': 2, 'inserted_jobs': 1}

    monkeypatch.setattr(runner, 'ingest', ingest)
    report = runner.execute(FakeConnection(), rows, journal, args)
    assert report['observed_jobs'] == 4
    assert report['held_stages'] == ['ingest:company-1']
    assert report['e2e_accepted'] is False


def test_qualification_exception_remains_reported_and_unproven_sources_never_activate(monkeypatch, tmp_path):
    rows, journal, args = prepare(monkeypatch, tmp_path, 3)
    seen = []

    def qualify(row, args):
        seen.append(row['id'])
        if row['id'] == 2:
            raise TimeoutError()
        return {'company_key': row['company_key']}

    monkeypatch.setattr(runner, 'qualify', qualify)
    monkeypatch.setattr(runner.activation, 'apply_activation', lambda *a: pytest.fail('partial activation'))
    result = runner.execute(FakeConnection(), rows, journal, args)
    assert result['qualification_errors'] == ['company-1']
    assert result['qualified_sources'] == 0
    assert seen == [1, 2, 3]


def test_database_configuration_gate_does_not_attempt_implicit_local_connection(monkeypatch):
    monkeypatch.setattr(runner, 'get_database_config', lambda: {'host': None})
    monkeypatch.setattr(runner.psycopg, 'connect', lambda **kw: pytest.fail('implicit DB'))
    with pytest.raises(RuntimeError, match='HOST_DATABASE_CONFIGURATION_MISSING'):
        with runner.database_session():
            pass


@pytest.mark.parametrize('preserve', [True, False])
def test_additive_activation_preserves_unproved_existing_sources(monkeypatch, preserve):
    from scripts import apply_generic_employer_origin_activation as activation

    class Cursor:
        def __init__(self):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            self.calls.append((sql, params))

        def fetchone(self):
            return {'id': 17}

    class Connection:
        def __init__(self):
            self.cur = Cursor()

        def cursor(self):
            return self.cur

    conn = Connection()
    monkeypatch.setattr(activation, '_relation_exists', lambda *a: True)
    activation.apply_activation(conn, [{
        'candidate_id': 17, 'company_key': 'acme',
        'layers': [{'layer': 'proof', 'state': 'pass'}],
    }], {17: 'https://acme.test/careers'}, preserve_existing=preserve)
    queries = [sql for sql, params in conn.cur.calls]
    assert any('DELETE FROM generic_employer_origin_active_sources' in sql for sql in queries) is (not preserve)
    assert any("SET status = 'candidate'" in sql for sql in queries) is (not preserve)
    assert any('source_name <> ALL' in sql for sql in queries) is (not preserve)
    retire_params = next(params for sql, params in conn.cur.calls if 'WHERE source_name LIKE' in sql)
    assert retire_params[1] is (not preserve)
    assert retire_params[2] == ['generic_origin:acme']
