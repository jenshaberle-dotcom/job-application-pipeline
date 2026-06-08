# S7X enercity Post-Ingestion Observability

## Summary

S7X validates that the newly activated `enercity:discovery` source target is visible in the existing observability, source-value and Gold health reporting after its first controlled Bronze/Silver run.

## Boundary

- No ingestion run was executed in this block.
- No source activation or search-profile migration was added in this block.
- No raw_jobs or silver_jobs were written in this block.
- No scheduler changes were made.
- No CSV/Excel/export artifacts were used as pipeline inputs.
- This block validates observability, records a source-value snapshot and updates the employer-origin candidate lifecycle state after verified activation/run evidence.

## Baseline

- source: `enercity:discovery`
- raw jobs: `1`
- silver jobs: `1`
- latest ingestion run: `527`
- latest run status: `success`
- inserted jobs: `1`
- duplicate jobs: `0`

## Source Heartbeat

`source_heartbeat` reports `enercity:discovery` as:

- heartbeat status: `healthy`
- last ingestion run id: `527`
- last status: `success`
- last total loaded: `1`
- last inserted count: `1`
- last duplicate count: `0`

## Dashboard Processing Summary

`dashboard_source_processing_summary` reports:

- ingestion run count: `1`
- successful run count: `1`
- failed run count: `0`
- total loaded jobs: `1`
- total inserted jobs: `1`
- total duplicate jobs: `0`
- total new relevant jobs: `1`
- total new unprocessed jobs: `0`
- has unprocessed jobs: `false`
- duplicate rate: `0.0000`
- new relevance rate: `1.0000`

## Gold Health

The enercity employer-origin candidate was moved from `discovery` to `active_controlled` after verifying:

- controlled activation migration `051_activate_enercity_discovery_source_target.sql`
- first successful ingestion run `527`
- Silver job `196`

Gold health now reports:

- candidate status: `active_controlled`
- health status: `active_controlled`
- active controlled count: `1`
- source type: `employer_origin_career_site`

## Source Value Snapshot

A corrected `source_value_snapshots` entry was created after the lifecycle/source-type fix with reason:

- `s7x_enercity_post_ingestion_observability_after_lifecycle_fix`

Corrected source-value interpretation:

- snapshot id: `176`
- source family: `enercity`
- source target: `discovery`
- source type: `employer_origin_career_site`
- ingestion runs: `1`
- successful runs: `1`
- failed runs: `0`
- raw jobs: `1`
- silver jobs: `1`
- distinct companies: `1`
- distinct candidate keys: `1`
- failure rate: `0.00`

## Historical Note

An earlier S7X snapshot, id `165`, classified `enercity:discovery` as `unknown`. This was intentionally superseded by snapshot id `176` after source-value typing was corrected for controlled employer-origin source families.

## Interpretation

The enercity source target is now visible end-to-end in the project’s post-ingestion observability path:

`controlled activation → Bronze → Silver → Source Heartbeat → Dashboard Processing Summary → Source Value Snapshot → Gold Health`

This confirms the source target can be monitored before any scheduler integration is considered.
