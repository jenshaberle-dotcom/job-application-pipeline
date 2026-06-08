# ADR 019: Separate Source Heartbeat from Ingestion Runs

## Status

Proposed

## Context

The project currently contains an initial dashboard-oriented source heartbeat view.

This view derives source status from ingestion runs.

This is useful as a first operational indicator, but it does not represent a true independent heartbeat.

An ingestion run is a productive data acquisition process. It fetches job data, stores raw jobs, records duplicates and creates job observations.

A heartbeat should be a lightweight operational check that verifies whether a source can be reached and whether the expected access pattern still responds.

The two concepts overlap in dashboard usage, but they answer different questions.

## Problem

If ingestion runs are used as the only heartbeat signal, failure analysis remains ambiguous.

A failed ingestion run can mean:

- the source is unreachable
- the source API changed
- request parameters failed
- authentication failed
- the connector implementation failed
- parsing failed
- local pipeline logic failed
- database persistence failed
- the source returned no valid jobs

In addition, heartbeat frequency and ingestion frequency may differ.

A source may need frequent lightweight availability checks while productive ingestion should run less often.

## Decision

The project will conceptually separate:

- source heartbeat checks
- productive ingestion runs
- dashboard-oriented source health summaries

The current ingestion-derived heartbeat view may remain as an initial dashboard indicator.

It should later evolve into or be replaced by a broader source health summary that combines:

- heartbeat results
- ingestion run results
- freshness information
- error information
- source-specific expectations

## Consequences

### Positive

- clearer operational semantics
- better failure diagnosis
- more meaningful dashboard health indicators
- heartbeat checks can run independently from ingestion
- ingestion runs remain focused on productive data acquisition
- source health can combine multiple signals

### Negative

- additional implementation complexity
- additional tables or views may be needed
- scheduling logic may become more explicit
- more documentation and naming discipline is required

## Future Implementation Notes

A future implementation may introduce:

- `source_heartbeat_checks`
- `source_health_snapshots`
- a dedicated heartbeat runner
- source-specific heartbeat capability methods
- dashboard views that combine heartbeat and ingestion signals

The heartbeat runner should not persist productive job data.

It should collect lightweight operational information such as:

- source name
- checked URL or endpoint
- status
- response status code
- response time
- error message
- checked timestamp

## Related Documentation

- `docs/reference/observability/source_health_and_heartbeat.md`
- `docs/archive/visualization/dashboard_vision.md`
- `docs/reference/database/tables.md`
