# Relevance and Search Quality Planning

## Relationship to Existing Relevance Logic

This planning document extends, but does not replace, the existing relevance boundary.

See also:

- `docs/decisions/adr/016_define_ingestion_scope_and_relevance_boundaries.md`
- `docs/decisions/adr/024_define_search_quality_and_relevance_evaluation_boundary.md`
- `docs/reference/scoring-and-gates/relevance_strategy.md`
- `src/silver/relevance.py`

The current Silver relevance logic answers whether a raw job is eligible for Silver normalization.

Candidate-fit scoring and search-term quality evaluation are separate later concerns.


## Required Lineage Foundation

Search-quality metrics require reliable search-term lineage.

An ingestion run should preserve the specific search term that triggered it, not only the broader search profile. Without this, multiple search terms inside one profile cannot be compared safely.

The intended lineage path is:

`search_terms` → `ingestion_runs` → `job_observations` → `raw_jobs`

This allows later analysis of term usefulness, duplicate rates, overlap and unique discoveries without adding scoring logic to connectors.

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

## Continuous Search Profile Calibration

Search profiles should not be treated as static forever.

Job-market terminology changes over time.

Skill focus inside a profile can also shift over time.

A profile that works well today may miss valuable jobs later if new role titles, skill clusters or source-specific terminology appear.

The project should therefore support recurring search-profile calibration.

Calibration should be based on evidence from loaded jobs, observations, duplicate patterns, Silver eligibility, later candidate-fit signals and controlled discovery checks.

Important questions:

- Which search terms still produce useful jobs?
- Which terms mostly produce noise?
- Which terms uniquely discover valuable jobs?
- Which valuable jobs are only found by indirect or exploratory terms?
- Which relevant role titles or skills are missing from the current profile scope?
- How do these patterns differ across Bundesagentur, Greenhouse and StepStone?

## Controlled Discovery Checks

A controlled discovery check is a bounded analysis run.

It is designed to detect potential false negatives without turning the project into broad crawling.

Discovery checks may use:

- broader role terms
- alternative source-specific terminology
- adjacent skill terms
- emerging market terms
- one-off exploratory search profiles

Discovery results should be compared against regular profile results.

A useful discovery finding is not merely a larger result set.

A useful discovery finding is evidence that a valuable job or recurring valuable term is missed by the regular profile.

Potential outputs:

- candidate search terms to add
- noisy search terms to narrow or remove
- profile scope changes to review
- source-specific terminology differences
- dashboard indicators for search-profile drift

Discovery checks should create reviewable evidence.

They should not automatically rewrite productive search profiles.

