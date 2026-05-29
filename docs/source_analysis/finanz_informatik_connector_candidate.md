# Finanz Informatik Connector Candidate — S2M Preparation

## Purpose

This document records the Finanz Informatik connector candidate prepared after S2J/S2K and alongside S2L incremental uniqueness review.

The connector candidate exists as code, but it is not activated by a search profile and is not presented as a production connector decision.

## Connector Boundary

The connector candidate is intentionally bounded:

- one configured listing page
- maximum three detail pages
- Hannover / target-scope candidates only
- no Frankfurt or Muenster detail fetching without visible remote/Germany-wide signal
- no OnApply crawling
- no arbitrary crawling
- no broad all-job ingestion
- relevance gates before RawJobRecord creation
- no raw HTML persistence

## Activation Boundary

The patch does not add a database migration or active search profile for Finanz Informatik.

Activation should require a later decision after S2L shows whether the selected candidates are incrementally unique.

## Source-Value Framing

Finanz Informatik should be evaluated as a precision source.

A small number of relevant, non-duplicate employer-origin candidates can justify source value if they add evidence that broad sources do not provide.

## Next Decision

After S2L, decide one of:

1. keep Finanz Informatik as a manual/watchlist source
2. build a RawJobRecord preview from the connector candidate
3. add a controlled inactive/active source profile only after explicit review
4. defer connector activation if candidates are already known elsewhere
