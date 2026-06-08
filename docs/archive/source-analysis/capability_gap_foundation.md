# S5H Capability Gap Foundation

## Purpose

S5H turns candidate intelligence and search-term value signals into explicit,
reviewable capability gaps.

The goal is not to decide whether Jens can or cannot do a job. The goal is to
make the learning delta visible:

- which skills are important for the Data Engineer direction,
- which of those skills already have market/vocabulary support,
- which gaps should be practiced in the project or handled through learning,
- and which gaps may later become certification candidates.

## Scope

S5H adds:

- `capability_gap_scores`
- `src/search_intelligence/capability_gap.py`
- `scripts/run_capability_gap_agent.py`
- migration and unit tests

## Interpretation

The current score is an initial heuristic.

It combines:

- candidate capability,
- career-direction weight,
- growth gap,
- and supporting search-term value signals.

This is intentionally not a final hiring probability model. The score is meant
to guide learning and portfolio prioritization.

## Boundaries

S5H does not:

- mutate search profiles,
- activate sources,
- register connectors,
- write Bronze jobs,
- schedule runs,
- or decide application suitability.

## Follow-up

A later block should compare actual jobs pairwise and use those comparisons to
calibrate the candidate profile and capability-gap weighting.
