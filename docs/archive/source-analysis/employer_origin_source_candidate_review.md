# Employer-Origin Source Candidate Review — S2F

## Purpose

S2F validates selected employer-origin career sources after the S2E employer-candidate and false-negative review.

The goal is not to build a connector yet. The goal is to answer:

    Which employer-origin or ATS-near source paths are reachable, defensible and promising enough for manual review before a controlled source-target activation?

This keeps the project between two unsafe extremes:

- assuming the current source set already covers the relevant market
- immediately building new connectors from every company signal

## Why This Exists

S2E showed that employer visibility can fail in different ways:

- a candidate may be visible in Silver
- a candidate may be visible only in Raw
- a candidate may be missing entirely
- bounded aggregator evidence may reveal company names, but not enough canonical job evidence

S2F therefore checks selected career/search pages directly before implementation decisions are made.

## Implemented Review Shape

S2F adds a bounded read-only script:

    python -m scripts.evaluate_employer_origin_sources \
      --export-dir exports/employer_origin_source_validation

The script:

- performs one configured request per employer target
- does not fetch detail pages
- does not write to the database
- extracts only static HTML/text signals
- detects simple ATS hints such as SuccessFactors, Personio, Greenhouse, Workday or Softgarden
- counts rough job-page vocabulary signals without treating them as parser evidence
- exports review artifacts for inspection

## Current Candidate Set

The first S2F pass intentionally stays small:

| Candidate | Reason |
|---|---|
| HDI Group | Strategic insurance/Hannover target and cross-source visibility signal. |
| Dirk Rossmann GmbH | Regional relevance and repeated current-source signal. |
| Finanz Informatik GmbH & Co. KG | Strong IT/Data domain fit and regional relevance. |
| WERTGARANTIE Group | Useful StepStone/company-discovery validation control case. |

Further candidates such as VHV, Hannover Rück, enercity, TIB or ivv should be added in a later batch only after the S2F shape is proven and documented.

## Output Files

The script exports:

    exports/employer_origin_source_validation/
    ├── employer_origin_source_validation.csv
    └── employer_origin_source_validation_manifest.json

### Validation CSV

The CSV contains one row per candidate:

- key
- company name
- source-family candidate
- source-type candidate
- configured URL
- final URL
- HTTP status
- static page title
- HTML byte size
- matched profile terms
- detected ATS hints
- rough job-signal count
- recommendation
- notes
- error, if any

### Manifest

The manifest records the defensive boundary:

- no database writes
- external requests are made
- no detail pages are fetched
- one configured URL per candidate
- positive findings require manual review before activation

## Interpretation Boundary

S2F is a validation workflow, not a connector.

A reachable page with an ATS hint is a candidate for manual review, not proof that a connector should be built.

A reachable page without static profile-term matches is not automatically useless. Some modern career pages render jobs dynamically, hide job data behind API calls or require query parameters. That is why S2F uses recommendations such as:

- `connector_candidate_after_manual_review`
- `ats_near_candidate_manual_review`
- `employer_origin_candidate_manual_review`
- `reachable_needs_manual_review`
- `reachable_low_signal_defer`
- `defer_or_fix_url`

The recommendation is a review aid. It is not an automatic source-activation decision.

## Relation to Company Discovery Radar

S2F is the follow-up step after Company Discovery Radar signals.

Bounded aggregator or StepStone evidence may identify interesting employers. S2F checks whether those employers expose a cleaner origin or ATS-near acquisition path.

The desired flow is:

    bounded discovery signal
    -> employer candidate appears interesting
    -> employer-origin / ATS-near path validation
    -> manual source-target decision
    -> only then connector/profile implementation

## Non-Goals

S2F does not implement a connector.

S2F does not crawl employer websites.

S2F does not fetch job detail pages.

S2F does not store raw HTML in the database.

S2F does not promote employer-origin pages to canonical evidence automatically.

S2F does not replace Silver-gate or search-term quality analysis.
