-- SUCCESSFACTORS-MULTI-LOCATION-001A
--
-- Preserve one-to-many employer-origin location evidence without changing the
-- legacy singular silver_jobs.city field or existing canonical key semantics.
--
-- Boundary:
--   - schema only; no source activation or scheduler mutation
--   - no automatic backfill or network request
--   - exact controlled backfills use an approval-gated runtime script

CREATE TABLE IF NOT EXISTS silver_job_locations (
    id BIGSERIAL PRIMARY KEY,
    silver_job_id BIGINT NOT NULL
        REFERENCES silver_jobs(id) ON DELETE CASCADE,
    city TEXT NOT NULL,
    country_code TEXT NOT NULL DEFAULT 'DE',
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    evidence_source TEXT NOT NULL,
    evidence_text TEXT NOT NULL,
    observed_at_utc TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_silver_job_locations_city_not_blank
        CHECK (length(trim(city)) > 0),
    CONSTRAINT chk_silver_job_locations_country_code
        CHECK (country_code ~ '^[A-Z]{2}$'),
    CONSTRAINT chk_silver_job_locations_evidence_source
        CHECK (length(trim(evidence_source)) > 0),
    CONSTRAINT chk_silver_job_locations_evidence_text
        CHECK (length(trim(evidence_text)) > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_silver_job_locations_identity
    ON silver_job_locations (
        silver_job_id,
        lower(trim(city)),
        lower(trim(country_code))
    );

CREATE INDEX IF NOT EXISTS idx_silver_job_locations_city_country
    ON silver_job_locations (
        lower(trim(city)),
        lower(trim(country_code)),
        silver_job_id
    );

CREATE UNIQUE INDEX IF NOT EXISTS uq_silver_job_locations_one_primary
    ON silver_job_locations (silver_job_id)
    WHERE is_primary;
