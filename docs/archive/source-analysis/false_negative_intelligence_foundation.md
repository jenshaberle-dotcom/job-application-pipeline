# S5A False Negative Intelligence Foundation

## Purpose

S5A adds the first DB-backed foundation for detecting false-negative risk in the job pipeline.

The trigger case is HDI: employer-origin exploration paused the candidate because detail evidence was not strong enough, while external aggregator evidence still showed relevant Data/Analytics jobs. That contradiction is a product signal, not just a connector defect.

## Core Decision

S5A introduces **Market Evidence** as a separate concept from jobs.

Market evidence is not Bronze ingestion and not a canonical Silver job. It is a bounded observation that a source such as StepStone or LinkedIn has shown a role signal for a company.

This prevents two bad extremes:

- aggressive crawling that bloats the database
- over-suppression that hides companies with unresolved false-negative risk

## New Components

- `market_evidence`
  - stores bounded aggregator/manual sightings such as company, title, source, URL and search term
- `candidate_market_evidence_summary`
  - aggregates market evidence against employer-origin candidates
- `false_negative_risk_snapshots`
  - persists reviewable false-negative risk assessments when explicitly requested
- `src/search_intelligence/false_negative_risk.py`
  - rule-based first risk engine
- `scripts/run_false_negative_intelligence_agent.py`
  - read-first false-negative risk preview and optional snapshot writer
- `scripts/record_market_evidence.py`
  - explicit manual evidence recorder for cases such as LinkedIn alerts

## Lifecycle-aware Suppression

The StepStone suppression policy is no longer simply `known company = suppress`.

| Candidate state | Aggregator handling |
| --- | --- |
| Unknown | keep for discovery review |
| Active controlled | suppress from bounded StepStone persistence |
| Manual review / unresolved | observe as market evidence |
| Hard stop / not actionable | suppress or ignore according to lifecycle policy |

This means an unresolved candidate such as HDI does not consume discovery as a new candidate, but also does not disappear from the system. Its aggregator sightings become false-negative evidence.

## Risk Rules

The first version is deliberately rule-based:

- `critical`: unresolved candidate with five or more recent market sightings
- `high`: unresolved candidate with recent or repeated market evidence
- `medium`: candidate has evidence but no strong recent unresolved signal
- `low`: no evidence or active controlled monitoring explains the sightings

No LLM, embedding or aggressive crawler is involved in S5A.

## Search Term Gap Foundation

S5A also extracts first suggested search terms from evidence titles. This is not automatic profile mutation. It is a review signal.

Example:

- Evidence title: `Data & Analytics Engineer`
- Suggested term: `analytics`

Future S5 work can compare these suggestions against active search terms and source-specific term performance.

## Approval Workspace Integration

The Approval Workspace receives a first **False Negative Risk** section. It surfaces companies where market evidence conflicts with the current employer-origin lifecycle state.

The UI remains local, server-rendered and aligned with the 05A clean/balanced dashboard direction.

## Boundaries

S5A does not:

- activate sources
- create connector registrations
- change schedulers
- perform aggressive crawling
- mutate search profiles automatically
- use CSV/Excel/export files as pipeline inputs

S5A does write DB-backed market evidence during bounded StepStone ingestion and when manually requested through `record_market_evidence.py`. These writes are observational review state, not Bronze job persistence.


## Follow-up: S5B

S5B builds on this foundation by converting high/medium false-negative risk into proposed search terms and reassessment queue items. S5B remains review-only: it does not mutate active search profiles automatically.
