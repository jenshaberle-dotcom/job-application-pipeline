# Job Application Pipeline

Status: active portfolio project
Theme: Deep Ocean / Search Intelligence
Primary scope: Hannover and remote-in-Germany job-market intelligence

## Why this project exists

Finding a few relevant jobs is easy. Finding the right market signals reliably
over time is harder: good employers can be hidden behind noisy aggregators,
missing career-page evidence, strict filters, stale search terms or safe-looking
pipeline stops that create false negatives.

This project builds a personal Search Intelligence system for that problem. It
is not optimized for maximum scraping volume. It is optimized for bounded
acquisition, evidence quality, explainable stops, next safe actions and
controlled source activation.

This is a portfolio project, but the engineering standard is product-grade:
traceable decisions, explicit gates, governance around agent-like helpers,
repeatable tests and documentation that survives more than one implementation
wave.

## Current system in one sentence

```text
Market signals -> candidates -> origin/detail evidence -> gates/stops/repair
-> connector readiness -> controlled sources -> Bronze/Silver/Gold -> Control Center
```

## What this project is not

It is not a scraper demo, not a pile of one-off job-search scripts, and not a
CSV/Excel-driven pipeline. Aggregators are treated as discovery inputs, not as
uncontrolled source truth.

## Deep Ocean design language

Deep Ocean is a practical product metaphor:

- **Sonar** for market sensing and signal discovery.
- **Depth** for evidence quality and confidence.
- **Control surfaces** for gates, stops, approvals and next safe actions.
- **Repair loops** for false-negative-aware learning instead of blind retries.

## Core principles

- Defensive acquisition beats aggressive crawling.
- Raw discovery may be broad; promotion and activation must be strict.
- Evidence comes before connector build.
- Dry-run comes before apply.
- No commits on `main`.
- Exports are reports, not source-of-truth handoffs or pipeline inputs.
- Agent-like behavior needs governance, capability boundaries and auditability.

## Documentation

Start with `docs/README.md`.

The documentation is organized as:

```text
docs/
├── README.md
├── current/
├── guides/
├── reference/
├── decisions/
├── planning/
└── archive/
```

Primary entry points:

1. `docs/current/product.md`
2. `docs/current/architecture.md`
3. `docs/current/pipeline.md`
4. `docs/current/system-diagrams.md`
5. `docs/current/governance.md`
6. `docs/current/operations.md`
7. `docs/guides/development-workflow.md`

## Repository map

| Path | Purpose |
|---|---|
| `src/` | Production code and shared modules. |
| `scripts/` | CLI agents, checks and operator commands. |
| `tests/` | Regression and contract tests. |
| `db/` | Database migrations and schema assets. |
| `docs/current/` | Current product, architecture, pipeline, governance and operations truth. |
| `docs/guides/` | Practical how-to documentation. |
| `docs/reference/` | Detailed lookup material. |
| `docs/decisions/` | ADRs and ADR status control. |
| `docs/archive/planning/` | Active planning only. |
| `docs/archive/` | Historical documentation and replaced artifacts. |
| `exports/` | Generated reports and handover artifacts; not pipeline input. |

## Architecture contract anchors

Some repository tests intentionally assert that the README still points to the
active architecture and governance baselines.

Current anchors:

- `ARCH-001-SAFETY-SECURITY-STATE`
- `docs/reference/governance/governance_foundation.md`
- `docs/reference/governance/documentation_drift_baseline.md`
- `docs/archive/planning/eo002b_candidate_reprocessing_url_finder_validation.md`
