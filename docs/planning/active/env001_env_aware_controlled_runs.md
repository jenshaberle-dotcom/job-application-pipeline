# ENV-001 / Env-aware controlled runs for external probes

Status: backlog / governance-tooling follow-up  
Scope: job-application-pipeline runtime/operator tooling, MCP-assisted controlled runs  
Created: 2026-06-17

## Context

During the controlled EXPAND-002C Tavily mini-probe, the first operator run stopped with:

```text
TAVILY_API_KEY is not set. Stop before external provider call.
```

The key was present in the project `.env` file, but it was not exported into the active shell environment. Activating the Python virtual environment does not load project `.env` values.

A bounded Python wrapper then loaded only `TAVILY_API_KEY` from `.env`, did not print the secret, and passed it as process environment to the controlled EXPAND-002 runner.

## Observed proof

Controlled EXPAND-002C Tavily mini-probe:

```text
provider=tavily
planned_probe_count=2
external_requests_executed_count=2
completed_probe_count=2
failed_probe_count=0
blocked_after_provider_auth_failure_count=0
candidate_count=1
candidate_with_external_hint_count=0
candidate_with_weak_external_hint_count=1
candidate_creation_count=0
gate_decision_count=0
database_write_count=0
mutation_database_writes=0
mutation_external_requests_executed_by_this_command=2
```

Downstream EXPAND-003 from the Tavily mini-probe:

```text
candidate_count=1
ready_for_human_evidence_review_count=0
ready_for_detail_followup_review_count=0
weak_external_hint_no_candidate_creation_count=1
candidate_creation_count=0
gate_decision_count=0
connector_activation_count=0
mutation_database_writes=0
review_item=3xperts | 3XPERTS GmbH | weak_external_hint_no_candidate_creation | weak_market_signal
```

## Problem

Controlled external-provider runs currently depend on the operator exporting secrets into the shell environment before running the bounded CLI.

This creates unnecessary friction and causes false stops even when the `.env` file is correctly configured. The workaround must not become unsafe shell behavior.

## Desired improvement

Add an explicit, governed way to run controlled provider-backed probes with `.env` awareness.

Acceptable implementation directions:

1. Pipeline runner option such as `--env-file .env`, loading only required provider keys.
2. MCP-side controlled-run wrapper that loads required environment variables for a single subprocess.
3. A shared utility for bounded dotenv loading used by controlled external runs.

## Hard boundaries

- Do not print secret values.
- Do not `source .env` through the shell.
- Do not execute arbitrary `.env` content as shell code.
- Load only explicit allowlisted keys required for the selected provider.
- External requests must still require an explicit operator flag such as `--execute-external-probes`.
- Default mode must remain dry-run / no external request.
- No DB writes.
- No candidate creation.
- No gate decision.
- No connector activation.
- No scheduler mutation.
- Generated outputs remain review artifacts only and must not become pipeline truth or gate inputs.

## System impact

Affected areas:

- Operator UX for controlled external probes.
- MCP-controlled run ergonomics.
- Provider credential handling.
- Safety/audit boundaries around external requests.

Not affected:

- Candidate creation.
- Gate decisions.
- Bronze/Silver/Gold mutations.
- Scheduler behavior.
- Database writes.

## Why this matters

The current workflow forces a bad choice between large manual copy/paste blocks and ad-hoc output artifacts until MCP can inspect, evaluate, and execute bounded actions under gates.

This item should reduce operator friction while preserving the core safety model: explicit external execution, narrow caps, no secret logging, no pipeline mutation, and review-only outputs.
