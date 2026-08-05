-- APP-011A PRIVATE CANDIDATE FACT FOUNDATION
--
-- Local schema only. This migration does not insert personal candidate facts,
-- assess a job, change Product V1 readiness, call a provider, activate a
-- source, create a score, or perform an application action.

CREATE TABLE IF NOT EXISTS candidate_fact_profiles (
    profile_key TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    profile_version TEXT NOT NULL,
    status TEXT NOT NULL,
    payload JSONB NOT NULL,
    payload_sha256 TEXT NOT NULL,
    source_type TEXT NOT NULL,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_candidate_fact_profile_key
        CHECK (profile_key = 'default'),
    CONSTRAINT chk_candidate_fact_profile_schema_version
        CHECK (schema_version = 'candidate_fact_profile.v1'),
    CONSTRAINT chk_candidate_fact_profile_version
        CHECK (length(trim(profile_version)) > 0),
    CONSTRAINT chk_candidate_fact_profile_status
        CHECK (status IN ('draft', 'approved', 'superseded')),
    CONSTRAINT chk_candidate_fact_profile_payload_object
        CHECK (jsonb_typeof(payload) = 'object'),
    CONSTRAINT chk_candidate_fact_profile_sha256
        CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_candidate_fact_profile_source_type
        CHECK (source_type = 'local_private_json'),
    CONSTRAINT chk_candidate_fact_profile_approval
        CHECK (
            (status = 'approved'
                AND approved_by IS NOT NULL
                AND length(trim(approved_by)) > 0
                AND approved_at IS NOT NULL)
            OR
            (status <> 'approved')
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_candidate_fact_profile_version
ON candidate_fact_profiles (profile_version);

CREATE TABLE IF NOT EXISTS candidate_facts (
    profile_key TEXT NOT NULL
        REFERENCES candidate_fact_profiles(profile_key) ON DELETE CASCADE,
    fact_key TEXT NOT NULL,
    category TEXT NOT NULL,
    evidence_class TEXT NOT NULL,
    approval_status TEXT NOT NULL,
    statement TEXT NOT NULL,
    capability_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    limitations JSONB NOT NULL DEFAULT '[]'::jsonb,
    provenance JSONB NOT NULL,
    valid_from DATE,
    valid_until DATE,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    fact_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (profile_key, fact_key),
    CONSTRAINT chk_candidate_fact_key
        CHECK (length(trim(fact_key)) > 0),
    CONSTRAINT chk_candidate_fact_category
        CHECK (category IN (
            'employment', 'education', 'skill', 'project', 'certification',
            'preference', 'target_direction', 'boundary'
        )),
    CONSTRAINT chk_candidate_fact_evidence_class
        CHECK (evidence_class IN (
            'professional_employment', 'formal_education',
            'portfolio_implementation', 'training_certification',
            'operator_preference', 'target_direction', 'planned_capability'
        )),
    CONSTRAINT chk_candidate_fact_approval_status
        CHECK (approval_status IN ('proposed', 'approved', 'rejected', 'superseded')),
    CONSTRAINT chk_candidate_fact_statement
        CHECK (length(trim(statement)) > 0),
    CONSTRAINT chk_candidate_fact_capability_tags_array
        CHECK (jsonb_typeof(capability_tags) = 'array'),
    CONSTRAINT chk_candidate_fact_limitations_array
        CHECK (jsonb_typeof(limitations) = 'array'),
    CONSTRAINT chk_candidate_fact_provenance_array
        CHECK (jsonb_typeof(provenance) = 'array'),
    CONSTRAINT chk_candidate_fact_payload_object
        CHECK (jsonb_typeof(fact_payload) = 'object'),
    CONSTRAINT chk_candidate_fact_validity
        CHECK (
            valid_from IS NULL
            OR valid_until IS NULL
            OR valid_until >= valid_from
        ),
    CONSTRAINT chk_candidate_fact_approval
        CHECK (
            (approval_status = 'approved'
                AND approved_by IS NOT NULL
                AND length(trim(approved_by)) > 0
                AND approved_at IS NOT NULL)
            OR
            (approval_status <> 'approved')
        )
);

CREATE INDEX IF NOT EXISTS idx_candidate_facts_profile_evidence
ON candidate_facts (profile_key, evidence_class, approval_status, fact_key);

CREATE TABLE IF NOT EXISTS candidate_fact_profile_revisions (
    id BIGSERIAL PRIMARY KEY,
    profile_key TEXT NOT NULL,
    revision_key TEXT NOT NULL,
    previous_payload JSONB,
    next_payload JSONB NOT NULL,
    previous_sha256 TEXT,
    next_sha256 TEXT NOT NULL,
    applied_by TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_candidate_fact_profile_revision
        UNIQUE (profile_key, revision_key),
    CONSTRAINT chk_candidate_fact_revision_profile_key
        CHECK (profile_key = 'default'),
    CONSTRAINT chk_candidate_fact_revision_key
        CHECK (length(trim(revision_key)) > 0),
    CONSTRAINT chk_candidate_fact_revision_previous_object
        CHECK (
            previous_payload IS NULL
            OR jsonb_typeof(previous_payload) = 'object'
        ),
    CONSTRAINT chk_candidate_fact_revision_next_object
        CHECK (jsonb_typeof(next_payload) = 'object'),
    CONSTRAINT chk_candidate_fact_revision_previous_sha
        CHECK (
            previous_sha256 IS NULL
            OR previous_sha256 ~ '^[0-9a-f]{64}$'
        ),
    CONSTRAINT chk_candidate_fact_revision_next_sha
        CHECK (next_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_candidate_fact_revision_applied_by
        CHECK (length(trim(applied_by)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_candidate_fact_profile_revisions_profile
ON candidate_fact_profile_revisions (profile_key, applied_at DESC, id DESC);
