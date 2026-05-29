# Documentation Design Rules

## Purpose

This document defines how visual identity rules are applied during documentation updates.

The project should not treat visual material as an afterthought. Diagrams, dashboard mockups and presentation assets must support the same architecture and governance story as the implementation.

## Default Rule

Every documentation update that touches diagrams, dashboard descriptions, README visuals, presentation assets or frontend plans must check the **Deep Ocean Intelligence** visual identity.

Text-only documentation changes do not need to create new visuals. However, if they introduce new visual concepts, dashboard concepts or architectural diagrams, they must use the project design rules from the beginning.

## Required Checks for Documentation Updates

When a documentation change touches visual or dashboard-facing content, verify:

1. **Layer colors are consistent** with the platform color rules.
2. **Source risk categories are explicit** where sources are compared.
3. **Aggregator sources are not shown as normal active sources** unless a later ADR explicitly changes the acquisition policy.
4. **Implemented, in-progress and vision items are distinguishable**.
5. **Dashboard labels use product-quality English terms**.
6. **German narrative remains available** where personal reflection or application storytelling is needed.
7. **No raw internal file names or temporary script labels appear in polished visuals** unless the document is explicitly a technical implementation note.
8. **Visuals reduce complexity instead of adding decoration**.

## Source Visualization Rules

Source visuals must show source strategy, not only source names.

A source overview should normally distinguish:

- preferred/direct sources
- defensive/limited sources
- discovery/radar sources
- blocked/not-used aggregator candidates

StepStone must remain visually marked as defensive/limited while the current acquisition policy stands.

Other aggregators must not appear as active production sources unless a later ADR changes the policy.

## Dashboard and UI Rules

Dashboard mockups should focus on project-specific intelligence:

- Source Health
- Incremental Uniqueness
- Duplicate Pressure
- Historical Burden
- False-Negative Risk
- Silver Promotion Rate
- Match Confidence
- Source Value
- Operational Observability

Avoid generic social-media or SaaS metrics that do not belong to this project.

## README Rules

README visuals should be understandable to a technical reviewer in under 30 seconds.

The README may eventually include:

- a visual project hero
- a platform architecture overview
- a source strategy overview
- a dashboard vision preview

These visuals must stay honest about the project state.

## ADR and Design Relationship

ADRs define architectural decisions.

Design documents define how those decisions are communicated visually.

A visual rule must not contradict an ADR. If visual communication requires a new architectural decision, create or update an ADR first.

## Review Prompt

Before merging visual documentation changes, ask:

> Does this make the platform easier to understand, or only more decorative?

If the answer is mostly decorative, revise or remove the visual.
