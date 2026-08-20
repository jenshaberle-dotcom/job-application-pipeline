ALTER TABLE ingestion_runs
ADD COLUMN IF NOT EXISTS connector_record_count INTEGER;

ALTER TABLE ingestion_runs
ADD COLUMN IF NOT EXISTS post_filter_count INTEGER;

ALTER TABLE ingestion_runs
DROP CONSTRAINT IF EXISTS ingestion_runs_connector_record_count_nonnegative;

ALTER TABLE ingestion_runs
ADD CONSTRAINT ingestion_runs_connector_record_count_nonnegative
CHECK (connector_record_count IS NULL OR connector_record_count >= 0);

ALTER TABLE ingestion_runs
DROP CONSTRAINT IF EXISTS ingestion_runs_post_filter_count_nonnegative;

ALTER TABLE ingestion_runs
ADD CONSTRAINT ingestion_runs_post_filter_count_nonnegative
CHECK (post_filter_count IS NULL OR post_filter_count >= 0);

ALTER TABLE ingestion_runs
DROP CONSTRAINT IF EXISTS ingestion_runs_stage_count_order;

ALTER TABLE ingestion_runs
ADD CONSTRAINT ingestion_runs_stage_count_order
CHECK (
    connector_record_count IS NULL
    OR post_filter_count IS NULL
    OR post_filter_count <= connector_record_count
);
