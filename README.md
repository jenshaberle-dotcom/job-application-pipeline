# Job Application Pipeline

Status: active portfolio product
Project character: **A — Intent Locked**
Theme: Deep Ocean / Search Intelligence
Primary scope: Hannover and remote-in-Germany job-market intelligence
Active product track: **PRODUCT-RECOVERY-001 / issue #783**
Current release checkpoint: **`v0.1.0-demo.1`**

## Why this project exists
A normal job search can find postings. The harder problem is noticing what the search keeps missing: relevant employers hidden behind noisy aggregators, stale vacancies, incomplete evidence, strict gates or safe-looking stops that quietly become **false negatives**.

This is a portfolio project, but its desired behavior is governed like a personal product. The system combines Search Intelligence, data engineering, evidence-aware ranking and review-only application preparation.

## Product authority
Jens owns desired product behavior. Engineering may adapt technical implementation but may not silently redefine target profile, evidence, freshness, ranking, Top-5, application or automation semantics.

Start with `docs/reference/product-contract/README.md` and `docs/current/README.md`.

## Current product objective
```text
market discovery -> Employer-Origin resolution -> current exact vacancy
-> Bronze / Silver -> assessment -> capability fit -> hard filters
-> deterministic ranking -> recommendations meeting the approved contract
-> Application Workspace -> CV/letter DOCX/PDF/ZIP draft_for_review
```

PRODUCT-RECOVERY-001 exists to make this path repeatable from a normal cold run. The controlled acceptance target is at least five current Employer-Origin recommendations that satisfy all approved gates and the current >=70/100 recommendation threshold, plus an application package requiring only small human edits. `rankable` is not synonymous with `recommended`, and Top 5 is at most five.

DEMO-001 is the salvaged checkpoint published as `v0.1.0-demo.1`; it proves the vertical slice exists but does not claim production readiness.

## Working principles
- Exact on product WHAT; adaptive on technical HOW.
- Discovery is broad; Product authority is strict.
- Employer-Origin and currentness before recommendation.
- Evidence before ranking and application claims.
- Dry-run before apply.
- No commits on `main`.
- Feature worktrees live under the declared project worktree root, not `/tmp`.
- Reports and exports are outputs, not source-of-truth inputs.
- CI does not prove local PostgreSQL/provider/live-web truth.
- A green technical suite does not substitute for operator product acceptance.
- No automatic application submission or send.

## Documentation
Start with `docs/README.md`.

Primary entry points:
1. `docs/current/README.md`
2. `docs/reference/product-contract/README.md`
3. `docs/current/product.md`
4. `docs/current/architecture.md`
5. `docs/current/pipeline.md`
6. `docs/current/system-diagrams.md`
7. `docs/current/governance.md`
8. `docs/current/operations.md`
9. `docs/guides/development-workflow.md`
10. `docs/planning/active/product_recovery_001.md`

## Repository map
| Path | Purpose |
|---|---|
| `src/` | Production code and shared modules. |
| `scripts/` | CLI operators, checks, diagnostics and recovery helpers. |
| `frontend/control-center/` | React Product V1 Control Center. |
| `tests/` | Regression and contract tests. |
| `db/` | Database migrations and schema assets. |
| `docs/current/` | Maintained current product/architecture/pipeline/governance/operations truth. |
| `docs/guides/` | Practical development/operator/testing guidance. |
| `docs/reference/` | Detailed product, database, governance, security and source contracts. |
| `docs/decisions/` | ADRs and decision status. |
| `docs/planning/` | Active planning only. |
| `docs/archive/` | Historical documentation and replaced artifacts. |
| `exports/` | Generated reports; not pipeline input. |

## Release history
GitHub Releases are the product-facing checkpoint history; commit history remains engineering detail. See `.github/RELEASE_MANAGEMENT.md`.

## Deep Ocean language
Deep Ocean is the product metaphor: sonar for sensing, depth for evidence, pressure for gates, calm control surfaces for decisions and visible repair loops for learning.

## Architecture contract anchors
- `ARCH-001-SAFETY-SECURITY-STATE`
- `docs/reference/governance/governance_foundation.md`
- `docs/reference/governance/documentation_drift_baseline.md`
- `docs/archive/planning/eo002b_candidate_reprocessing_url_finder_validation.md`
