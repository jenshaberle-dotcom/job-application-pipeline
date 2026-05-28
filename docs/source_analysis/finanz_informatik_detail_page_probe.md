# Finanz Informatik Detail-Page Probe — S2K

## Purpose

S2K adds a tiny detail-page probe after the S2J export-first listing spike.

The goal is not to implement a connector. The goal is to inspect whether the very small S2J candidate set provides enough detail-page evidence to justify later RawJobRecord-shaped preview work or a minimal connector decision.

## Boundary

S2K is deliberately small:

- read-only
- export-first
- no database writes
- no raw HTML persistence
- no connector implementation
- no source-target activation
- no OnApply crawling
- only selected Hannover S2J candidates
- maximum three detail pages by default

## Candidate Selection

S2K reads:

    exports/s2j_finanz_informatik_export_first_spike/finanz_informatik_spike_candidates.csv

It keeps only rows where:

- `detail_fetch_needed_later` is true
- `location_signal` is `hannover`
- the S2J recommendation is either:
  - `strong_listing_candidate_for_review`
  - `job_candidate_low_profile_signal`

Deferred Frankfurt/Muenster rows are intentionally not fetched unless a future listing-level remote/Germany-wide signal is visible and separately documented.

## Export Output

S2K writes:

    exports/s2k_finanz_informatik_detail_page_probe/

Expected files:

- `finanz_informatik_detail_page_probe.csv`
- `finanz_informatik_detail_page_probe_summary.csv`
- `finanz_informatik_detail_page_probe_manifest.json`
- `finanz_informatik_detail_page_probe_review.md`

## Interpretation Boundary

Positive S2K rows are manual review evidence only.

S2K does not approve:

- Bronze persistence
- connector activation
- recurring ingestion
- broad detail-page fetching
- OnApply usage

## Decision Use

S2K should answer whether Finanz Informatik still looks useful after detail-page evidence is checked.

A useful result would show detail pages with enough title, location, profile, remote/hybrid or description evidence to support a later RawJobRecord-shaped preview.\n\nExclusion terms are scoped to the candidate URL, path and page title so that global career navigation, footer links or generic employer pages do not incorrectly exclude otherwise relevant detail pages.

A weak result should lead to deferring Finanz Informatik as a manual/watchlist source and returning focus to BA coverage, search-term quality or Silver/Gold analysis.

## Source-Value Interpretation

S2K also treats Finanz Informatik as a precision source, not as a broad-volume source.

For employer-origin sources, even a very small number of relevant, non-duplicate candidates can justify source value if they add incremental evidence not already available from BA or other sources.

A later decision should therefore evaluate incremental uniqueness against existing raw and Silver evidence before any connector or Bronze persistence decision.
