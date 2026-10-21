from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from scripts import run_product_v1_f5_mailbox_identity_backfill as backfill


def fixture():
    evidence = {'gmail-message:one': [{'title': 'Systemtester Maschinen- und Anlagentechnik (m/w/d)', 'employer': 'bundesdruckerei gruppe'}]}
    bindings = [{'source_identity_key': 'gmail-message:one', 'matched_application_id': 1, 'match_status': 'exact'}]
    apps = [{'id': 1, 'discovery_kind': 'mailbox_observed', 'silver_job_id': None,
        'job_identity_snapshot': {'employer_name': 'Bundesdruckerei-Gruppe', 'job_title': None},
        'provenance': {'operator_status': {'status': 'closed'}}}]
    return evidence, bindings, apps


def test_exact_message_binding_enriches_only_missing_title():
    evidence, bindings, apps = fixture()
    plan = backfill.build_plan(evidence, bindings, apps)
    assert len(plan['updates']) == 1
    assert plan['updates'][0]['source_identity_keys'] == ['gmail-message:one']
    assert apps[0]['job_identity_snapshot']['job_title'] is None


@pytest.mark.parametrize('variation', ['wrong_employer', 'conflicting_title', 'duplicate_binding', 'unmatched', 'manual_history', 'linked_silver'])
def test_uncertain_or_protected_identity_requires_review(variation):
    evidence, bindings, apps = fixture()
    if variation == 'wrong_employer': evidence['gmail-message:one'][0]['employer'] = 'another'
    if variation == 'conflicting_title': evidence['gmail-message:one'].append({'title': 'Data Engineer', 'employer': 'bundesdruckerei gruppe'})
    if variation == 'duplicate_binding': bindings.append(dict(bindings[0]))
    if variation == 'unmatched': bindings[0]['match_status'] = 'ambiguous'
    if variation == 'manual_history': apps[0]['provenance']['identity_corrections'] = [{'field': 'job_title'}]
    if variation == 'linked_silver': apps[0]['silver_job_id'] = 42
    plan = backfill.build_plan(evidence, bindings, apps)
    assert not plan['updates']
    assert plan['review']


@pytest.mark.parametrize('field', ['job_title', 'title', 'position'])
def test_any_existing_title_remains_unchanged(field):
    evidence, bindings, apps = fixture()
    apps[0]['job_identity_snapshot'][field] = 'Manual title'
    assert not backfill.build_plan(evidence, bindings, apps)['updates']


def test_apply_preserves_status_and_records_source_evidence():
    import json
    evidence, bindings, apps = fixture()
    plan = backfill.build_plan(evidence, bindings, apps)
    writes = []
    cursor = SimpleNamespace(execute=lambda sql, values: writes.append((sql, values)), rowcount=1)
    conn = SimpleNamespace(cursor=lambda: nullcontext(cursor))
    backfill.apply_updates(conn, plan, apps)
    assert len(writes) == 1
    snapshot, _, provenance, app_id = writes[0][1]
    assert app_id == 1
    assert json.loads(provenance)['operator_status'] == {'status': 'closed'}
    assert json.loads(provenance)['mailbox_identity_enrichments'][0]['source_identity_keys'] == ['gmail-message:one']
    assert json.loads(snapshot)['job_title'].startswith('Systemtester')
    assert 'lifecycle' not in writes[0][0]


def test_stale_identity_aborts_before_write():
    evidence, bindings, apps = fixture()
    plan = backfill.build_plan(evidence, bindings, apps)
    apps[0]['provenance']['operator_status'] = {'status': 'withdrawn'}
    with pytest.raises(RuntimeError, match='identity_changed'):
        backfill.apply_updates(None, plan, apps)


def test_only_explicit_subject_title_is_eligible():
    row = {'source_kind': 'gmail', 'mailbox_account_fingerprint': 'account', 'thread_reference': 'thread',
        'message_reference': 'message', 'observed_at': '2026-10-21T10:00:00+00:00',
        'subject': 'Ihre Bewerbung auf unsere Stelle Systemtester (m/w/d)', 'text_excerpt': 'Vielen Dank',
        'employer_name': 'Example', 'job_title': None}
    assert next(iter(backfill.input_titles([row]).values()))[0]['title'] == 'Systemtester (m/w/d)'
    assert backfill.input_titles([{**row, 'subject': 'Ihre Bewerbung', 'job_title': 'Guessed title'}]) == {}


def test_preflight_readonly_and_stale_apply_stop(monkeypatch, tmp_path):
    import psycopg
    from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig
    evidence, bindings, apps = fixture()
    input_path = tmp_path / 'normalized.jsonl'
    input_path.write_text('', encoding='utf-8')
    plan_path = tmp_path / 'plan.json'
    commands = []
    conn = SimpleNamespace(transaction=lambda: nullcontext(), execute=lambda sql: commands.append(sql))
    monkeypatch.setattr(psycopg, 'connect', lambda *a, **kw: nullcontext(conn))
    monkeypatch.setattr(DatabaseConfig, 'from_environment', lambda: SimpleNamespace(dsn=lambda: 'test'))
    monkeypatch.setattr(backfill, '_checkout_sha', lambda: 'source')
    monkeypatch.setattr(backfill, 'input_titles', lambda rows: evidence)
    monkeypatch.setattr(backfill, 'read_state', lambda *a, **kw: (bindings, apps))
    kwargs = dict(input_path=input_path, input_sha256=backfill._sha256_file(input_path), source_sha='source', plan_path=plan_path)
    report = backfill.run(**kwargs)
    assert report['database_writes'] == 0
    assert commands == ['SET TRANSACTION READ ONLY']
    apps[0]['job_identity_snapshot']['job_title'] = 'Operator filled meanwhile'
    with pytest.raises(RuntimeError, match='preflight_stale'):
        backfill.run(**kwargs, apply=True, expected_plan_sha256=report['plan_sha256'])
    assert commands[-1] == 'SET TRANSACTION ISOLATION LEVEL SERIALIZABLE'


def test_changed_input_rejected_before_database_access(monkeypatch, tmp_path):
    path = tmp_path / 'input.jsonl'
    path.write_text('', encoding='utf-8')
    monkeypatch.setattr(backfill, '_checkout_sha', lambda: 'source')
    with pytest.raises(RuntimeError, match='source_or_input_changed'):
        backfill.run(input_path=path, input_sha256='wrong', source_sha='source', plan_path=tmp_path/'plan')


def test_normal_sync_enrichment_uses_existing_transaction_without_git(monkeypatch):
    from scripts.product_v1_runtime_mailbox_sync import _enrich_missing_titles
    evidence, bindings, apps = fixture()
    connection = object()
    applied = []
    monkeypatch.setattr(backfill, 'input_titles', lambda rows: evidence)
    def read(conn, keys, *, lock):
        assert conn is connection and lock is True
        return bindings, apps
    monkeypatch.setattr(backfill, 'read_state', read)
    monkeypatch.setattr(backfill, '_checkout_sha', lambda: pytest.fail('runtime must not require Git'))
    monkeypatch.setattr(backfill, 'apply_updates', lambda conn, plan, rows: applied.extend(plan['updates']))
    assert _enrich_missing_titles(connection, []) == {'updated': 1, 'review_required': 0}
    assert len(applied) == 1
    apps[0]['job_identity_snapshot']['job_title'] = 'Manual correction'
    assert _enrich_missing_titles(connection, []) == {'updated': 0, 'review_required': 0}
    assert len(applied) == 1
