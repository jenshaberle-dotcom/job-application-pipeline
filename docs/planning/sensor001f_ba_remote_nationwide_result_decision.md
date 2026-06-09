# SENSOR-001F BA Remote/Nationwide Result Decision

SENSOR-001F converts a bounded SENSOR-001E sample export into a decision-ready, read-only recommendation.

## Boundary

SENSOR-001F is a decision report only.

It must not:

- call external sources
- write to the database
- write `raw_jobs` or `ingestion_runs`
- mutate scheduler state
- activate a profile
- mutate candidates, gates, connectors, Bronze, Silver, or Gold

## Failure-aware behavior

If SENSOR-001E failed before collecting sample data, SENSOR-001F must not infer market quality.

The correct result is:

- `decision_blocked_by_sensor001e_execution_failure`
- `repair_sensor001e_and_rerun_before_decision`

This preserves the sample boundary: technical execution failures are not product evidence.

## Decision inputs

SENSOR-001F requires these SENSOR-001E metrics:

- `total_loaded_by_term`
- `inserted_count_by_term`
- `duplicate_count_by_term`
- `distinct_company_count`
- `new_company_count`
- `known_company_overlap_count`
- `remote_signal_count`
- `local_or_hannover_overlap_count`
- `profile_relevant_title_count`
- `irrelevant_title_count`
- `error_count`

## Decision options

- `activate_controlled_profile`
- `repeat_bounded_sample_with_repaired_terms`
- `keep_review_profile_inactive_and_monitor`
- `reject_or_archive_profile_as_noise`
- `repair_sensor001e_and_rerun_before_decision`

## Current expected path

The first SENSOR-001E execution failed before sample collection due to a technical implementation issue.
SENSOR-001F should therefore block market decisions and recommend repairing and rerunning SENSOR-001E.
