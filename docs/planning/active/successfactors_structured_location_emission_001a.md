# SuccessFactors Structured Location Emission 001A

Status: implementation for issue `#354`  
Boundary: additive raw employer-origin evidence only

## Context

Issue `#352` and PR `#353` established a normalized Silver location relation and
proved the exact controlled E.ON projection for `Essen`, `Hannover` and
`München`. The generic SuccessFactors connector still emitted only its singular
listing-card or URL location hint in `job.location`.

## Contract

Future SuccessFactors raw records now retain two distinct location concepts:

- `job.location` and `result_card.location` remain the existing singular
  compatibility/listing-hint value;
- `job.locations` contains ordered structured employer-origin detail evidence.

Each `job.locations` item contains:

```json
{
  "city": "Hannover",
  "country_code": "DE",
  "evidence_source": "successfactors_detail_location_field",
  "evidence_text": "Essen, DE Hannover, DE München, DE"
}
```

`detail_evidence.structured_location_count` exposes the number of accepted
structured locations.

## Fail-closed behavior

The connector reuses the deterministic labelled-field parser introduced by PR
`#353`. It does not infer locations from arbitrary vacancy prose. When a detail
page mentions cities without an explicit `Location:`, `Standort:` or `Ort:`
metadata field, `job.locations` is an empty list and the structured count is
zero.

## Compatibility

This slice does not change:

- source selection or request limits;
- listing-page or detail-page fetch behavior;
- `job.location` or `result_card.location`;
- Bronze/Silver persistence behavior;
- the existing Silver city, normalized location or canonical key;
- Product V1 readiness, hard-filter or ranking state.

## Boundaries

This slice does not:

- activate a source or scheduler;
- add pagination;
- perform a provider or LLM call;
- automatically write `silver_job_locations`;
- mutate existing rows;
- generate or submit an application.

Projection from future raw `job.locations` evidence into the normalized Silver
relation remains a separate controlled ingestion concern.
