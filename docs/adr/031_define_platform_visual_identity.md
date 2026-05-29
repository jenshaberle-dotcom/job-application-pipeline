# ADR-031: Define Platform Visual Identity and Documentation Design Rules

## Status

Accepted

## Context

The project has evolved from a local job-ingestion pipeline into a personal job market intelligence platform with source governance, Bronze/Silver/Gold layering, historical burden analysis, source value evaluation and future dashboard/API direction.

This evolution is now substantial enough that project communication must not rely on ad-hoc visuals, inconsistent Mermaid diagrams or generic presentation styling.

The project also aims to be a professional portfolio artifact. Its visual communication should therefore support the same qualities as the implementation:

- clarity
- traceability
- source-risk awareness
- data-quality awareness
- controlled scope
- platform thinking

During dashboard and presentation exploration, the project identified a preferred visual direction named **Deep Ocean Intelligence**: a calm, dark, technically credible style with restrained cyan/blue accents, analytical density and only subtle cinematic depth.

## Decision

The project will define and use a reusable visual identity for diagrams, dashboard mockups, presentation assets, README visuals and future frontend work.

The visual identity is documented under `docs/design/`.

The accepted style is named:

```text
Deep Ocean Intelligence
```

This style must be used as the default for new polished project visuals.

The project will also add documentation design rules so that future documentation updates check visual consistency whenever they touch diagrams, dashboards, architecture visuals or presentation assets.

## Visual Principles

The project visuals should communicate:

- calm technical competence
- analytical depth
- source governance
- operational observability
- layered data architecture
- defensible platform decisions

Visuals must not become pure decoration.

A visual is useful only if it clarifies at least one of:

- architecture
- data flow
- source value
- source risk
- historical burden
- false-negative analysis
- operational health
- future dashboard direction

## Color and Layer Rules

The project will use a stable color mapping for major platform concepts:

| Concept | Visual role |
|---|---|
| Sources / connectors | cyan / entry point |
| Bronze | amber / raw evidence and burden risk |
| Silver | emerald or cyan / normalized decisions |
| Gold | purple / analytics and intelligence |
| API/UI | blue / serving and interaction |
| Risk / blocked | red / hard gate or not used |

These rules apply to future diagrams, README visuals, dashboard mockups and frontend concepts.

## Source Risk Visualization

Source visuals must preserve the project's source acquisition policy.

In particular:

- direct or employer-origin sources may be shown as preferred or active when validated
- StepStone must be shown as defensive/limited while the current policy stands
- other commercial aggregators must not be shown as normal active production sources unless a later ADR changes the policy
- discovery sources must be visually distinct from production ingestion sources
- blocked or not-used candidates must be shown as risk or exclusion, not as active coverage

This prevents visual material from accidentally weakening the project's responsible acquisition stance.

## Language Strategy

The project will use a controlled hybrid language strategy.

English is preferred for:

- dashboard labels
- architecture labels
- UI concepts
- product metrics
- connector contracts
- engineering surfaces

German remains appropriate for:

- project story
- lessons learned
- application storytelling
- reflective documentation
- German-language communication

This keeps the product surface internationally readable while preserving the user's personal engineering narrative.

## Consequences

### Positive

- makes the project visually recognizable
- supports a stronger GitHub and portfolio presentation
- keeps future dashboard/UI work aligned with the project identity
- prevents generic or inconsistent visuals
- makes risk and source-value boundaries visible
- gives documentation reviews an explicit visual quality gate

### Negative

- adds another consistency dimension to documentation work
- requires discipline to avoid over-polished visuals that overstate implementation state
- may require future regeneration of older diagrams to align with the style

## Implementation Notes

This ADR introduces documentation only.

It does not implement the frontend, dashboard or design assets yet.

Immediate follow-up work may include:

1. creating first project-style README visuals
2. refreshing architecture diagrams in the Deep Ocean Intelligence style
3. adding a source risk/value map
4. creating dashboard mockups that distinguish implemented, in-progress and planned capabilities
5. preparing reusable visual templates for future docs and presentations

## Related ADRs

- ADR-013: Evolve toward a personal job market intelligence platform
- ADR-017: Prepare API-first dashboard architecture
- ADR-024: Define search quality and relevance evaluation boundary
- ADR-026: Define source acquisition scope, canonical source strategy and source value evaluation
- ADR-029: Define historical burden retention strategy
- ADR-030: Define trend eligibility and source coverage boundary
