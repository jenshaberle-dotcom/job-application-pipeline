# Finanz Informatik Controlled Activation — S2P

## Purpose

S2P moves Finanz Informatik from connector candidate to one explicitly controlled active source target.

The activation is deliberately narrow:

- source name: `finanz_informatik:hannover`
- profile name: `finanz_informatik_hannover_precision`
- target URL: `https://www.f-i.de/de/karriere/offene-stellen`
- maximum detail pages: three, enforced by the connector
- target scope: Hannover candidates selected by connector relevance gates

## Why Activation Is Acceptable

The source is not expected to produce high volume. Its value is precision and incremental uniqueness. One or two relevant, non-duplicate employer-origin jobs can justify the target because employer-origin evidence may add jobs that broad aggregators do not show reliably.

S2P therefore activates a bounded target, not a broad source family.

## What This Activation Does

The activation adds:

- connector registration in `src/ingest_jobs.py`
- Silver transformer support for `finanz_informatik:%` raw records
- one DB migration that creates an active search profile and active terms
- scheduler watchdog documentation for local daily/catch-up operation

## Boundaries

S2P does not approve:

- broad Finanz Informatik crawling
- all-location ingestion
- CSV/export artifacts as activation inputs
- source-family-wide recurring ingestion
- treating low source volume as failure

## Manual Verification

After applying the migration, verify the active profile and run one controlled manual refresh:

```bash
python -m src.ingest_jobs --list-profiles
python -m src.ingest_jobs --source finanz_informatik --log-level INFO
python -m src.run_silver_jobs
```

Review raw and Silver counts before the PR is merged.

## Silver Relevance Follow-Up

The first controlled manual run proved that the connector can write bounded Bronze records, but it also exposed a Silver relevance vocabulary gap. The Finanz Informatik records carried relevant evidence in `job.profile_terms`, `result_card` and detail-page title fields, while the generic Silver relevance text originally did not read those fields.

S2P therefore extends Silver relevance extraction to include connector-provided profile evidence and adds explicit Product Owner, Business Analyst and selected software/UI role phrases. This is not a broad ingestion relaxation; the Finanz Informatik connector remains bounded to three Hannover candidates and the Silver gate still requires role/skill evidence plus an accessibility signal.
## Source-Type Semantics

The controlled Finanz Informatik source target uses:

- `source_family`: `finanz_informatik`
- `source_target`: `hannover`
- `source_type`: `employer_origin_career_site`

This classification is part of the controlled activation contract. It must be preserved in Bronze evidence, Silver canonicalization and source-value snapshots. The activated employer-origin source target must not appear as `unknown` in source-value reporting.
