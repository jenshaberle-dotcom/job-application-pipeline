# EXPAND-002 Controlled External Probe Trial Run

Status: planned implementation block  
Scope: Search Intelligence / manual market candidates / controlled external evidence probe

## Purpose

EXPAND-002 executes a controlled external probe trial for manually discovered candidates that were prepared by MARKET-003F / EXPAND-001.

The purpose is to measure how far the newly found companies can progress through the discovery/evidence part of the pipeline before a human decision is needed.

This block may execute external search requests, but only behind an explicit operator flag.

## Boundary

This block may:

- read the EXPAND-001 trial plan export
- create bounded origin/detail probe queries
- optionally execute external search requests after explicit operator action
- write JSON/CSV/Markdown review artifacts
- summarize evidence hints and stop conditions

This block must not:

- create candidates automatically
- promote candidates automatically
- write gate decisions
- activate connectors
- mutate Bronze, Silver or Gold
- write database state
- change scheduler state
- bypass human approval gates

## Default dry-run

The default command builds a manifest and executes no external requests:

    python scripts/run_expand002_controlled_external_probe_trial_run.py

## Explicit external trial

A fake provider can be used for local validation without network calls:

    python scripts/run_expand002_controlled_external_probe_trial_run.py --execute-external-probes --provider fake --max-candidates 5 --max-total-requests 10

A Tavily run requires `TAVILY_API_KEY` and an explicit provider choice:

    python scripts/run_expand002_controlled_external_probe_trial_run.py --execute-external-probes --provider tavily --max-candidates 200 --max-queries-per-candidate 2 --max-results-per-query 5 --max-total-requests 500

Even when the operator chooses a generous credit budget, bounded request limits remain part of the safety design.

## Inputs

Default input:

    exports/market003f_expand001_controlled_manual_candidate_pipeline_trial/market003f_expand001_controlled_manual_candidate_pipeline_trial_plan.json

## Outputs

Default output directory:

    exports/expand002_controlled_external_probe_trial_run/

Expected output files:

- `expand002_controlled_external_probe_trial_run.json`
- `expand002_controlled_external_probe_trial_results.csv`
- `expand002_controlled_external_probe_trial_run.md`

## Interpretation

Evidence hints are not gate decisions.

A candidate with external hints may become a stronger human-review candidate, but this block does not decide promotion, approval, connector registration or activation.

## Next step

A later review/apply block may let the operator inspect the evidence and explicitly decide which companies should become real candidates or receive additional evidence repair.
