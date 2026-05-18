# ADR-024: Define search quality and relevance evaluation boundary

## Status

Accepted

## Context

The project already separates ingestion, Bronze storage, Silver normalization and later Gold/dashboard views.

ADR-016 defines that ingestion scope, relevance filtering and downstream scoring are separate concerns.

The current Silver relevance logic is a deterministic gate that helps decide whether a raw job is eligible for Silver normalization.

Controlled StepStone ingestion showed a broader problem:

- real job sources return noisy results
- multiple search terms create overlapping observations
- broad search terms can produce false positives
- narrow or outdated search terms can miss valuable jobs
- market language and skill focus can change over time

The most important risk is not only that irrelevant jobs are loaded.

The more important long-term risk is that valuable jobs are never loaded because the current search profiles and search terms do not cover the market well enough.

This makes false-negative evaluation and search-profile calibration a core future analytics topic.

## Decision

Search quality, false-positive analysis, false-negative analysis and candidate-facing relevance evaluation are not connector responsibilities.

They belong after raw ingestion, most likely on top of Bronze observations, Silver-normalized data or a dedicated scoring/evaluation layer feeding Gold/dashboard views.

The project treats the following as separate responsibilities:

| Concern | Responsibility |
|---|---|
| Connector | Fetch source data and preserve source-specific evidence |
| Bronze | Store raw source records, search profiles, search terms and observations |
| Silver relevance | Decide whether a raw job is eligible for canonical Silver normalization |
| Search quality evaluation | Evaluate whether search terms and profiles find useful jobs |
| False-positive analysis | Identify loaded jobs that are weak matches or source-side noise |
| False-negative analysis | Detect potentially valuable jobs missed by current profiles or terms |
| Candidate-fit scoring | Estimate how well a normalized job matches a candidate profile |
| Gold / Dashboard | Present KPIs, trends, rankings, review queues and calibration signals |

## Primary Focus

The primary focus is sustainable search quality evaluation.

This includes:

- measuring search-term usefulness
- identifying noisy terms
- identifying terms that uniquely discover valuable jobs
- detecting weak source-side matching behavior
- supporting evidence-based changes to search profiles
- making search-profile quality visible over time

Candidate-fit scoring may later support this analysis, but it is not the only goal.

## False Positives

False positives are jobs that are loaded but do not match the intended profile well.

They may be caused by:

- broad source-side search behavior
- generic IT terms
- fuzzy matching by commercial job portals
- weak title-only matches
- skill mentions outside the actual role focus

False-positive analysis should happen after ingestion.

It should not be implemented inside connectors.

## False Negatives

False negatives are potentially relevant jobs that are missed by current search profiles, search terms or source configurations.

This is strategically important because missed jobs cannot be evaluated, scored or displayed later.

False-negative evaluation should therefore become a recurring analysis topic.

It should help answer:

- Are the current search terms still aligned with the market?
- Are relevant jobs appearing under different role titles?
- Are new skill clusters emerging?
- Are some sources using different terminology than expected?
- Are valuable jobs only found by exploratory or indirect search terms?
- Should the profile scope be adjusted?

## Controlled Discovery Checks

The project may later introduce controlled discovery checks.

A discovery check is not broad crawling.

It is a bounded analysis run used to evaluate whether current search profiles miss valuable jobs.

Possible discovery approaches:

- run broader or alternative search terms at a controlled frequency
- compare discovered jobs against regular profile results
- identify high-quality jobs found only by discovery terms
- extract recurring role, title or skill signals from strong matches
- propose new search terms based on evidence
- retire or narrow search terms that mostly produce noise

Discovery results should not automatically change productive profiles.

They should create reviewable evidence for profile calibration.

## Search-Term Quality

Search-term quality should evaluate how useful a term is within and across sources.

Possible later metrics:

- total observations per search term
- unique raw jobs per search term
- duplicate observation rate
- Silver inclusion rate
- Silver skip rate
- false-positive rate
- strong-match rate
- unique strong matches found only by that term
- source-specific noise indicator
- trend over time

Search-term quality should support improving search profiles without turning the project into an uncontrolled crawler.

## Candidate-Fit Scoring

Candidate-fit scoring is still relevant, but it is a later downstream concern.

It may use:

- role family
- skill matches
- seniority indicators
- location and remote compatibility
- employment type
- company or industry relevance
- CV-derived candidate profile signals
- source quality and field completeness

Candidate-fit scoring can support:

- ranking
- dashboard views
- strong-match detection
- search-term quality metrics
- false-positive and false-negative review

It must not be implemented inside connectors.

## Consequences

Connectors remain source-focused and simple.

Bronze remains evidence-preserving.

Silver relevance remains a deterministic eligibility gate for normalization.

Search quality and profile calibration become measurable instead of anecdotal.

False-negative risk becomes visible as an explicit analytics problem.

Future dashboards can show whether search profiles continue to cover the relevant market.

## Non-Goals

This ADR does not implement:

- a candidate-fit scoring algorithm
- an LLM-based matcher
- automatic profile updates
- automatic search-term discovery
- a new database schema for scores
- dashboard views
- connector-level candidate filtering
- broad crawling
