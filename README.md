# Job Application Pipeline

Status: active portfolio project
Theme: Deep Ocean / Search Intelligence
Primary scope: Hannover and remote-in-Germany job-market intelligence

## Why this project exists

A normal job search can find a few interesting postings. The harder problem is
noticing what the search keeps missing: relevant employers hidden behind noisy
aggregators, weak search terms, missing career-page evidence, strict gates or
safe-looking stops that quietly become false negatives.

This repository builds a personal Search Intelligence system around that
problem. It is not a scraper demo and not a volume game. The value is in bounded
acquisition, evidence, explainable stops, repair paths and controlled source
activation.

This is a portfolio project, but the engineering bar is deliberately
product-like: traceable decisions, tests, explicit gates, agent governance and
clean documentation instead of clever one-off scripts.

## System in one sentence

```text
Market signals -> candidates -> origin/detail evidence -> gates/stops/repair
-> connector readiness -> controlled sources -> Bronze/Silver/Gold -> Control Center
```

## Deep Ocean language

Deep Ocean is the product metaphor, not decoration:

- sonar for market sensing,
- depth for evidence quality,
- pressure for gates and risk,
- control surfaces for approvals and next safe actions,
- repair loops for learning without blind retries.

## Working principles

- Defensive acquisition over aggressive crawling.
- Broad raw discovery, strict promotion and activation.
- Evidence before connector build.
- Dry-run before apply.
- No commits on `main`.
- Reports and exports are outputs, not source-of-truth inputs.
- Agent-like behavior needs clear boundaries and auditability.

## Documentation

Start with `docs/README.md`. The documentation is intentionally organized into a
small active surface:

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
| `docs/current/` | Small current product, architecture, pipeline, governance and operations truth. |
| `docs/guides/` | Practical how-to documentation. |
| `docs/reference/` | Detailed lookup material. |
| `docs/decisions/` | ADRs and ADR status control. |
| `docs/planning/` | Active planning only. |
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
