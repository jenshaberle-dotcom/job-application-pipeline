#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$HOME/projects/job-application-pipeline"
LOG_DIR="$HOME/job-pipeline-logs"
LOCK_DIR="/tmp/job-pipeline-daily.lock"

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

cd "$PROJECT_DIR"

log "Activating virtual environment"
source .venv/bin/activate

log "Checking Docker/Postgres"
docker exec -i job_pipeline_postgres pg_isready -U job_user -d job_pipeline | tee -a "$LOG_FILE"

log "Running Bronze ingestion"
python -m src.ingest_jobs --log-level INFO 2>&1 | tee -a "$LOG_FILE"

log "Running Silver normalization"
python -m src.run_silver_jobs 2>&1 | tee -a "$LOG_FILE"

log "Creating source value snapshot"
python -m scripts.create_source_value_snapshot --reason scheduled_daily 2>&1 | tee -a "$LOG_FILE"

log "END daily job pipeline OK"
