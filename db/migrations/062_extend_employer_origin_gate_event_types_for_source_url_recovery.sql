-- A1f5: allow bounded source URL recovery events in gate-event audit history.
-- This keeps source URL recovery DB-backed and auditable instead of hiding it in logs.

ALTER TABLE employer_origin_candidate_gate_events
    DROP CONSTRAINT IF EXISTS employer_origin_candidate_gate_events_event_type_check;

ALTER TABLE employer_origin_candidate_gate_events
    ADD CONSTRAINT employer_origin_candidate_gate_events_event_type_check
    CHECK (event_type IN (
        'candidate_created',
        'gate_initialized',
        'gate_updated',
        'candidate_status_updated',
        'candidate_url_recovered'
    ));
