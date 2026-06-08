# SENSOR-001C BA Remote/Nationwide Controlled Activation

SENSOR-001C introduces a DB-backed, review-controlled BA remote/nationwide
profile. It does not productively activate the profile.

## Scope

This work item creates:

- an idempotent migration for an inactive BA remote/nationwide review profile
- a read-only review script for controlled activation state
- tests that guard against accidental active profile creation

## Current baseline

The current BA source has one active Hannover-region profile:

- `ba_data_engineer_30629_50km`
- `search_location = 30629`
- `search_radius_km = 50`
- `page_size = 10`
- `is_active = true`

SENSOR-001C does not modify that profile.

## Review profile

The migration creates:

- `ba_data_engineering_remote_nationwide_review`
- `source_name = bundesagentur_fuer_arbeit`
- `search_location = NULL`
- `search_radius_km = NULL`
- `page_size = 10`
- `is_active = false`

The terms mirror the existing BA data-engineering baseline.

## Why inactive

BA remote filtering is not yet confirmed as a server-side capability in the
project contract. The safe controlled step is to create a review profile first,
then separately run bounded sample-ingestion review before any productive
activation.

## Review states

The read-only SENSOR-001C review can report:

- `migration_pending`: review profile does not exist yet
- `review_profile_ready`: inactive review profile exists with expected terms
- `unsafe_active_profile_detected`: review profile is active and must be stopped
- `configuration_mismatch`: review profile exists but does not match expected shape

## Follow-up

A later work item may run a bounded sample-ingestion review. Productive scheduler
activation remains out of scope for SENSOR-001C.
