# Job Application Pipeline

Status: active portfolio project
Project character: **A — Intent Locked**
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

This is a portfolio project, but its desired behavior is governed like a personal product.

## Product authority
Jens owns desired product behavior. DON may adapt technical implementation but
may not redefine target profile, geography, Top-5, ranking, review or automation
semantics. Start with `docs/reference/product-contract/README.md`.

## System in one sentence
```text
Market signals -> candidates -> origin/detail evidence -> gates/stops/repair
-> connector readiness -> controlled sources -> Bronze/Silver/Gold -> Control Center
```

## Working principles
- Exact on product WHAT; adaptive on technical HOW.
- Defensive acquisition over aggressive crawling.
- Broad raw discovery, strict promotion and activation.
- Evidence before connector build.
- Dry-run before apply.
- No commits on `main`.
- Reports and exports are outputs, not source-of-truth inputs.
- Agent-like behavior needs clear boundaries and auditability.
- Open product decisions remain open.

## Documentation
Start with `docs/README.md`.

Primary entry points:
1. `docs/reference/product-contract/README.md`
2. `docs/current/product.md`
3. `docs/current/architecture.md`
4. `docs/current/pipeline.md`
5. `docs/current/system-diagrams.md`
6. `docs/current/governance.md`
7. `docs/current/operations.md`
8. `docs/guides/development-workflow.md`

## Repository map
| Path | Purpose |
|---|---|
| `src/` | Production code and shared modules. |
| `scripts/` | CLI agents, checks and operator commands. |
| `tests/` | Regression and contract tests. |
| `db/` | Database migrations and schema assets. |
| `docs/current/` | Small current product, architecture, pipeline, governance and operations truth. |
| `docs/guides/` | Practical how-to documentation. |
| `docs/reference/` | Detailed product, database, governance, security and source contracts. |
| `docs/decisions/` | ADRs and ADR status control. |
| `docs/planning/` | Active planning only. |
| `docs/archive/` | Historical documentation and replaced artifacts. |
| `exports/` | Generated review reports; not pipeline input. |

## Deep Ocean language
Deep Ocean is the product metaphor: sonar for sensing, depth for evidence,
pressure for gates, calm control surfaces for decisions and repair loops for
learning.

## Architecture contract anchors
Some tests intentionally assert that the README still points to active
architecture and governance baselines.

- `ARCH-001-SAFETY-SECURITY-STATE`
- `docs/reference/governance/governance_foundation.md`
- `docs/reference/governance/documentation_drift_baseline.md`
- `docs/archive/planning/eo002b_candidate_reprocessing_url_finder_validation.md`
