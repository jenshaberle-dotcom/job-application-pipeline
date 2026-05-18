ALTER TABLE ingestion_runs
ADD COLUMN IF NOT EXISTS search_term_id BIGINT REFERENCES search_terms(id);

ALTER TABLE ingestion_runs
ADD COLUMN IF NOT EXISTS search_term TEXT;

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_search_term_id
ON ingestion_runs (search_term_id);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_search_term
ON ingestion_runs (search_term);
