# Employer Candidate and False-Negative Review — S2E

## Purpose

S2E turns the current source-coverage concern into reviewable evidence.

The goal is to answer:

```text
Do we see the employers that we would expect to see for Hannover, Germany or remote-in-Germany data roles?
```

A missing candidate is not proof that the employer has no relevant roles. It is a false-negative signal that may point to source coverage, search terms, fetch limits or Silver filtering.

## Why This Exists

S2D showed that aggregators can surface additional company signals, but the results were mixed. Some sources were hard-gated, some required credentials, and public API-friendly probes produced both useful signals and noise.

At the same time, the current source overlap appears low. This suggests that each source can add value, but also that the market is fragmented.

The resulting risk is:

```text
If expected employers are not visible in the pipeline, the issue may be our acquisition boundary rather than the market.
```

S2E therefore checks expected and discovered employers against the current database before selecting another source target.

## Candidate Groups

### Strategic expected candidates

These are employers that should be watched because they fit the target market or region:

- HDI Group
- Dirk Rossmann GmbH
- Finanz Informatik GmbH & Co. KG
- WERTGARANTIE Group
- VHV Gruppe
- Talanx

### Aggregator-discovered candidates

These are company signals surfaced during S2D and worth checking against the current pipeline:

- SumUp
- Cordes & Graefe KG
- Quantum-Systems GmbH
- 1KOMMA5° as already-active control case

### Active source control

S2E also exports unique company names per current source from the hot store. This supports the current defensive use of aggregators such as StepStone as bounded company-discovery input.

This does not promote aggregator content into canonical evidence. It only helps discover possible employer-origin follow-up candidates.

## Implemented Review Shape

S2E adds a read-only script:

```bash
python -m scripts.review_employer_source_candidates \
  --export-dir exports/employer_candidate_review
```

The script:

- reads the current local database
- does not write to the database
- does not make external requests
- checks expected and discovered employers against `raw_jobs`, `silver_jobs`, `silver_processing_decisions` and `ingestion_runs`
- exports unique company names per source for bounded discovery review

## Output Files

```text
exports/employer_candidate_review/
├── employer_candidate_review_summary.csv
├── employer_candidate_review_details.csv
├── employer_candidate_review_manifest.json
└── source_unique_company_discovery.csv
```

### Summary CSV

The summary CSV contains one row per candidate:

- candidate group
- current raw visibility
- current Silver visibility
- source names
- matched aliases
- matched search terms
- visibility status
- false-negative signal
- likely gap type
- recommendation

### Details CSV

The details CSV contains matched raw/Silver rows for inspection. It is intended for local review only and should not be treated as a canonical dataset.

### Unique Company Discovery CSV

The unique company discovery CSV contains company names extracted from the current hot store per source.

This is especially useful for bounded aggregator review:

```text
Use StepStone and similar bounded sources to discover company names,
then validate stronger employer-origin or ATS-near source paths.
```

It is not a reason to broaden StepStone aggressively.

## Interpretation Boundary

S2E is a review workflow, not a connector.

A candidate can be:

- visible in Silver
- visible only in raw and skipped/filtered
- visible only in raw and not promoted
- not visible in the current database

The last case should be treated as a signal, not as a final truth.

For strategic expected employers, missing visibility means:

```text
Investigate employer-origin path and search-term gap before assuming the market is covered.
```

For aggregator-discovered employers, missing visibility means:

```text
Validate employer-origin or ATS path before connector work.
```

## Relation to Search-Term Quality

S2E is an early bridge to the later search-quality chapter.

It does not solve false negatives completely, but it creates the first structured evidence for questions such as:

- Did a known relevant employer appear in any source?
- Did it reach Silver?
- Was it skipped due to relevance/accessibility filtering?
- Which search terms made it visible?
- Is the likely gap source coverage, search vocabulary, fetch limit or Silver filtering?

## Non-Goals

S2E does not fetch company career pages.

S2E does not scrape aggregators.

S2E does not make source activation decisions automatically.

S2E does not solve search-term quality. It creates review evidence for the next decision.

