# Visual Identity: Deep Ocean Intelligence

## Purpose

The project uses a reusable visual identity to make the platform recognizable across documentation, diagrams, dashboards, presentations and future frontend work.

The visual identity must support the same engineering principles as the code and documentation:

- clarity before effects
- evidence before assumptions
- controlled source expansion
- source value over raw volume
- explicit risk boundaries
- long-term maintainability

The intended impression is:

> calm technical competence with visible analytical depth

## Style Name

**Deep Ocean Intelligence**

## Design Intent

The style should feel like a serious engineering and analytics platform, not a generic portfolio dashboard and not a gaming HUD.

It combines:

- modern dark product UI
- controlled neon accents
- operational / mission-control structure
- analytical information density
- restrained cinematic depth

The style should not become over-designed. Cinematic elements are allowed only as subtle depth cues, not as the main message.

## Core Palette

| Purpose | Token | Suggested color | Usage |
|---|---|---:|---|
| Page background | `deep-navy` | `#050A14` | Main background for dashboards, decks and dark diagrams. |
| Panel background | `ocean-panel` | `#0A1423` | Cards, dashboard panels and diagram containers. |
| Secondary surface | `slate-surface` | `#111827` | Tables, secondary panels and low-emphasis blocks. |
| Primary accent | `signal-cyan` | `#00DFFF` | Active flows, primary outlines, selected navigation, key technical focus. |
| Analytics accent | `intelligence-blue` | `#38BDF8` | Trend lines, analytics and exploration signals. |
| Governance accent | `governance-emerald` | `#22C55E` | Health, validated quality, accepted decisions. |
| Risk / watch accent | `watch-amber` | `#F59E0B` | Defensive use, warnings, watchlist state, risk notes. |
| Strategy accent | `decision-purple` | `#8B5CF6` | Gold, intelligence, strategic analysis, future vision. |
| Error / hard gate | `hard-red` | `#EF4444` | Not used, blocked, failed, hard risk. Use sparingly. |
| Main text | `text-primary` | `#F8FAFC` | Main labels and headings on dark background. |
| Muted text | `text-muted` | `#94A3B8` | Secondary notes, metadata and captions. |

## Layer Color Rules

Layer colors must remain stable across diagrams, dashboard mockups and presentation visuals.

| Platform concept | Preferred color | Meaning |
|---|---|---|
| Sources / connectors | `signal-cyan` | External acquisition and source entry points. |
| Bronze / raw evidence | `watch-amber` | Raw source evidence, provenance and historical burden risk. |
| Silver / decisions | `governance-emerald` or `signal-cyan` | Normalized, cleaned and decision-backed records. |
| Gold / analytics | `decision-purple` | Dashboard-ready insights, trends and reporting. |
| API / UI | `intelligence-blue` | Serving, interaction and application workflow. |
| Risk / blocked source | `hard-red` | Not used or blocked by acquisition policy. |

## Source Risk and Value Visualization

Source visuals must reflect the project's defensive source strategy.

The project does **not** treat all sources equally.

Required source categories:

| Category | Meaning | Visual treatment |
|---|---|---|
| Preferred / direct | Official API or employer-origin source with acceptable risk and clear value. | Green or cyan status, normal flow line. |
| Defensive / limited | Source is used only under strict operational boundaries. | Amber status, capped flow, explicit constraint label. |
| Discovery / radar | Source may help identify companies or targets but is not a production ingestion source. | Dashed line or radar marker, not a normal ingestion lane. |
| Not used / blocked | Source is excluded due to risk, instability, opacity or weak value. | Red marker, outside the active flow. |

Aggregator handling must stay explicit:

- StepStone is a defensive, limited aggregator source.
- Other aggregators are not active production sources unless a later ADR changes the decision.
- Aggregator candidates may be shown as discovery or blocked/risk items, not as normal active sources.

## Dashboard Metric Language

Dashboard labels should use clear, product-like English terms.

Preferred labels:

| Concept | Preferred label |
|---|---|
| Source health | `Source Health` |
| Incremental value | `Incremental Uniqueness` |
| Duplicate pressure / redundancy | `Duplicate Pressure` |
| Historical data burden | `Historical Burden` |
| False-negative concern | `False-Negative Risk` |
| Silver conversion | `Silver Promotion Rate` |
| Matching confidence | `Match Confidence` |
| Source evaluation | `Source Value` |
| Source lifecycle | `Source Governance` |
| Pipeline monitoring | `Operational Observability` |

Avoid literal or awkward translations such as `Duplikat-Druck` in polished dashboards or presentations.

## Language Strategy

The project uses a controlled hybrid language model.

### English for product and engineering surfaces

Use English for:

- dashboards
- UI components
- architecture labels
- API concepts
- connector contracts
- visual metric labels
- layer labels

Examples:

- `Source Health`
- `Historical Burden`
- `Incremental Uniqueness`
- `False-Negative Risk`
- `Operational Observability`

### German for reflective project narrative

Use German for:

- personal project story
- lessons learned
- interview explanations
- German-language application material
- reflective documentation where the user's reasoning is the focus

This allows the product to remain internationally readable while preserving the personal engineering story.

## Typography Guidance

Recommended font direction:

- Use a clean sans-serif style for documentation images and UI mockups.
- Avoid overly decorative sci-fi fonts for normal content.
- Use display-style typography only for hero titles or section headers.

Preferred feel:

- readable
- calm
- technical
- confident

## Visual Rules

Use:

- dark backgrounds
- subtle grid structure
- rounded panels
- restrained glow
- clear status indicators
- consistent iconography
- visible data-flow direction
- small but meaningful operational details

Avoid:

- random bright colors
- heavy cyberpunk/gaming overload
- decorative effects without information value
- raw internal file names as polished labels
- screenshots that cannot be understood without context
- overly large vision claims without implemented/in-progress/future distinction

## Implementation State Labels

Visuals that mix current state and vision must clearly distinguish:

- `Implemented`
- `In progress`
- `Planned`
- `Vision`

This prevents polished mockups from overstating the current implementation.

## Reusable Project Motifs

The following motifs should become recognizable project elements:

- layered flow: `Sources → Bronze → Silver → Gold → API/UI`
- source risk vs. source value map
- source lifecycle state cards
- historical burden trend
- incremental uniqueness score
- false-negative risk indicator
- source coverage change annotation
- dashboard health ring for platform status

## Design Quality Gate

A visual asset is acceptable only if it helps explain at least one of:

- architecture
- data flow
- source risk
- source value
- quality boundaries
- operational state
- historical trend interpretation
- future dashboard direction

If a visual asset only looks impressive but does not clarify the system, it should not be added.
