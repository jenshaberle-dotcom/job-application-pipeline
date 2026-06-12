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

## EXPAND-002B result-quality hardening

The live smoke test proved that the explicit provider path can complete requests and keep the no-mutation boundary. It also exposed two quality risks that must be controlled before larger runs:

- duplicate trial candidates or duplicate probe rows must be deduplicated before external requests are executed
- generic job boards, aggregators or broad market-search pages must not be classified as actionable origin/detail evidence

EXPAND-002B therefore separates evidence strength:

- `origin_or_career_hint_found` for company-specific career/origin URLs
- `company_specific_job_detail_hint_found` for company-specific job/detail evidence
- `weak_market_or_aggregator_hint_found` for generic job-board or market-search results
- `no_actionable_hint` when no useful evidence is present

Weak hints remain learning signals for human review, but they are not origin evidence, detail-page evidence, gate truth, connector truth, or automatic candidate promotion evidence.

Provider authentication failures are fail-fast: after the first authentication failure, remaining planned probes are blocked instead of continuing repeated failed external requests.


## EXPAND-002C result evidence classifier calibration

EXPAND-002B separated strong and weak external hints, but the controlled 10x20 run showed that URL-level evidence still needed calibration:

- generic company tokens such as `data`, `service`, `software`, `business` or `consulting` must not make generic job boards look company-specific
- career subdomains such as `karriere.<company>.de` must be recognized as origin/career evidence when the company identity is plausible
- provider-hosted recruiting URLs such as Onlyfy, ZohoRecruit, Workday, Personio, Greenhouse, Lever or SmartRecruiters are only actionable when the company identity appears in the host, path or title
- aggregator/market URLs remain weak learning signals, not origin evidence and not gate truth

EXPAND-002C therefore classifies each returned URL before deriving the candidate-level evidence hint:

- `company_origin_or_career_url`
- `company_specific_job_detail_url`
- `origin_provider_url`
- `aggregator_or_market_url`
- `unrelated_or_generic_url`

The report summary includes URL-level counters for strong, weak and generic evidence. Candidate outcomes continue to require human review and still cannot create candidates, write gates, activate connectors or mutate database/pipeline state.
