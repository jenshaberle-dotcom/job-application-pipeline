# E.ON Multi-Location Projection 001A

Status: implementation for issue `#352`  
Boundary: exact E.ON pilot raw job `26342` / Silver job `466`  
Projection key: `EON-MULTI-LOCATION-PROJECTION-001`

## Product problem

The SuccessFactors listing card and URL expose `Essen` as one location hint. The
stored employer-origin detail text identifies the same vacancy as eligible in
`Essen`, `Hannover` and `München`.

The existing Silver model has one compatibility field, `silver_jobs.city`. That
field remains unchanged in this slice because it participates in existing read
models and canonicalization behavior. Complete eligible-location evidence is
projected into a normalized one-to-many relation instead.

## Schema

Tracked migration `086_create_silver_job_locations.sql` creates
`silver_job_locations` with:

- a foreign key to the existing Silver job;
- city and ISO-style two-letter country code;
- one optional primary location per Silver job;
- source text and evidence-source lineage;
- optional source observation time;
- deterministic case-insensitive location identity.

The migration performs no data backfill and does not update `silver_jobs`.

## Evidence parser

`extract_successfactors_locations` accepts only labelled SuccessFactors metadata
fields such as:

```text
Location: Essen, Hannover, München Function area: IT/Digital
```

and the rendered footer form:

```text
Location: Essen, DE Hannover, DE München, DE
```

It does not infer locations from unlabelled prose and rejects work-model values
such as `Remote`, `Hybrid` or `Home Office` as cities.

## Controlled runtime

After applying migration 086, plan-only execution is:

```bash
python -m scripts.run_eon_location_projection \
  --raw-job-id 26342 \
  --silver-job-id 466
```

Controlled Apply is:

```bash
python -m scripts.run_eon_location_projection \
  --raw-job-id 26342 \
  --silver-job-id 466 \
  --apply \
  --approval-token EON-MULTI-LOCATION-PROJECTION-001
```

The runner binds to the exact authorized E.ON pilot provenance, exact source,
external job ID, title, raw/Silver IDs and legacy city. It rebuilds the expected
location evidence inside one advisory-locked transaction and accepts replay only
when existing rows match the deterministic projection.

## Expected result

```text
legacy_city: Essen
locations: Essen, Hannover, München
locations_inserted: 3
legacy_city_unchanged: true
readiness_before: hard_filter_evidence_required
readiness_after: hard_filter_evidence_required
```

An idempotent second Apply reports `locations_inserted: 0`.

## Explicit non-goals

This slice does not:

- call the network, a provider or an LLM;
- activate or schedule a connector;
- add another Bronze or Silver job;
- alter `silver_jobs.city`, normalized location or canonical key candidates;
- create a hard-filter decision or ranking score;
- make the job rankable;
- generate or submit an application;
- yet modify the generic SuccessFactors connector emission path.

Generic connector emission is bound only after this exact runtime projection has
been validated.
