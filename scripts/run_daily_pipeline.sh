#!/usr/bin/env bash

set -uo pipefail

PROJECT_DIR="$HOME/projects/job-application-pipeline"
LOG_DIR="$HOME/job-pipeline-logs"
LOCK_DIR="/tmp/job-pipeline-daily.lock"
DB_READY_MAX_ATTEMPTS="${DB_READY_MAX_ATTEMPTS:-30}"
DB_READY_SLEEP_SECONDS="${DB_READY_SLEEP_SECONDS:-10}"

mkdir -p "$LOG_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/daily_pipeline_$TIMESTAMP.log"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') | $*" | tee -a "$LOG_FILE"
}

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log "ERROR another daily pipeline run appears to be active: $LOCK_DIR"
  exit 1
fi

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT

log "START daily job pipeline"
log "project_dir=$PROJECT_DIR"

cd "$PROJECT_DIR" || {
  log "ERROR project directory unavailable"
  exit 1
}

log "Activating virtual environment"
# shellcheck disable=SC1091
source .venv/bin/activate || {
  log "ERROR virtual environment activation failed"
  exit 1
}

DB_READY_EXIT=1
for ((attempt = 1; attempt <= DB_READY_MAX_ATTEMPTS; attempt++)); do
  log "Checking configured Postgres dependency attempt=$attempt/$DB_READY_MAX_ATTEMPTS"
  python - <<'PY' 2>&1 | tee -a "$LOG_FILE"
from src.config import get_database_config
import psycopg

config = get_database_config()
with psycopg.connect(**config, connect_timeout=10) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1
print("Postgres configured connection ready")
PY
  DB_READY_EXIT=${PIPESTATUS[0]}
  if [ "$DB_READY_EXIT" -eq 0 ]; then
    break
  fi
  if [ "$attempt" -lt "$DB_READY_MAX_ATTEMPTS" ]; then
    sleep "$DB_READY_SLEEP_SECONDS"
  fi
done

if [ "$DB_READY_EXIT" -ne 0 ]; then
  log "FAILED configured Postgres dependency unavailable after $DB_READY_MAX_ATTEMPTS attempts exit_code=$DB_READY_EXIT"
  exit "$DB_READY_EXIT"
fi

ORIGIN_EXIT=0
SENSOR_EXIT=0
SILVER_EXIT=0
SNAPSHOT_EXIT=0

log "Running employer-origin Bronze ingestion"
python -m src.ingest_jobs --role employer_origin --log-level INFO 2>&1 | tee -a "$LOG_FILE"
ORIGIN_EXIT=${PIPESTATUS[0]}
if [ "$ORIGIN_EXIT" -ne 0 ]; then
  log "WARN employer-origin ingestion degraded exit_code=$ORIGIN_EXIT; continuing so successful origin observations can reach Silver"
else
  log "Employer-origin ingestion completed"
fi

log "Running sensor Bronze ingestion"
python -m src.ingest_jobs --role sensor --log-level INFO 2>&1 | tee -a "$LOG_FILE"
SENSOR_EXIT=${PIPESTATUS[0]}
if [ "$SENSOR_EXIT" -ne 0 ]; then
  log "WARN sensor ingestion degraded exit_code=$SENSOR_EXIT; authoritative origin freshness will continue"
else
  log "Sensor ingestion completed"
fi

log "Running Silver normalization after all successful Bronze observations"
python -m src.run_silver_jobs 2>&1 | tee -a "$LOG_FILE"
SILVER_EXIT=${PIPESTATUS[0]}
if [ "$SILVER_EXIT" -ne 0 ]; then
  log "ERROR Silver normalization failed exit_code=$SILVER_EXIT"
else
  log "Silver normalization completed"
fi

if [ "$SILVER_EXIT" -eq 0 ]; then
  log "Creating source value snapshot"
  python -m scripts.create_source_value_snapshot --reason scheduled_daily 2>&1 | tee -a "$LOG_FILE"
  SNAPSHOT_EXIT=${PIPESTATUS[0]}
  if [ "$SNAPSHOT_EXIT" -ne 0 ]; then
    log "ERROR source value snapshot failed exit_code=$SNAPSHOT_EXIT"
  fi
else
  SNAPSHOT_EXIT=1
  log "SKIP source value snapshot because Silver normalization failed"
fi

log "component_status origin=$ORIGIN_EXIT sensor=$SENSOR_EXIT silver=$SILVER_EXIT snapshot=$SNAPSHOT_EXIT"

# Employer-origin freshness and Silver are the authoritative daily core. A sensor
# outage remains explicit evidence in ingestion_runs/logs but cannot suppress a
# successful origin observation from reaching Silver/current lifecycle truth.
if [ "$ORIGIN_EXIT" -ne 0 ] || [ "$SILVER_EXIT" -ne 0 ] || [ "$SNAPSHOT_EXIT" -ne 0 ]; then
  log "END daily job pipeline FAILED_AUTHORITATIVE_CORE"
  exit 1
fi

if [ "$SENSOR_EXIT" -ne 0 ]; then
  log "END daily job pipeline OK_WITH_SENSOR_DEGRADATION"
  exit 0
fi

log "END daily job pipeline OK"
exit 0
