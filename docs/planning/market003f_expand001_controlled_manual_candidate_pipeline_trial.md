# MARKET-003F / EXPAND-001 Controlled Manual Candidate Pipeline Trial

Status: planned implementation block  
Scope: Search Intelligence / manual market candidates / controlled trial planning

## Purpose

MARKET-003F / EXPAND-001 prepares a controlled pipeline-trial manifest for newly found manual market candidates.

It uses the MARKET-003E read-only review queue as input and creates a measurable plan for how far each candidate should be allowed to proceed in an explicit future trial.

The goal is to answer product questions such as:

- Which manually found companies are ready for external origin/detail probing?
- Which ones are blocked by identity uncertainty or weak evidence?
- Where would each candidate likely stop in the current pipeline?
- Which missing evidence class blocks progress?
- Would a separate human-approved promotion workflow be justified later?

## Boundary

This block is plan-only and export-only.

It must not:

- execute external requests
- spend Tavily/search credits
- create candidates automatically
- promote candidates automatically
- write gate decisions
- activate connectors
- mutate Bronze, Silver or Gold
- change scheduler state
- write database state

External requests may be allowed in a later explicit run block, but only after an operator-visible command boundary.

## Credit Policy

The operator may choose a generous external-search budget for a future trial run.

That does not weaken the project boundaries:

- legal/operational risk controls remain active
- gate decisions remain human-approved
- connector activation remains explicit
- scheduler behavior remains unchanged

## Trial Lanes

The trial plan may classify queue cards into:

- `ready_for_controlled_external_trial`
- `known_candidate_context_revalidation`
- `blocked_until_identity_review`
- `parked_not_trial_ready`
- `unclassified_manual_review_needed`

These lanes are trial planning labels, not candidate states.

## Planned Stages

A ready candidate may receive these planned stages:

- `review_queue_context_intake`
- `company_identity_checkpoint`
- `origin_url_discovery_probe`
- `detail_page_evidence_probe`
- `pipeline_stop_or_progress_measurement`
- `human_review_summary`

The stage list is a manifest for controlled execution, not execution itself.

## Command

    python scripts/run_market003f_expand001_controlled_manual_candidate_pipeline_trial.py

Default input:

    exports/market003e_candidate_expansion_review_ui_queue_readiness/market003e_candidate_expansion_review_ui_queue_readiness.json

Default output:

    exports/market003f_expand001_controlled_manual_candidate_pipeline_trial/

Expected outputs:

- `market003f_expand001_controlled_manual_candidate_pipeline_trial_plan.json`
- `market003f_expand001_controlled_manual_candidate_pipeline_trial_candidates.csv`
- `market003f_expand001_controlled_manual_candidate_pipeline_trial_plan.md`

## Next Step

After this block, a separate explicit execution block may run external origin/detail probes for the eligible candidates.

That execution block must still keep these boundaries:

- no automatic candidate creation
- no automatic gate decision
- no connector activation
- no scheduler mutation
- no uncontrolled pagination or source abuse
- review artifacts only until an apply workflow is explicitly approved
