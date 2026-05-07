# ADR-001 — Use Real Job Market Sources

## Status

Accepted

---

## Context

The project aims to become a realistic engineering and portfolio project instead of a simplified tutorial implementation.

Tutorial APIs provide stable and simplified data structures but fail to represent real-world ingestion challenges.

The project should expose realistic problems such as:
- inconsistent data quality
- varying source structures
- duplicate handling
- detail page ingestion
- anti-bot mechanisms
- pagination complexity
- source-specific limitations

---

## Decision

Use real-world job market sources as ingestion targets.

The initial source is:
- Bundesagentur für Arbeit

Planned additional sources:
- StepStone
- LinkedIn Jobs
- Greenhouse ATS
- Workday-based career systems

---

## Consequences

### Positive
- realistic engineering challenges
- stronger portfolio relevance
- better architecture decisions
- more representative data structures
- realistic ingestion complexity

### Negative
- higher implementation complexity
- less stable source interfaces
- potential anti-bot restrictions
- more maintenance effort
