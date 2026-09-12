-- Bind a Silver processing decision to the recurring-observation evidence that
-- justified it.
--
-- Migrations 095/097 make the exact current recurring evidence + hash durable on
-- job_observations while raw_jobs intentionally stays deduplicated. A historical
-- Silver skip must therefore be reconsiderable when a later sighting carries
-- genuinely different evidence, without rewriting Bronze and without reprocessing
-- unchanged observations forever.
--
-- Historical decisions intentionally remain NULL. The bounded Silver loader may
-- reconsider a legacy missing-accessibility skip once a newer versioned observation
-- exists, then records the exact evidence basis used for the new decision.

ALTER TABLE silver_processing_decisions
    ADD COLUMN IF NOT EXISTS normalized_evidence_hash text,
    ADD COLUMN IF NOT EXISTS evidence_contract_version text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'silver_processing_decisions_evidence_basis_pair_check'
          AND conrelid = 'silver_processing_decisions'::regclass
    ) THEN
        ALTER TABLE silver_processing_decisions
        ADD CONSTRAINT silver_processing_decisions_evidence_basis_pair_check
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

COMMENT ON COLUMN silver_processing_decisions.normalized_evidence_hash IS
    'SHA-256 of the recurring observation evidence projection used for this Silver decision; NULL means legacy/original Bronze decision without a versioned observation basis.';

COMMENT ON COLUMN silver_processing_decisions.evidence_contract_version IS
    'Evidence projection contract version paired with normalized_evidence_hash; comparisons are meaningful only together.';
