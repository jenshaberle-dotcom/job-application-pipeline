CREATE TABLE IF NOT EXISTS generic_employer_origin_active_sources (
    candidate_id INTEGER PRIMARY KEY
        REFERENCES employer_origin_source_candidates(id) ON DELETE RESTRICT,
    company_key TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL UNIQUE,
    authority TEXT NOT NULL
        CHECK (authority = 'generic_evidence_driven_layer_model'),
    proof_state TEXT NOT NULL
        CHECK (proof_state = 'pass'),
    proof_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    activated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (source_name = 'generic_origin:' || company_key)
);

COMMENT ON TABLE generic_employer_origin_active_sources IS
    'Materialized current proof=PASS projection from the sole generic Employer-Origin layer model; not an independent admission authority.';
COMMENT ON COLUMN generic_employer_origin_active_sources.proof_evidence IS
    'Evidence copied from the current generic proof layer that caused source admission.';
