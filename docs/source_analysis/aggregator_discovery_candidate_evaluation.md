# Aggregator Discovery Candidate Evaluation — S2D

## Purpose

S2D evaluates aggregator/discovery candidates in one bounded review step.

The goal is not to turn aggregators into connectors. The goal is to quickly test whether the aggregator source family can produce better employer-origin, ATS or company-board candidates than the current shortlist.

This follows the S2C hard-gate decision in `docs/source_analysis/aggregator_discovery_feasibility_matrix.md`.

## Current Interpretation

The current source data suggests a strong source-fragmentation signal:

1. Overlap between the active sources is low.
2. Therefore, each clean source can still add value.
3. The job market appears fragmented across Bundesagentur, StepStone, ATS boards and company-specific targets.
4. Large aggregators may have high human discovery value, but the project cannot assume they provide defensible automated market coverage because access, storage and automation boundaries are restrictive.
5. The practical way around this is to use aggregator/discovery candidates to identify better employer-origin or ATS-near sources instead of forcing aggregators into Bronze ingestion.

This reinforces the existing source strategy: more sources can be valuable, but only if their acquisition path is explainable, defensive and maintainable.

## Implemented Evaluation Shape

S2D adds a read-only script:

```bash
python -m scripts.evaluate_aggregator_discovery_candidates \
  --export-dir exports/aggregator_discovery_candidate_evaluation
```

The script evaluates these source groups in one run:

| Source | Role in S2D | Probe behavior |
|---|---|---|
| LinkedIn | `research_only_discovery_signal` | Not probed by design. Hard-gated unless a suitable approved API path exists. |
| XING | `research_only_discovery_signal` | Not probed by design. Hard-gated for search ingestion unless a suitable API path exists. |
| Indeed | `research_only_discovery_signal` / `reference_only` | Not probed by design. Hard-gated for independent broad ingestion unless approved partner/API use exists. |
| Glassdoor | `reference_only` | Not probed by design. No harvesting or operational job evidence. |
| StepStone | `existing_defensive_source` | Not probed by this script. Existing one-page boundary remains in place. |
| Arbeitnow | `bounded_discovery_probe_candidate` | Public API probe with minimal evidence export. |
| Adzuna | `bounded_discovery_probe_candidate` | Credentialed API probe only when `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` are present. |
| Jooble | `bounded_discovery_probe_candidate` | Credentialed API probe only when `JOOBLE_API_KEY` is present. |
| Remotive | `market_signal_sampler_candidate` | Public API probe for remote-market signal only. |

## Output Files

The script exports:

```text
exports/aggregator_discovery_candidate_evaluation/
├── aggregator_discovery_candidate_evaluation.csv
├── aggregator_discovery_candidate_matches.csv
└── aggregator_discovery_candidate_manifest.json
```

### Summary CSV

The summary CSV explains per platform:

- hard-gate status
- legal / terms boundary
- automation boundary
- probe status
- request count
- returned records
- matched records
- matched companies
- recommendation

### Matches CSV

The matches CSV contains minimal discovery evidence only:

- platform
- query
- title
- company
- location
- remote signal
- URL
- source job id
- matched terms

It intentionally does not export full job descriptions.

### Manifest

The manifest records the interpretation boundary:

- no database writes
- no detail pages fetched
- no raw content persistence beyond minimal discovery evidence
- hard-gated platforms remain research-only/reference-only
- positive API matches are employer-origin or ATS discovery leads, not canonical job evidence

## Why This Is Not a Manual Monitoring Workflow

A source that requires recurring manual monitoring to create value is not a pipeline source.

S2D is therefore not a daily manual aggregator review. It is a bounded, one-off or sporadic source-family evaluation step.

Valid use:

```text
run occasionally -> identify candidate employers / source targets -> validate employer-origin or ATS source -> decide whether to ingest that source
```

Invalid use:

```text
open aggregators every day -> manually copy jobs -> pretend this is source coverage
```

## Decision Use

S2D should answer these questions:

- Do API-friendlier aggregators produce relevant German or remote job signals?
- Do they surface employers not covered by the current sources?
- Are the resulting employers better candidates than another Greenhouse/Personio board?
- Is the evidence strong enough to validate one employer-origin or ATS-near target?
- Or do the results confirm that the current better path is direct employer/source-target research?

## Non-Goals

S2D does not implement a connector.

S2D does not authorize scraping, browser automation, login automation, account automation, CAPTCHA handling, proxy usage or third-party scraped-data APIs.

S2D does not turn aggregator content into canonical job evidence.

S2D does not persist aggregator descriptions as raw job records.
