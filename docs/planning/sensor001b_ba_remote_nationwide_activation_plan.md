# SENSOR-001B BA Remote/Nationwide Activation Plan

SENSOR-001B creates a reviewable activation plan for Germany-wide remote-option
coverage. It does not activate a profile, mutate the database, run ingestion, or
change the scheduler.

## Generic requirement

Every market sensor must make two coverage dimensions explicit:

1. local or regional market coverage
2. Germany-wide remote-option coverage

Bundesagentur is the first concrete implementation case because the current DB
inspection shows one active BA profile for `30629` with a 50 km radius. That is a
useful Hannover-region sensor, but it is not a validated Germany-wide remote
sensor.

## Current BA baseline

The observed active profile is:

- `ba_data_engineer_30629_50km`
- source: `bundesagentur_fuer_arbeit`
- location: `30629`
- radius: `50`
- page size: `10`
- active: `true`

The observed active search terms are the existing data-engineering terms such as
Data Engineer, Analytics Engineer, ETL, Data Platform, Data Warehouse, Big Data,
and Python SQL.

## Planned profile

SENSOR-001B proposes, but does not activate, a separate profile:

- `ba_data_engineering_remote_nationwide_review`
- source: `bundesagentur_fuer_arbeit`
- location: `NULL`
- radius: `NULL`
- page size: bounded to 10
- active: `false`

This keeps the Hannover baseline unchanged and prevents accidental scheduler
expansion.

## Why inactive by default

BA remote filtering is not currently modeled as a confirmed server-side source
capability. Therefore the safe first step is a Germany-wide bounded discovery
profile plus downstream review of remote/hybrid evidence, not immediate
productive ingestion.

## Activation gates

A later SENSOR-001C activation must confirm:

- leaving location/radius empty is the intended BA nationwide-query strategy
- a bounded sample run does not flood Bronze with low-value noise
- duplicate rate, inserted count, role relevance, location distribution, and
  remote/hybrid signal quality are measurable
- existing local BA coverage remains unchanged
- activation happens through a separate reviewed migration or operator action

## Safety boundary

SENSOR-001B is read-only. It may create JSON, Markdown, and SQL draft artifacts
under `exports/`, but it must not write to the project database or activate any
source profile.
