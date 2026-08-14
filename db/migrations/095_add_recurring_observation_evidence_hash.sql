-- Persist truthful per-sighting evidence fingerprints for recurring connectors.
--
-- Runtime Issue #137 proved that repeated job_observations are abundant but the
-- historical schema stores neither the current observation payload nor a hash of
-- it. Existing raw_jobs.content_hash cannot repair that history because duplicate
-- Bronze inserts are intentionally not rewritten.
--
-- This migration is deliberately additive and does NOT backfill old observations:
-- historical repeated payloads cannot be reconstructed truthfully. New ingestion
-- code writes the exact current evidence hash + evidence projection contract for
-- every future sighting, including sightings of an already-known raw job.
--
-- Boundary: observability only. No lifecycle, Silver, ranking, application,
-- source-activation or scheduler state is changed here.

ALTER TABLE job_observations
    ADD COLUMN IF NOT EXISTS normalized_evidence_hash text,
    ADD COLUMN IF NOT EXISTS evidence_contract_version text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'job_observations_evidence_hash_contract_pair_check'
          AND conrelid = 'job_observations'::regclass
    ) THEN
        ALTER TABLE job_observations
        ADD CONSTRAINT job_observations_evidence_hash_contract_pair_check
        CHECK (
            (normalized_evidence_hash IS NULL AND evidence_contract_version IS NULL)
            OR
            (
                normalized_evidence_hash ~ '^[0-9a-f]{64}$'
                AND NULLIF(BTRIM(evidence_contract_version), '') IS NOT NULL
            )
        );
    END IF;
END;
$$;

COMMENT ON COLUMN job_observations.normalized_evidence_hash IS
    'SHA-256 of the exact current recurring-observation evidence projection. Historical rows remain NULL when no truthful per-sighting payload can be reconstructed.';

COMMENT ON COLUMN job_observations.evidence_contract_version IS
    'Version of the evidence projection used for normalized_evidence_hash; comparisons are valid only within the same contract version.';
