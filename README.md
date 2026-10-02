# JAP Classic — Job Application Pipeline

Status: maintained local product and migration source for JAP Cloud.
Project character: **A — Intent Locked**. Theme: **Deep Ocean / Search Intelligence**.

## Why this project exists

This is a portfolio project and a personal job-search product. It addresses false negatives:
relevant vacancies lost behind aggregators, missing employer evidence or overly strict stops.
It turns verified Employer-Origin jobs into explainable Candidate Fit, Affinity, Top 5,
application preparation and tracking. Jens owns product intent.

## Current implementation

| Area | Repository implementation |
|---|---|
| UI | React/TypeScript Control Center in `frontend/control-center/`. |
| Local service | Python product service and HTTP API in `scripts/` and `src/search_intelligence/`. |
| Persistence | PostgreSQL; ordered migrations in `db/migrations/`. |
| Windows app | .NET 8/WebView2 shell; Python/private environment through WSL. |
| Updates | Immutable desktop/runtime assets; staged verification, consent, transactional cutover. |
| CI and packaging | RCC General Pool; JAP declares demand and verifies exact assignment. |
| Cloud direction | Cloud parity and verified migration, then one normal Cloud product path. |

`windows/JAP.ControlCenter.Desktop/VERSION` defines the desktop product version.
The root `VERSION` and frontend package version identify other components; they are not
interchangeable release authorities. A version file never proves an installed runtime.

## Start here

- [Documentation](docs/README.md)
- [Product and boundaries](docs/current/product.md)
- [Architecture](docs/current/architecture.md)
- [Windows install and updates](docs/guides/jap_control_center_windows_app.md)
- [Operation and recovery](docs/guides/operator-runbook.md)
- [Development workflow](docs/guides/development-workflow.md)
- [Current engineering evidence](docs/current/REENTRY.md)

## Repository map

| Path | Purpose |
|---|---|
| `src/` | Product, acquisition and domain code. |
| `scripts/` | Local API, CLI commands, diagnostics and validation. |
| `frontend/control-center/` | React UI and build. |
| `windows/` | Native desktop host and updater. |
| `db/` | Ordered PostgreSQL migrations. |
| `tests/` | Product, runtime, safety and contract regression checks. |
| `.rcc/` | Consumer demand and dependency declaration; RCC owns runners. |
| `docs/current/` | Current product and architecture facts. |
| `docs/guides/` | Practical operation and engineering instructions. |
| `docs/reference/` | Product contracts and technical lookup. |
| `docs/decisions/` | Decisions and their current/superseded status. |
| `docs/planning/` | Active planning only. |
| `docs/archive/` | Historical documentation and replaced artifacts. |
| `exports/` | Generated review output; never hidden pipeline authority. |

## Working boundaries

**ARCH-001-SAFETY-SECURITY-STATE**: evidence before effects, explicit transitions,
dry-run before apply, private facts protected, no automatic application submission.
Candidate Fit and Affinity retain separate authority. A test pass or published package
is not live acquisition, Top-5 or fleet proof.

- No commits on `main`.
- Reports and exports are outputs, not source-of-truth inputs.
- Dry-run before apply.

- [Governance foundation](docs/reference/governance/governance_foundation.md)
- [Documentation evidence rules](docs/reference/governance/documentation_drift_baseline.md)
