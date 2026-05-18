# Relevance and Search Quality Planning

## Purpose

This document captures future work around job relevance, candidate fit scoring and search-term quality evaluation.

The topic became visible during controlled StepStone ingestion validation.

The StepStone connector successfully ingested result-card records, but the result set showed broad and noisy source-side matching behavior.

This is not a connector defect.

Connectors should fetch and preserve source data. They should not decide whether a job is a good fit for a specific candidate profile.

## Problem

Search terms such as `Data Engineer`, `Analytics Engineer`, `ETL`, `Data Platform`, `Data Warehouse`, `Big Data` and `Python SQL` can produce overlapping and noisy results.

Some results may be:

- strong matches
- weak but adjacent matches
- false positives caused by broad source-side search behavior
- useful jobs that appear only through indirect search terms
- potentially relevant jobs missed by the current search-term set

This affects later dashboard quality, confidence scoring and candidate-facing recommendations.

## Important Questions

- How well does a job match the candidate profile?
- Which search terms produce high-quality matches?
- Which search terms mostly produce noise?
- Which good jobs appear through unexpected search terms?
- Which potentially good jobs are missed by the current search-term set?
- How does source-side search quality differ between Bundesagentur, Greenhouse and StepStone?
- Which fields are reliable enough for matching in Bronze?
- Which fields require Silver normalization before scoring?

## Possible Future Metrics

Possible metrics for Silver, Gold or dashboard layers:

- candidate fit score
- source relevance score
- search-term precision proxy
- duplicate observation count
- number of search terms that found the same job
- strong-match rate per search term
- weak-match or false-positive rate per search term
- source-specific noise indicator
- missing-field impact on scoring confidence
- profile-match confidence level

## False Positives

False positives are jobs that are technically returned by a source but do not match the intended candidate profile well.

Examples may include:

- adjacent roles with weak data-engineering relevance
- generic IT roles
- roles that mention only one broad keyword
- jobs matched because of source-side fuzzy search behavior

False-positive analysis should happen after raw ingestion, not inside connectors.

## False Negatives

False negatives are relevant jobs that may not appear because the current search terms are incomplete or too narrow.

Potential future approaches:

- compare high-quality matched jobs and extract recurring title or skill terms
- test additional search terms in controlled one-off discovery runs
- compare result overlap across sources
- track which search terms discover unique high-quality jobs
- add new search terms only when they are justified by evidence

This must be controlled to avoid turning the project into broad crawling.

## Candidate Fit Scoring

Candidate fit scoring should likely use:

- job title
- company
- location
- source-specific description or snippet
- employment type
- remote or hybrid hints
- skill keywords
- seniority indicators
- candidate profile or CV-derived skills
- source confidence and field completeness

This belongs in a later Silver/Gold or dedicated scoring layer.

It should not be part of connector logic.

## Architectural Boundary

Connectors:

- fetch source data
- preserve source-specific evidence
- expose raw records
- avoid candidate-specific relevance decisions

Bronze:

- stores raw source records and observations
- preserves source-specific fields and evidence

Silver:

- normalizes relevant fields
- derives comparable attributes
- prepares scoring inputs

Gold / Dashboard:

- exposes KPIs
- visualizes search quality
- visualizes candidate fit and relevance confidence

## Initial Decision

Do not implement relevance scoring in connectors.

Treat relevance, search-term quality and candidate fit scoring as a later dedicated topic after controlled multi-source ingestion is stable.
