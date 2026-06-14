
# PROVIDER-001B Provider Evidence Discovery

Status: implemented foundation
Boundary: `review_output_only_not_pipeline_input`

PROVIDER-001B is a read-only evidence discovery report for the
`provider_backed_origin_coverage` gap in the generics-first path. It scans
existing repository/database evidence for ATS/provider-backed origin signals,
for example Personio, Greenhouse, Workday, SuccessFactors, SmartRecruiters,
Lever, Ashby, Recruitee, Workable, Softgarden, d.vinci, onlyfy and similar
providers.

## What it is allowed to do

- Read existing local DB evidence in a read-only transaction when `--include-db`
  is passed and a DSN is available.
- Classify provider-like URL, host and source/evidence text signals.
- Write JSON/Markdown review artifacts under `exports/`.
- Recommend the next review work item: PROVIDER-001C Provider Coverage Decision
  Bundle.

## What it must not do

- It must not call external URLs.
- It must not write to the database.
- It must not approve, reject, create or activate candidates, gates, connectors,
  Bronze, Silver or Gold state.
- It must not treat generated exports as pipeline inputs.

## Operator command

    python scripts/run_provider001b_provider_evidence_discovery.py --include-db

For a curated run-scoped output folder:

    stamp="$(date +%Y%m%d-%H%M%S)"
    out="exports/provider001b_validation_${stamp}"
    mkdir -p "$out"
    python scripts/run_provider001b_provider_evidence_discovery.py --include-db --output-dir "$out"

## Interpretation

The report can demonstrate that existing data already contains provider-backed
origin signals. It does not prove current reachability. If current reachability
is required, a later bounded external probe must first pass COMPLIANCE-001A Probe
Boundary Matrix and remain separate from this read-only report.


## DB-backed evidence run hardening

For the actual provider-backed evidence decision, run the report with `--include-db --require-db`.
The script resolves the local DB DSN from supported env aliases, local env files, or a Docker Compose Postgres configuration. If no read-only DB scan can complete, the report is intentionally not sufficient evidence for PROVIDER-001C/APPLY-001.
