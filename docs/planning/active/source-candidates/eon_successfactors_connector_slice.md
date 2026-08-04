# E.ON SuccessFactors Connector Slice

## Status

Planned implementation slice. This file binds the scope before code changes.

## Evidence

- the E.ON Digital Technology corporate origin is operator-verified;
- the corporate page remains blocked for the approved non-browser collector with HTTP 403;
- the public E.ON Germany career board at `careers.eon.com` returned HTTP 200;
- the bounded feasibility probe classified it as `likely_feasible` with one job-search page and concrete job-detail evidence;
- the source target exposes stable-looking numeric job identifiers in detail URLs.

## Goal

Add a reusable, bounded SuccessFactors-style career-board connector with E.ON Germany as the first configured target. The connector must:

1. fetch one public listing page;
2. extract concrete same-host job-detail URLs;
3. rank only title-relevant, non-entry-level candidates;
4. fetch at most five detail pages;
5. retain only jobs whose detail page identifies `E.ON Digital Technology GmbH`;
6. emit reviewable `RawJobRecord` objects;
7. expose a no-write live preview.

## Boundaries

- no browser automation;
- no access-control bypass;
- no pagination in this slice;
- no provider request;
- no database write;
- no Bronze or Silver persistence;
- no active search profile;
- no scheduler change;
- code-backed connector registration is allowed, but does not activate ingestion;
- output is review-only until a separate controlled activation slice.

## Acceptance

- fixture tests cover listing extraction, exclusions, employer filtering, stable IDs, bounds, and registry creation;
- live preview performs at most one listing request plus five detail requests;
- live preview reports zero provider requests and zero pipeline mutation;
- full CI is green;
- productive activation remains closed.
