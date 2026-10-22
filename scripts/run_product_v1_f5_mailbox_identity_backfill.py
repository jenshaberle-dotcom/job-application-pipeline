"""Explicit, message-bound missing-title enrichment; never rematch or change status."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.product_v1_f5_mailbox_ingest import canonical_sha256, parse_normalized_mailbox_observation, source_message_identity_key
from scripts.run_product_mailbox_bridge import enrich_identity
from scripts.run_product_v1_f5_mailbox_batch_preflight import load_jsonl
from scripts.run_product_v1_f5_mailbox_identity_enrichment_preflight import _clean
from scripts.run_product_v1_f5_mailbox_persistence_apply import _checkout_sha, _sha256_file
from src.search_intelligence.application_identity_matching import normalize_company


def input_titles(rows):
    """Only an explicit subject role is eligible, bound to the original message."""
    evidence = defaultdict(list)
    for row in rows:
        observation = parse_normalized_mailbox_observation(row)
        enriched = enrich_identity({**row, 'job_title': None})
        title = _clean(enriched.get('job_title'))
        if title:
            evidence[source_message_identity_key(observation)].append({
                'title': title, 'employer': normalize_company(enriched.get('employer_name')),
            })
    return dict(evidence)


def build_plan(evidence, bindings, applications):
    proposed = defaultdict(list)
    review = []
    for source_key, values in sorted(evidence.items()):
        matches = [r for r in bindings if r['source_identity_key'] == source_key]
        if len(matches) != 1 or matches[0].get('match_status') != 'exact' or not matches[0].get('matched_application_id'):
            review.append({'source_identity_key': source_key, 'reason': 'message_binding_not_unique_exact'})
            continue
        application_id = int(matches[0]['matched_application_id'])
        for value in values:
            proposed[application_id].append({**value, 'source_identity_key': source_key})
    updates = []
    by_id = {int(a['id']): a for a in applications}
    for application_id, values in sorted(proposed.items()):
        app = by_id.get(application_id)
        if not app or app.get('discovery_kind') != 'mailbox_observed' or app.get('silver_job_id') is not None:
            review.append({'application_id': application_id, 'reason': 'not_unlinked_mailbox_application'})
            continue
        snapshot = app.get('job_identity_snapshot') or {}
        provenance = app.get('provenance') or {}
        if any(_clean(snapshot.get(k)) for k in ('job_title', 'title', 'position')):
            continue
        if any(r.get('field') == 'job_title' for r in provenance.get('identity_corrections', [])):
            review.append({'application_id': application_id, 'reason': 'operator_title_history_preserved'})
            continue
        company = normalize_company(snapshot.get('employer_name') or snapshot.get('company_name') or snapshot.get('company'))
        titles = {v['title'] for v in values}
        if not company or any(v['employer'] != company for v in values) or len(titles) != 1:
            review.append({'application_id': application_id, 'reason': 'conflicting_or_missing_identity'})
            continue
        updates.append({'application_id': application_id, 'job_title': next(iter(titles)),
            'expected_identity_sha256': canonical_sha256(snapshot),
            'expected_provenance_sha256': canonical_sha256(provenance),
            'source_identity_keys': sorted({v['source_identity_key'] for v in values})})
    return {'updates': updates, 'review': review}


def read_state(conn, keys, *, lock=False):
    with conn.cursor() as cur:
        cur.execute("SELECT source_identity_key, matched_application_id, match_status FROM application_event_candidates "
            "WHERE source_kind = 'gmail' AND is_active AND source_identity_key = ANY(%s) ORDER BY id" + (' FOR UPDATE' if lock else ''), (keys,))
        bindings = list(cur.fetchall())
        ids = sorted({int(r['matched_application_id']) for r in bindings if r['matched_application_id'] is not None})
        cur.execute("SELECT id, discovery_kind, silver_job_id, job_identity_snapshot, provenance FROM applications "
            "WHERE id = ANY(%s) ORDER BY id" + (' FOR UPDATE' if lock else ''), (ids,))
        return bindings, list(cur.fetchall())


def apply_updates(conn, plan, applications):
    by_id = {int(a['id']): a for a in applications}
    for update in plan['updates']:
        app = by_id[update['application_id']]
        snapshot = dict(app['job_identity_snapshot'])
        provenance = dict(app.get('provenance') or {})
        if canonical_sha256(snapshot) != update['expected_identity_sha256'] or canonical_sha256(provenance) != update['expected_provenance_sha256']:
            raise RuntimeError('identity_changed_refresh_preflight')
        if any(_clean(snapshot.get(k)) for k in ('job_title', 'title', 'position')):
            raise RuntimeError('existing_title_preserved')
        snapshot['job_title'] = update['job_title']
        history = list(provenance.get('mailbox_identity_enrichments', []))
        history.append({**update, 'authority': 'exact_message_subject_evidence',
            'recorded_at': datetime.now(timezone.utc).isoformat()})
        provenance['mailbox_identity_enrichments'] = history
        with conn.cursor() as cur:
            cur.execute('UPDATE applications SET job_identity_snapshot = %s::jsonb, job_identity_sha256 = %s, provenance = %s::jsonb WHERE id = %s',
                (json.dumps(snapshot, ensure_ascii=False), canonical_sha256(snapshot), json.dumps(provenance, ensure_ascii=False), update['application_id']))
            if cur.rowcount != 1:
                raise RuntimeError('application_update_count_mismatch')


def run(*, input_path, input_sha256, source_sha, plan_path, apply=False, expected_plan_sha256=None):
    if _checkout_sha() != source_sha or _sha256_file(input_path) != input_sha256:
        raise RuntimeError('source_or_input_changed')
    evidence = input_titles(load_jsonl(input_path))
    expected = None
    if apply:
        if not expected_plan_sha256 or _sha256_file(plan_path) != expected_plan_sha256:
            raise RuntimeError('preflight_plan_hash_mismatch')
        expected = json.loads(plan_path.read_text(encoding='utf-8'))
    import psycopg
    from psycopg.rows import dict_row
    from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig
    with psycopg.connect(DatabaseConfig.from_environment().dsn(), row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE' if apply else 'SET TRANSACTION READ ONLY')
            bindings, applications = read_state(conn, sorted(evidence), lock=apply)
            plan = {'schema': 'jap.f5.mailbox_identity_backfill.v1', 'source_sha': source_sha,
                'input_sha256': input_sha256, **build_plan(evidence, bindings, applications)}
            if apply:
                if plan != expected:
                    raise RuntimeError('preflight_stale_rebuild_required')
                apply_updates(conn, plan, applications)
    if not apply:
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return {'status': 'APPLIED' if apply else 'PREFLIGHT_PASS', 'planned_updates': len(plan['updates']),
        'review_required': len(plan['review']), 'database_writes': len(plan['updates']) if apply else 0,
        'gmail_requests': 0, 'lifecycle_mutations': 0, 'plan_sha256': _sha256_file(plan_path)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--expected-input-sha256', required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-plan-sha256')
    args = parser.parse_args()
    result = run(input_path=args.input, input_sha256=args.expected_input_sha256, source_sha=args.source_sha,
        plan_path=args.plan, apply=args.apply, expected_plan_sha256=args.expected_plan_sha256)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
