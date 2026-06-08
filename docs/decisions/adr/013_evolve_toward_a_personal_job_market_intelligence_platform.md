# ADR-013: Evolve toward a personal job market intelligence platform

## Status

Accepted

## Context

The project originally started as a technical exploration of automated job ingestion pipelines.

The initial goal was:
- collecting job postings
- automating search processes
- experimenting with data engineering concepts
- learning ingestion and transformation architectures

However, the project evolved significantly during implementation.

The architecture now includes:
- Bronze/Silver layering
- source-preserving ingestion
- canonical modeling
- multi-source ingestion preparation
- semantic deduplication strategy
- historical observation preparation
- source evaluation
- connector abstraction
- architectural decision tracking

At the same time, the project increasingly exposes opportunities for analytical and personal decision-support functionality.

The platform can potentially provide:
- job market analytics
- skill trend analysis
- application tracking
- market visibility metrics
- source quality analysis
- semantic CV-to-job matching
- gap analysis between profile and market demand
- personalized job prioritization
- historical market movement analysis

The project therefore evolves beyond a pure ingestion pipeline.

---

## Decision

The project evolves toward a personal job market intelligence platform.

The platform is intended to support:
- ingestion
- normalization
- analytics
- visualization
- decision support
- market intelligence
- personal career development

The project intentionally combines:
- data engineering
- analytics engineering
- semantic modeling
- historical analytics
- personal workflow support

The platform may later include:
- dashboards
- visualizations
- web applications
- personal application management
- AI-assisted workflows
- recommendation systems
- semantic matching
- market intelligence metrics

The project intentionally remains grounded in realistic data engineering problems rather than becoming a purely UI-focused application.

---

## Planned Functional Areas

### Job Market Intelligence

Examples:
- top new postings
- fastest growing skills
- company hiring intensity
- source propagation analysis
- job lifetime analysis
- source freshness analysis

---

### Personal Workflow Support

Examples:
- application tracking
- application status management
- interview tracking
- AI-assisted application drafting
- follow-up reminders
- saved opportunities

---

### Skill & Gap Analysis

Examples:
- skill frequency trends
- missing skill analysis
- market demand comparison
- personal capability gap analysis
- technology trend tracking

---

### Semantic Matching

Examples:
- CV-to-job similarity
- semantic ranking
- personalized recommendations
- role clustering
- skill similarity analysis

---

## Architectural Direction

The architecture should remain modular.

Core architectural principles remain:
- source preservation
- replayability
- canonical modeling
- traceability
- separation of concerns
- incremental evolution

The platform intentionally separates:
- ingestion
- normalization
- semantic interpretation
- analytics
- visualization
- workflow support

This allows:
- independent evolution of layers
- future technology additions
- optional cloud migration
- optional analytical warehouses
- optional semantic/vector search extensions

---

## Consequences

### Positive

- The project becomes substantially more realistic.
- The architecture supports meaningful analytics.
- The platform demonstrates real-world data engineering challenges.
- The project becomes more differentiated as a portfolio project.
- Visualization and analytics become grounded in real historical data.
- The project creates value beyond technical experimentation alone.

### Negative

- Project scope increases significantly.
- Historical data management becomes more important.
- Semantic modeling complexity increases.
- Data governance concerns become more relevant.
- UI/dashboard decisions may later require frontend technologies.
- Infrastructure requirements may grow over time.

---

## Notes

The project intentionally prioritizes:
- architectural depth
- realistic data problems
- explainability
- evolutionary design
- analytical value

over maximizing the number of technologies used.

The project is intended to evolve incrementally from:
- ingestion pipeline
toward:
- analytics platform
and eventually:
- a personal job market intelligence system.
