-- Complete, provenance-bound employer observations. No source activation or job filtering.
CREATE TABLE IF NOT EXISTS bronze_cloud_census_imports (
    population_digest text PRIMARY KEY CHECK (population_digest ~ '^[0-9a-f]{64}$'),
    census_run text NOT NULL UNIQUE,
    source_revision text NOT NULL CHECK (source_revision ~ '^[0-9a-f]{40}$'),
    payload jsonb NOT NULL,
    candidate_count integer NOT NULL CHECK (candidate_count > 0),
    imported_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS bronze_cloud_census_candidates (
    population_digest text NOT NULL REFERENCES bronze_cloud_census_imports(population_digest),
    cloud_company_key text NOT NULL,
    observation jsonb NOT NULL,
    classic_candidate_id bigint REFERENCES employer_origin_source_candidates(id),
    disposition text NOT NULL CHECK (disposition IN ('CREATED_DISCOVERY', 'EXISTING', 'IDENTITY_REVIEW')),
    PRIMARY KEY (population_digest, cloud_company_key)
);
