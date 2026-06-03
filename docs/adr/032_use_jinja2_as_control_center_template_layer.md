# ADR-032: Use Jinja2 as the Control Center Template Layer

## Status

Accepted

## Context

The Search Intelligence Control Center has reached a point where the data story is stronger than the current UI implementation. The existing control surface is functional and useful for daily review, but HTML, CSS and rendering logic are still concentrated in Python string rendering.

The project needs a more product-quality executive dashboard while avoiding a premature frontend rewrite.

## Decision

Use Jinja2 as a server-rendered intermediate UI layer for the Search Intelligence Control Center.

Jinja2 is introduced as a presentation layer only. It must not become a place for business, lifecycle, gate or source-status decisions.

The intended architecture is:

PostgreSQL / Gold read models
→ Python loaders
→ Python ViewModels
→ Jinja2 templates
→ browser-rendered Control Center

A later React frontend should be able to consume the same ViewModel shape through JSON/API endpoints.

## Dependency

Add the runtime dependency:

- `Jinja2>=3.1,<4`

Jinja2 brings MarkupSafe transitively for safe HTML escaping support.

No Node, npm, Vite, React, Dash or Streamlit dependency is introduced by this decision.

## Project Rules

1. Templates are presentation-only.
2. Gate, lifecycle, source-health and approval decisions belong in database views or Python ViewModels.
3. Jinja2 templates may branch only on already prepared display state.
4. Visual components must be backed by real project state or explicitly marked as planned.
5. No fake metrics may be presented as real metrics.
6. CSS/SVG micro-interactions are allowed if they are optional, accessible and do not hide state.
7. Animation must respect `prefers-reduced-motion` once animation is introduced.
8. The structure must keep a later React migration possible.

## Visual Direction

The Control Center follows the combined S8A target image:

- Deep Ocean Intelligence
- product-cool rather than gaming
- executive KPI strip
- source landscape and risk overview
- Dataflow Live from Bronze to Silver to Gold
- candidate lifecycle with enercity as active controlled and HDI blocked by the detail evidence gate
- Quality & Intelligence
- Activity & Alerts
- Controlled Intelligence Loop storyboard

## Consequences

Positive:

- Better separation of presentation and Python control logic.
- More reviewable UI changes.
- Faster route to a product-quality dashboard.
- No frontend build-chain overhead.
- Smooth path toward a later React UI if needed.

Trade-offs:

- Jinja2 is less suitable than React for rich client-side interactivity.
- Templates require discipline to avoid hidden business logic.
- ViewModels must be kept clean and explicit.

## Boundary

This decision does not introduce source activation, connector registration, Bronze writes, scheduler changes or approval bypasses.

It only defines the server-rendered UI template architecture.
