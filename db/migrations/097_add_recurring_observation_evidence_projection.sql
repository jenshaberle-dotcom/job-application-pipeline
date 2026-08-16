-- Persist the exact per-sighting recurring evidence projection used for hashing.
--
-- Migrations 095/096 established truthful observation hashes and execution
-- correlation, but repeated source-local identities keep raw_jobs deduplicated.
-- A later observation can therefore carry a new hash while its raw_job_id still
-- points at the first Bronze row. This additive column makes the exact current
-- evidence projection durable on the observation itself.
--
-- Historical rows intentionally remain NULL. No evidence can be reconstructed
-- truthfully from an old raw_jobs row or from the hash alone.

ALTER TABLE job_observations
    ADD COLUMN IF NOT EXISTS normalized_evidence jsonb;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'job_observations_normalized_evidence_shape_check'
          AND conrelid = 'job_observations'::regclass
    ) THEN
        ALTER TABLE job_observations
        ADD CONSTRAINT job_observations_normalized_evidence_shape_check
        CHECK (
            normalized_evidence IS NULL
            OR (
                jsonb_typeof(normalized_evidence) = 'object'
                AND normalized_evidence ? 'source_url'
                AND normalized_evidence ? 'raw_evidence'
                AND jsonb_typeof(normalized_evidence -> 'source_url') = 'string'
                AND jsonb_typeof(normalized_evidence -> 'raw_evidence') = 'object'
            )
        );
    END IF;
END;
$$;

COMMENT ON COLUMN job_observations.normalized_evidence IS
    'Exact versioned per-sighting recurring evidence projection whose canonical SHA-256 is stored in normalized_evidence_hash. Historical rows remain NULL when the original sighting projection was not persisted.';
