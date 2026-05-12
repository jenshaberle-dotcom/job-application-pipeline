# ADR 021: Expand Source Capability Model Before Complex Sources

## Status

Accepted

## Context

The project started with a structured public API source and later added a full-fetch ATS board source.

These two sources already showed that real-world job sources differ significantly in filtering behavior, metadata completeness and ingestion strategy.

The next planned source candidates include commercial job portals and more complex ATS systems.

Examples include:

- StepStone
- Workday
- Personio
- Lever
- direct company career pages

These sources may introduce higher operational complexity, including HTML parsing, browser-like access patterns, unstable identifiers, incomplete metadata, pagination complexity, anti-bot behavior and legal or ethical constraints.

The previous compact capability matrix was useful for the first connectors, but it is not detailed enough to guide responsible implementation of more complex sources.

## Decision

The project will expand source capability documentation before implementing additional complex production connectors.

The expanded model documents:

- access model
- filtering capability
- identifier quality
- publication date quality
- pagination model
- operational risk
- heartbeat strategy
- ingestion strategy

Complex sources should be evaluated before being implemented as production connectors.

Commercial job portals should first go through source analysis and, if justified, a limited technical spike.

## Consequences

### Positive

- Improves source comparison quality
- Makes connector decisions more explainable
- Reduces risk of ad-hoc scraping implementations
- Supports future StepStone evaluation
- Supports heartbeat planning
- Supports dashboard interpretation
- Keeps source-specific complexity visible

### Negative

- Adds documentation overhead
- May slow down connector implementation
- Requires maintaining source profiles as knowledge evolves

## Future Implementation Notes

The expanded capability model may later be reflected in code.

Possible future options include:

- extended connector capability classes
- source configuration metadata tables
- heartbeat strategy configuration
- dashboard labels for source reliability and risk
- source evaluation templates

For now, the expanded model remains documentation-first.

## Related Documentation

- `docs/data_sources/source_capabilities.md`
- `docs/source_evaluation.md`
- `docs/observability/source_health_and_heartbeat.md`
