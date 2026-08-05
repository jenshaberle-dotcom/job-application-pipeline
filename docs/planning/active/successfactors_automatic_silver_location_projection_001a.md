# SuccessFactors Automatic Silver Location Projection 001A

Status: implementation for issue `#357`  
Boundary: future generic Silver processing of explicit SuccessFactors `job.locations`

## Product gap

Migration `086_create_silver_job_locations.sql` created the one-to-many Silver
location relation. The exact E.ON pilot was backfilled and replay-validated, and
future SuccessFactors connector records now retain structured location evidence
in `raw_data.job.locations`.

Before this slice, the standard Silver runner still wrote only `silver_jobs`.
A new SuccessFactors job could therefore carry complete employer-origin location
evidence in Bronze while losing that evidence during normal Silver processing.

## Closed path

The standard runner now calls
`write_silver_job_with_successfactors_locations()` instead of the legacy
single-table upsert.

For each relevant raw job, the writer:

1. builds the unchanged legacy Silver job representation;
2. distinguishes missing legacy `job.locations` from an explicit authoritative
   list;
3. validates structured SuccessFactors location objects before opening a DB
   transaction;
4. upserts the Silver job and synchronizes structured locations on one
   connection and in one commit;
5. rolls back both writes when any location operation fails.

## Compatibility semantics

The existing fields remain unchanged:

- `silver_jobs.city` continues to use the singular compatibility/listing hint;
- `normalized_location` continues to derive from that singular field;
- `canonical_key_candidate` continues to use the existing singular-location
  canonicalization;
- structured locations are additive evidence in `silver_job_locations`.

For an E.ON-shaped future job, the compatibility city remains `Essen`, while the
one-to-many relation contains:

- Essen, DE — primary because it matches the compatibility city;
- Hannover, DE;
- München, DE.

If no structured city matches the compatibility city, the first structured
location becomes primary. Exactly one projected row is primary whenever at least
one location exists.

## Legacy and empty semantics

Missing and empty are intentionally different:

- missing `job.locations`: legacy raw record; preserve all existing location
  evidence and do not query or mutate `silver_job_locations`;
- explicit `job.locations: []`: authoritative empty result; clear only rows whose
  evidence source is `successfactors_detail_location_field`.

Rows from other evidence sources are outside this synchronization boundary.

## Idempotency

Location identity is the existing case-insensitive database identity of
`silver_job_id`, city and country code.

The writer:

- clears a former automatic primary only when the primary identity changes;
- deletes stale rows only from the automatic SuccessFactors evidence source;
- uses conflict-aware inserts;
- updates existing rows only when primary, evidence or observation values differ.

A replay therefore creates no duplicates and does not churn unchanged location
rows.

## Fail-closed rules

The authoritative field is rejected before mutation when it contains:

- a non-list value;
- non-object entries;
- blank, overlong or delimiter-bearing cities;
- work-model values such as Remote or Hybrid as cities;
- invalid country codes;
- another evidence-source identifier;
- duplicate case-insensitive city/country identities;
- missing or blank evidence text.

## Explicit non-goals

This slice does not:

- activate or schedule SuccessFactors ingestion;
- add a migration or backfill existing jobs;
- issue a network, provider or LLM request;
- change ranking, hard-filter, readiness or application state;
- reinterpret the legacy singular location fields.
