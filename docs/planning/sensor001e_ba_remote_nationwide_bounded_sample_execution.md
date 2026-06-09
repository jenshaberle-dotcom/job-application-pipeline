# SENSOR-001E BA Remote/Nationwide Bounded Sample Execution Review

SENSOR-001E executes the operator-approved BA remote/nationwide sample that SENSOR-001D planned.

## Boundary

This work item may perform bounded external BA requests after explicit approval, but it does not activate a profile and does not write Bronze/Silver/Gold pipeline state.

- external requests: only with `--execute-approved`
- database reads: yes, for profile state, known-company overlap, and duplicate comparison
- database writes: no
- `raw_jobs` writes: no
- `ingestion_runs` writes: no
- scheduler changes: no
- candidate/gate/connector mutation: no
- productive activation: no

## Default command

    python scripts/run_sensor001e_ba_remote_bounded_sample_execution.py --execute-approved

The runner exports JSON and Markdown artifacts under `exports/`.

## Decision handoff to SENSOR-001F

SENSOR-001F should use the exported metrics, especially:

- `total_loaded_by_term`
- `inserted_count_by_term` as would-insert count without Bronze write
- `duplicate_count_by_term`
- `distinct_company_count`
- `new_company_count`
- `known_company_overlap_count`
- `remote_signal_count`
- `local_or_hannover_overlap_count`
- `profile_relevant_title_count`
- `irrelevant_title_count`
- `error_count`

SENSOR-001F must not activate the review profile from volume alone.
