"""Local, reversible operator decisions; never sends an employer message."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from typing import Mapping

STATUSES = frozenset({'closed', 'withdrawn', 'rejected', 'interview', 'automatic'})

@dataclass(frozen=True)
class OperatorStatusRequest:
    application_id: int
    status: str
    reason: str
    expected_identity_sha256: str
    expected_revision: int
    request_id: str

def parse_operator_status(payload):
    from scripts.product_v1_f5_application_actions import ApplicationActionError
    try:
        app_id = int(payload['application_id'])
        revision = int(payload['expected_revision'])
    except (KeyError, TypeError, ValueError) as exc:
        raise ApplicationActionError('invalid_status_identity') from exc
    status = str(payload.get('status', ''))
    reason = str(payload.get('reason', '')).strip()
    identity = str(payload.get('expected_identity_sha256', ''))
    request_id = str(payload.get('request_id', ''))
    if (app_id < 1 or revision < 0 or status not in STATUSES or not 1 <= len(reason) <= 1000
        or not re.fullmatch('[0-9a-f]{64}', identity)
        or not re.fullmatch('[a-zA-Z0-9-]{16,64}', request_id)):
        raise ApplicationActionError('invalid_operator_status')
    return OperatorStatusRequest(app_id, status, reason, identity, revision, request_id)

def status_history(provenance):
    if not isinstance(provenance, Mapping):
        return []
    events = provenance.get('operator_status_events', [])
    return events if isinstance(events, list) else []

def append_status(provenance, snapshot, request):
    from scripts.product_v1_f5_application_actions import ApplicationActionError, canonical_sha256
    history = status_history(provenance)
    for event in history:
        if event.get('request_id') == request.request_id:
            if event.get('status') != request.status or event.get('reason') != request.reason:
                raise ApplicationActionError('status_request_conflict')
            return dict(provenance), False
    if canonical_sha256(snapshot) != request.expected_identity_sha256 or len(history) != request.expected_revision:
        raise ApplicationActionError('application_identity_changed_refresh_required')
    event = {'status': request.status, 'reason': request.reason, 'request_id': request.request_id,
             'identity_sha256': request.expected_identity_sha256, 'authority': 'explicit_operator_confirmation',
             'recorded_at': datetime.now(timezone.utc).isoformat()}
    return {**dict(provenance or {}), 'operator_status_events': [*history, event]}, True

def record_operator_status(request):
    import psycopg
    from psycopg.rows import dict_row
    from scripts.product_v1_f5_application_actions import ApplicationActionError, DatabaseConfig
    with psycopg.connect(DatabaseConfig.from_environment().dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT job_identity_snapshot, provenance FROM applications WHERE id=%s FOR UPDATE', (request.application_id,))
            row = cur.fetchone()
            if row is None:
                raise ApplicationActionError('application_not_found')
            provenance, changed = append_status(row['provenance'], row['job_identity_snapshot'], request)
            if changed:
                cur.execute('UPDATE applications SET provenance=%s WHERE id=%s', (json.dumps(provenance), request.application_id))
    return {'status': 'saved' if changed else 'already_saved', 'application_id': request.application_id,
            'external_submission_action': False, 'database_writes': int(changed)}
