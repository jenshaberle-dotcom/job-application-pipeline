# Personio Source Analysis

## Status

Initial technical integration completed.

Personio is currently integrated as a defensive public XML feed source for one validated source target:

- `personio:schluetersche-mediengruppe`

## Current Scope

The current implementation intentionally uses a narrow scope:

- one public XML request per configured source target and search term
- no detail-page fetching
- no pagination
- local keyword filtering before Bronze record creation
- Silver transformation from stable Bronze job fields

## Validated Pipeline Path

The following path has been validated locally:

```text
Personio public XML feed
→ Bronze raw_jobs
→ Silver silver_jobs
→ Source Value Summary
```

The currently validated record is:

```text
Data Engineer (m/w/d)
Schlütersche Verlagsgesellschaft mbH & Co. KG
Hannover
```

## Bronze Structure

Personio Bronze records expose stable extracted job fields under:

```text
raw_data.job.title
raw_data.job.company_name
raw_data.job.location
raw_data.job.source_url
```

The original XML-derived structure is preserved under:

```text
raw_data.source_specific.raw_position
```

Silver transformation reads the stable `raw_data.job` fields and does not parse XML evidence directly.

## Silver Result

Personio is now Silver-compatible.

The current Personio Silver record contains:

- title
- company name
- city/location
- normalized title
- normalized company name
- normalized location
- canonical key candidate

## Source Value Interpretation

The current Personio dataset contains only one relevant Silver job.

This is sufficient to validate:

- technical feasibility
- Bronze integration
- Silver compatibility
- Source Value integration

It is not sufficient to evaluate:

- source value
- company coverage
- overlap behaviour
- duplicate behaviour
- long-term stability
- search-domain usefulness

## Known Limitations

- only one source target validated
- only one relevant job currently present
- no meaningful source-value statistics yet
- no cross-source overlap observed yet
- no long-term stability signal yet
- internal `source_name` still uses `personio:<target>` until a future source-target model is implemented

## Initial Conclusion

Personio has successfully passed technical validation.

The connector, Bronze ingestion, Silver transformation and Source Value integration are functioning as intended.

However, Personio has not yet passed source-value validation.

The current dataset is too small to determine whether Personio contributes meaningful additional jobs, companies or canonical candidates compared with Bundesagentur, Greenhouse or StepStone.

## Batch 1 Candidate Selection

The current dataset is too small for meaningful source-value evaluation.

A controlled Batch 1 expansion has therefore been selected.

### Selected Targets

- `personio:eraneos` (multiple Data, Analytics and AI-related matches with remote-friendly positions)
- `personio:1komma5grad` (large employer-near feed with several relevant Data and Analytics positions)
- `personio:it-p` (Hannover relevance and mobile-working opportunities)
- `personio:otl-akademie` (small feed but direct remote Data Engineer and Data Migration relevance)

### Rejected Targets

- `personio:loyos-bi` (public XML endpoint returned HTTP 404 during evaluation)

### Deferred Targets

- `personio:xibix-solutions-gmbh` (technically reachable but currently lower geographic relevance for the target search domain)

## Evaluation Questions

The following questions will be used to evaluate the source value of Personio Batch 1:

- How many jobs does each selected target expose?
- How many relevant jobs reach Bronze and Silver?
- Which companies are new compared with existing sources?
- Which jobs overlap with Bundesagentur, Greenhouse or StepStone?
- Does Personio provide employer-near evidence for aggregator findings?
- Does Personio justify further expansion?

## Next Step

Run a controlled Personio Batch 1 with the selected targets.

The objective is not broad acquisition.

Instead, the goal is to determine whether Personio contributes measurable value for the target search domain based on the evaluation questions defined above.
