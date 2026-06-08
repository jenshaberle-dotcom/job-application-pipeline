# Source Health and Heartbeat Concept

## Purpose

This document describes the intended separation between productive ingestion runs, lightweight source heartbeat checks and dashboard-oriented source health summaries.

The goal is to make operational source monitoring explicit instead of deriving all health information indirectly from ingestion runs.

## Current State

The current project contains an initial dashboard-oriented source heartbeat view.

This view is useful as a first operational indicator because it summarizes the latest ingestion run state per source.

However, it is not a true independent heartbeat.

Current behavior:

- source health is derived from ingestion runs
- ingestion runs represent productive data acquisition
- failed ingestion runs can indicate operational issues
- failed ingestion runs now persist `error_type`, `error_stage` and `error_message`
- successful ingestion runs provide useful freshness information
- source reachability is not checked independently

## Problem

Using ingestion runs as the only heartbeat signal has limitations.

A failed ingestion run does not clearly explain whether:

- the source is unreachable
- the source API changed
- authentication or request parameters failed
- the connector implementation failed
- the parser failed
- local pipeline logic failed
- the source returned zero valid jobs
- the database write failed

Ingestion frequency and heartbeat frequency may also differ.

A source could be checked more frequently than productive ingestion should run.

## Target Separation

The project should distinguish three concepts:

- `source_heartbeat`
- `ingestion_runs`
- `source_health`

## source_heartbeat

A source heartbeat is a lightweight operational check.

Purpose:

- verify whether a source can be reached
- verify whether the expected endpoint or access pattern still responds
- collect status code, latency and basic error information
- avoid persisting productive job data
- run independently from productive ingestion
- optionally run more frequently than ingestion

A heartbeat should answer:

> Could the pipeline theoretically communicate with this source right now?

It should not answer:

> Did we successfully ingest and store productive job data?

## ingestion_runs

An ingestion run is a productive data acquisition process.

Purpose:

- fetch job data from a source
- apply source-specific and local filtering
- store raw jobs
- record duplicate behavior
- create job observations
- provide lineage for downstream Silver and Gold processing

An ingestion run should answer:

> Did we productively fetch, process and persist job data?

## source_health

Source health is a dashboard-oriented summary that combines multiple operational signals.

Potential inputs:

- latest heartbeat result
- latest successful heartbeat
- latest ingestion run
- latest successful ingestion run
- failed heartbeat count
- failed ingestion count
- source-specific error type and stage diagnostics
- source-specific error messages
- freshness thresholds
- data availability expectations

Source health should answer:

> Is this source currently healthy enough to trust in the dashboard?

## Candidate Future Tables

### source_heartbeat_checks

Potential purpose:

Store individual heartbeat attempts per source.

Possible fields:

| Field | Meaning |
|---|---|
| `id` | Heartbeat check identifier |
| `source_name` | Checked source |
| `checked_at` | Timestamp of the check |
| `status` | Result status, for example `success` or `failed` |
| `response_status_code` | HTTP status code if available |
| `response_time_ms` | Approximate response latency |
| `error_type` | Classified heartbeat failure type |
| `error_stage` | Heartbeat stage where the failure occurred |
| `error_message` | Error details if the heartbeat failed |
| `checked_url` | Endpoint or URL used for the heartbeat |
| `connector_name` | Connector implementation used for the check |

### source_health_snapshots

Potential purpose:

Persist evaluated source health states for dashboard and history.

Possible fields:

| Field | Meaning |
|---|---|
| `id` | Source health snapshot identifier |
| `source_name` | Evaluated source |
| `evaluated_at` | Timestamp of the evaluation |
| `health_status` | Dashboard status such as `healthy`, `warning`, `critical`, `unknown` |
| `last_successful_heartbeat_at` | Latest successful heartbeat timestamp |
| `last_successful_ingestion_at` | Latest successful ingestion timestamp |
| `latest_error_type` | Latest classified operational error type |
| `latest_error_stage` | Latest operational stage where a failure occurred |
| `latest_error_message` | Latest relevant operational error |
| `reason` | Human-readable explanation for the health status |

## Dashboard Usage

Potential dashboard widgets:

- source availability status
- latest successful heartbeat
- latest failed heartbeat
- latest successful ingestion
- latest failed ingestion
- source freshness warning
- failed checks by source
- source health traffic-light indicator

## Design Principles

The heartbeat process should be:

- lightweight
- source-aware
- independent from ingestion
- safe to run frequently
- explicit about failure reasons
- useful for dashboard monitoring
- not responsible for productive data persistence

## Current Decision

The current ingestion-derived heartbeat view remains useful as an initial dashboard indicator.

The ingestion diagnostics fields on `ingestion_runs` improve failed-run explainability, but they should not be treated as the final heartbeat architecture.

A later implementation should introduce a dedicated heartbeat process and evolve the current dashboard source heartbeat view into a broader source health summary.
