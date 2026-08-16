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

COMMENT ON COLUMN job_observations.normalized_evidence IS
    'Exact versioned per-sighting recurring evidence projection whose canonical SHA-256 is stored in normalized_evidence_hash. Historical rows remain NULL when the original sighting projection was not persisted.';