## Implementation Note: Pre-Gold Refactoring Candidate

The current S2E review script intentionally prioritizes false-negative visibility over structural refactoring. It contains short-term SQL-template handling for source-family detection, including psycopg-escaped literal wildcards such as `LIKE 'greenhouse:%%'` and `LIKE 'personio:%%'`.

This is acceptable for the S2E read-only review phase, but should be refactored before Gold-layer work starts.

Preferred refactoring direction:

- replace source-family wildcard checks with clearer prefix semantics such as `starts_with(source_name, 'greenhouse:')`
- introduce shared source-family helpers for Greenhouse, Personio and future ATS families
- centralize raw title/company extraction per source family
- reduce duplicated SQL template logic in review scripts
- update documentation after the refactoring so docs describe the final Gold-ready implementation rather than this interim review-script shape

This refactoring is intentionally deferred because the immediate S2E priority is to quantify false-negative risk and employer visibility before adding more sources or Gold-layer trend logic.

## Silver Gate Review Principle

Silver is intentionally stricter than Bronze. Raw jobs may be broad, noisy or exploratory; Silver should contain only jobs with enough canonical relevance evidence.

However, strict must not become blind-strict. Strategic employer candidates that are visible in Raw but not in Silver require explainable rejection evidence.

A raw-only strategic candidate does not automatically indicate a Silver bug. It does indicate that the project should be able to explain one of the following:

- the visible roles are not actually relevant for the target profile
- the location, remote or accessibility signal is insufficient
- the role title is misleading but the job is not a good fit
- the search profile is too narrow
- the Silver gate is too strict for a relevant role variant
- the better next step is employer-origin validation rather than relaxing Silver globally

This makes raw-only strategic candidates a review signal, not an automatic inclusion signal.

## Company Discovery Radar Boundary

Company Discovery Radar is a source-analysis role, not a full ingestion role.

Its purpose is to identify potential employer-origin or ATS-near candidates from bounded aggregator signals. It is not intended to create a hidden aggregator scraping layer or a second job database.

For this project, StepStone is retained as a bounded commercial aggregator observation source. Its value is company discovery and market visibility evidence, not full market coverage.

The StepStone boundary remains:

- one bounded result page
- no pagination
- no detail-page crawling
- no full fetch
- no broad cross-aggregator scraping
- no assumption that observed company counts represent full platform coverage

Future company discovery should prefer defensible access paths such as existing project sources, employer-origin sources, ATS-near sources and API-based aggregator candidates where terms and scope are compatible with the project gates.

## Deferred Pre-Gold Refactoring Candidate

The current S2E review script prioritizes false-negative visibility over structural refactoring. It contains short-term SQL-template handling for source-family detection, including psycopg-escaped literal wildcards such as `LIKE 'greenhouse:%%'` and `LIKE 'personio:%%'`.

This is acceptable for the S2E read-only review phase, but should be refactored before Gold-layer work starts.

Preferred refactoring direction:

- replace source-family wildcard checks with clearer prefix semantics such as `starts_with(source_name, 'greenhouse:')`
- introduce shared source-family helpers for Greenhouse, Personio and future ATS/source families
- centralize raw title/company extraction per source family
- reduce duplicated SQL template logic in review scripts
- update documentation after the refactoring so docs describe the final Gold-ready implementation rather than this interim review-script shape

This refactoring is intentionally deferred because the immediate S2E priority is to quantify false-negative risk and employer visibility before adding more sources or Gold-layer trend logic.

## AI Assistant Scope Decision

Because aggregators are increasingly treated as Company Discovery Radar sources rather than primary job evidence, semantic duplicate detection is no longer a core prerequisite for source expansion.

The project should first prioritize employer-origin and ATS-near source coverage, deterministic source-priority rules, canonical-source evidence modeling and Silver-gate explainability.

An AI-based assistant may still be valuable later as an audit/review layer for ambiguous duplicate candidates, false-negative analysis and search-term discovery, but it should not replace deterministic canonicalization and source-priority rules.
