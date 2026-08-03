# Staged Origin Repair and Database Audit

Status: implemented for validation  
Boundary: read-only discovery and explicit SZ1 review planning  
Trigger: 1&1 acceptance run on 2026-08-03

## Confirmed bugs

The successful 1&1 run selected `https://career.1and1.org/`, but still made seven
Tavily requests. Deterministic symbol-brand hosts and Tavily results were combined
before validation, so the selected stage was reported as `selected_tavily_repair`
even when the selected URL originated from deterministic generation.

The old CAND-001 path also reran the complete provider cascade instead of consuming
the already written, successful repair artifact. That repeated solved work and
could create avoidable provider cost.

A third output ambiguity displayed a high rejected-candidate score as
`confidence` beside `decision=not_found`. That value is not confidence that no
URL exists; it is the best observed candidate score below the selection contract.

## New staged default

```text
deterministic_baseline
→ deterministic_symbol_brand
→ Tavily only after deterministic miss
→ early LLM search hypotheses only after Tavily miss
→ deep evidence and optional late LLM adjudication
```

The deterministic symbol-brand stage is a separate discovery pass. A selected URL
ends the run with:

```text
final_state=selected_deterministic_symbol_brand
provider_requests=0
```

Tavily receives only novel search-result URLs. Previously probed deterministic
brand hosts are not mixed into its candidate batch.

Console output now labels unresolved stage scores as `best_candidate_score`, not
`confidence`. The JSON payload also carries a `score_semantics` contract.

## Validated artifact reuse

`scripts.run_cand001_repair_artifact_gate` accepts a completed repair artifact only
after validating:

- supported artifact schema;
- `review_output_only_not_pipeline_input=true` marker;
- timezone-aware generation timestamp and maximum age;
- exactly one result for the requested company key;
- selected final state, selected stage and matching HTTPS URL;
- no operator-review, exhaustion or configuration-blocked contradiction;
- no candidate, connector, source, Bronze/Silver or scheduler mutation boundary;
- no repeated-state finding;
- exact company-name match against the current database candidate.

This is an explicit evidence handoff, not hidden export ingestion. Default mode is
dry-run and rolls the DB transaction back. `--apply` remains mandatory for the
SZ1 candidate URL write and continues to create the CAND-001 audit review.

Example dry-run:

```bash
python -m scripts.run_cand001_repair_artifact_gate \
  --benchmark-label product_e2e_1und1_candidate_url_plan_20260803 \
  --repair-artifact "$HOME/product_v1_runtime_artifacts/origin_url_default_repair_20260803T173957905735Z.json" \
  --company-key 1_1
```

## Database-wide audit

`scripts.run_origin_url_database_audit` reads the latest candidate row per company
from `employer_origin_source_candidates`, closes the DB transaction, and then runs
the staged default repair sequentially. It never writes candidate URLs or any
pipeline state.

Explicit all-company invocation:

```bash
python -m scripts.run_origin_url_database_audit --all-companies
```

Default safety ceilings:

- maximum 250 total provider requests;
- maximum 50 total LLM requests;
- stop scheduling new companies once either ceiling is reached;
- continue after a single-company exception unless `--stop-on-error` is supplied;
- no parallel external requests;
- no scheduler installation.

Outputs are written to `~/product_v1_runtime_artifacts/` as JSON, Markdown and CSV.
The report groups final states and selected stages and records provider/LLM request
counts, attempted query/URL counts, repeated-state findings and per-company errors.

## Acceptance gates

1. 1&1 selects `career.1and1.org` in `deterministic_symbol_brand` with zero provider
   requests.
2. A deterministic miss allows Tavily, but Tavily receives no already-probed direct
   brand hosts.
3. A fresh, internally consistent selected artifact builds a CAND-001 dry-run plan
   without any provider rerun.
4. Stale, mismatched, repeated-state or mutation-boundary artifacts fail closed.
5. Database audit completes read-only and emits one visible result row per current
   company, including errors and budget-guarded rows.
6. Full CI, Ruff, migration/governance and React checks pass before merge.
