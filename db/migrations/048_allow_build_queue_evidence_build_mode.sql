-- S7Q Allow Build Queue Evidence Build Mode
--
-- Purpose:
--   Allow approval-gated connector build requests to persist the S7O-derived
--   connector_candidate_from_build_queue_evidence build mode.
--
-- Boundary:
--   Schema contract update only. This migration does not build connector
--   artifacts, register connectors, activate sources, write Bronze records
--   or change scheduler configuration.

ALTER TABLE IF EXISTS employer_origin_connector_build_requests
    DROP CONSTRAINT IF EXISTS chk_employer_origin_connector_build_mode;

ALTER TABLE IF EXISTS employer_origin_connector_build_requests
    ADD CONSTRAINT chk_employer_origin_connector_build_mode
    CHECK (build_mode = ANY (ARRAY[
        'none'::text,
        'connector_candidate_from_gate_evidence'::text,
        'connector_candidate_from_build_queue_evidence'::text,
        'bounded_investigation_connector'::text,
        'existing_artifacts'::text
    ])) NOT VALID;
