# Employer-Origin Candidate Gate-State Model

## Status

Proposed for S2R implementation.

## Purpose

This document describes the DB-backed review-state model for employer-origin connector candidates.

S2Q defined the gated connector build process. S2R makes that process recordable in the database so later scripts or AI agents can execute the process without relying on CSV, Excel or generated review files as hidden inputs.

## Boundary

This model stores candidate and gate-review state only.

It does not:

- activate a source
- run a connector
- approve Bronze persistence
- approve recurring ingestion
- execute destructive operations
- use generated Markdown/JSON/CSV outputs as process inputs

Generated artifacts may still exist for human review, but the operational process state belongs in PostgreSQL.

## Tables

### `employer_origin_source_candidates`

Stores one candidate employer/source target.

Key fields:

- `company_key`
- `company_name`
- `candidate_url`
- `source_name_candidate`
- `source_family_candidate`
- `source_target_candidate`
- `source_type_candidate`
- `status`
- `risk_level`
- `notes`

### `employer_origin_candidate_gate_reviews`

Stores the current state for each gate of one candidate.

Each candidate is initialized with the standard gate list from S2Q:

1. `company_candidate`
2. `source_discovery`
3. `risk_gate`
4. `technical_reachability_gate`
5. `scope_gate`
6. `defensive_preview_gate`
7. `relevance_gate`
8. `detail_evidence_gate`
9. `incremental_uniqueness_gate`
10. `connector_candidate_gate`
11. `controlled_activation_gate`
12. `bronze_validation`
13. `silver_validation`
14. `source_lifecycle_tracking`

### `employer_origin_candidate_gate_events`

Stores an event trail for candidate creation and gate updates.

This keeps gate updates explainable without turning Markdown reports into operational state.

## CLI Helper

`scripts/record_employer_origin_gate_review.py` supports:

- `create-candidate`
- `record-gate`
- `list-candidates`

The helper uses environment database variables through normal project conventions and writes to PostgreSQL.

## Example

Create a DB-backed candidate:

```bash
python -m scripts.record_employer_origin_gate_review create-candidate \
  --company-key finanz_informatik \
  --company-name "Finanz Informatik GmbH & Co. KG" \
  --candidate-url "https://www.f-i.de/de/karriere/offene-stellen" \
  --source-name-candidate "finanz_informatik:hannover" \
  --source-family-candidate finanz_informatik \
  --source-target-candidate hannover \
  --source-type-candidate employer_origin_career_site \
  --status active_controlled \
  --risk-level low \
  --notes "Reference employer-origin connector path after controlled activation."
```

Record a gate result:

```bash
python -m scripts.record_employer_origin_gate_review record-gate \
  --candidate-id 1 \
  --gate-name risk_gate \
  --gate-status passed \
  --decision continue \
  --evidence-json '{"risk": "bounded read-only public career listing"}' \
  --event-reason "Manual backfill of Finanz Informatik reference path."
```

List candidates:

```bash
python -m scripts.record_employer_origin_gate_review list-candidates
```

## Agent-Ready Interpretation

A future connector-building agent should use this model as the state backbone.

The agent should:

- create or load a candidate
- process gates in order
- record each gate decision
- stop at the first failed hard gate
- provide a documented stop reason
- propose connector code only when the connector-candidate gate passes

The agent must not:

- infer hidden state from local export files
- use CSV/Excel as gate input
- activate a connector without DB-backed gate state
- broaden scope outside the candidate definition
- ignore a failed hard gate

## Design Principle

The process state lives in the database.

Reports explain decisions to humans.

Connectors are built only when the DB-backed gate state justifies them.
