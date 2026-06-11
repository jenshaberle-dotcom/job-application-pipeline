# MARKET-003B Manual Observation Backfill

Status: planned / patch-ready
Work item: `MARKET-003B Manual Observation Backfill`

## Purpose

`MARKET-003B` anchors the manually reconstructed LinkedIn / market reality-check
company list as explicit `MARKET-003` learning signals and normalizes older HDI
manual sightings that still use legacy provenance.

This closes the gap after `MARKET-003`: the capability to record manual market
observations exists, but the complete manual company list was not yet persisted.

## Scope

Included:

- code-backed backfill inventory for the reconstructed manual company list
- dry-run-first review report
- explicit `--write` path limited to `market_evidence`
- duplicate skip for already persisted `manual_market_observation` rows
- legacy normalization for rows such as HDI with:
  - `evidence_kind = manual_aggregator_sighting`
  - `evidence.input_mode = manual_market_evidence`
- JSON/Markdown reports under `exports/`

Excluded:

- no CSV/Excel/export as pipeline input
- no job ingestion
- no Bronze/Silver/Gold mutation
- no candidate creation
- no gate decision
- no connector activation or build
- no scheduler change
- no destructive deletion of legacy rows

## Safety boundary

The default mode is dry-run. `--write` only performs bounded `market_evidence`
changes:

1. Insert missing manual observations from the code-backed inventory.
2. Normalize legacy manual evidence provenance in-place.

Legacy rows are not deleted. They are updated to carry `MARKET-003` manual
observation provenance and a `legacy_migration_work_item = MARKET-003B` marker.

## Manual company inventory

The backfill inventory is based on the reconstructed manual LinkedIn / market
reality-check list from the 2026-06-09/10 project discussion. Relevance remains a
learning signal and is not gate truth.

Default fields:

- `title = Data Engineer`
- `search_term = Data Engineer`
- `observation_channel = linkedin`
- `remote_signal = unknown`
- `relevance_signal = unknown`
- `source_seen_at = 2026-06-10T00:00:00+00:00`

## Review commands

Dry run:

```bash
python scripts/run_market003b_manual_observation_backfill.py
```

List code-backed inventory:

```bash
python scripts/run_market003b_manual_observation_backfill.py --list-default-companies
```

Apply after review:

```bash
python scripts/run_market003b_manual_observation_backfill.py --write
```

Post-write review:

```bash
python scripts/run_market003_external_market_observation.py --review-only
```

## Interpretation

`MARKET-003B` makes manual market observations measurable and reusable for recall
and false-negative analysis. It must not be interpreted as candidate approval,
origin-source evidence, connector readiness or Gold truth.
