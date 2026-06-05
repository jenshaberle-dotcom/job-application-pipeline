# StepStone Fetch-Time Exclusion Feasibility Audit

## Purpose

This note documents EO-002A.1: a bounded feasibility audit for StepStone fetch-time company exclusion.

The goal is to distinguish between:

- one failed implementation attempt
- and a disproven concept

The failed implementation attempt so far is the minus-search-string approach.

## Context

The project observed that StepStone provides repeated market evidence for already-known companies. Local post-fetch suppression can prevent duplicate downstream handling, but it cannot make StepStone refill a top-25 result page with lower-ranked companies.

The desired capability would be fetch-time exclusion:

Data Engineer in Hannover, but exclude known companies before StepStone returns the result page.

If StepStone supports this, new companies could become visible without pagination. If StepStone does not support this, the project should move to bounded refill or search-term iteration.

## Known failed method

The following search string was tested:

Data Engineer -HDI -Finanz Informatik -enercity -Ratiodata -Deutsche Bahn -adesso

Result:

- StepStone did not interpret this as reliable company exclusion.
- Known companies still appeared.
- The negative variant changed the search behavior, but not in a controlled exclusion/refill way.
- The method is therefore not suitable for production use.

Conclusion:

Minus syntax is rejected.

This does not yet reject fetch-time exclusion as a concept.

## Audit questions

The feasibility audit checks:

1. Does StepStone expose a documented or discoverable company/employer exclusion parameter?
2. Does the HTML or embedded page data contain filter/facet metadata that suggests such a parameter?
3. Do alternative syntaxes such as NOT, quoted NOT, or query-like variants behave differently?
4. Do any variants remove known companies while keeping the intended Data Engineer search intent?
5. Do any variants produce a refill effect without drifting into unrelated search results?

## Defensive boundaries

The audit must remain bounded:

- no login
- no scraping bypass
- no detail pages
- no pagination
- no DB writes
- no Bronze writes
- no candidate creation
- no connector activation
- no scheduler changes
- small number of requests only
- human review before any project behavior changes

## Decision criteria

Fetch-time exclusion remains viable only if a tested variant or discoverable parameter:

- reliably removes known companies,
- preserves the original search intent,
- produces new relevant companies,
- is stable enough to document and test,
- and does not require brittle or evasive behavior.

If no such mechanism is found, EO-002A should move to bounded refill and/or search-term iteration.

## Current decision state

Status: under audit.

Minus syntax: rejected.

Fetch-time exclusion concept: not yet rejected.
