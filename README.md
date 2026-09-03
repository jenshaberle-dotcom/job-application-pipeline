# Job Application Pipeline

Status: active portfolio product  
Project character: **A — Intent Locked**  
Theme: Deep Ocean / Search Intelligence  
Primary scope: Hannover and remote-in-Germany job-market intelligence  
Active product track: **PRODUCT-RECOVERY-001 / issue #783**  
Current release checkpoint: **`v0.1.0-demo.1`**

## Why this project exists

A normal job search can find postings. The harder problem is reliably turning a noisy market into a small set of **current, relevant, employer-origin-verified opportunities** without being misled by stale aggregators, ambiguous source URLs or incomplete evidence — and then preparing a truthful application with minimal manual effort.

The project therefore combines Search Intelligence, data engineering, evidence-aware ranking and application preparation.

## Current product objective

```text
Discover
-> resolve Employer Origin
-> prove the exact vacancy is current
-> Bronze / Silver
-> assess capability + hard filters
-> deterministic ranking
-> recommend up to five jobs that meet the approved quality threshold
-> Application Workspace
-> CV + letter DOCX/PDF/ZIP draft_for_review
```

The immediate objective is **not** more subsystem hardening for its own sake. PRODUCT-RECOVERY-001 exists to make this end-to-end path repeatable from a normal cold run.

## Product authority

Jens owns desired product behavior. Engineering may adapt technical implementation but may not silently redefine target profile, evidence, freshness, ranking, Top-5, application or automation semantics.

Start with `docs/reference/product-contract/README.md` and `docs/current/README.md`.

Important current approved rules include:

- aggregators such as BA/StepStone are discovery evidence, not final Top-5/Application authority;
- Top 5 means **at most five**, never quota-filled with weaker jobs;
- current minimum recommendation quality is **70/100**;
- hard-filter failures or unresolved required evidence do not enter authoritative ranking/Top-5;
- no automatic application submission;
- application generation remains operator-triggered and `draft_for_review`.

## Current checkpoint and maturity

DEMO-001 was salvaged to `main` and published as `v0.1.0-demo.1`.

It proves that the repository contains a real vertical slice covering:

- discovery and Employer-Origin evidence;
- Bronze/Silver/Gold data layers;
- Product V1 assessment, capability fit, hard filters and ranking;
- React Control Center;
- live vacancy/detail-drift handling;
- provider-backed application drafting with evidence-first fallback;
- CV/letter DOCX/PDF/ZIP export;
- GitHub Release Management and release notes.

It also exposed material integration debt. The product is **not production-ready** and a cold discovery-to-application run is not yet reliable enough without repair/operator intervention.

## Product Recovery metric

The primary product metric is:

> **Five current Employer-Origin jobs that pass the approved product gates and recommendation threshold, produced through one normal observable flow, plus a review-ready application package requiring only small human edits.**

The target must be reached by improving currentness, truth propagation, assessment/ranking throughput and document quality — not by weakening evidence or recommendation gates.

## System areas

| Area | Role |
|---|---|
| Market sensors / aggregators | Broad bounded discovery and recall. |
| Employer-Origin resolution | Converts discovery evidence into employer-controlled vacancy authority. |
| Bronze | Raw observations and lineage. |
| Silver | Canonical normalized jobs. |
| Gold / Product V1 | Assessment, ranking and operator read models. |
| Control Center | Evidence, source health, jobs, metrics, ranking and application workflow. |
| Application Workspace | Candidate Facts + exact vacancy + approved base documents -> review draft package. |
| Release Management | Product-facing version/change history with features, bug fixes and known limitations. |

## Working principles

- Exact on product WHAT; adaptive on technical HOW.
- Discovery is broad; Product authority is strict.
- Employer-Origin and currentness before recommendation.
- Evidence before ranking and application claims.
- Dry-run/apply separation for bounded mutations where applicable.
- No commits directly on `main`.
- Feature worktrees live under the declared project worktree root, not `/tmp`.
- Reports/exports are outputs, not hidden pipeline inputs.
- CI does not prove local PostgreSQL/provider/live-web truth.
- A green technical suite does not substitute for operator product acceptance.
- Release notes are the product-facing history; commits remain engineering detail.

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
9. `docs/planning/active/product_recovery_001.md`

## Repository map

| Path | Purpose |
|---|---|
| `src/` | Production code and shared modules. |
| `scripts/` | CLI operators, checks, diagnostics and recovery helpers. |
| `frontend/control-center/` | React Product V1 Control Center. |
| `tests/` | Regression and contract tests. |
| `db/` | Database migrations and schema assets. |
| `docs/current/` | Maintained product/architecture/pipeline/governance/operations truth. |
| `docs/guides/` | Practical development/operator/testing guides. |
| `docs/reference/` | Detailed product, database, governance, security and source contracts. |
| `docs/decisions/` | ADRs and decision status. |
| `docs/planning/active/` | Current sequencing and active product recovery. |
| `docs/archive/` | Historical and superseded artifacts. |
| `.github/release-*` | Release notes/requests/promotion records and release governance. |
| `exports/` | Generated reports; not pipeline input. |

## Release history

GitHub Releases are the product-facing history. Release notes should describe visible features, bug fixes, known limitations and relevant operator proof.

Current checkpoint:

- `v0.1.0-demo.1` — DEMO-001 salvaged product path.

See `.github/RELEASE_MANAGEMENT.md` for the canonical release process.

## Deep Ocean language

Deep Ocean remains the product metaphor: sonar for sensing, depth for evidence, pressure for gates, calm control surfaces for decisions and visible repair loops for learning.

## Architecture contract anchors

- `ARCH-001-SAFETY-SECURITY-STATE`
- `docs/reference/governance/governance_foundation.md`
- `docs/reference/governance/documentation_drift_baseline.md`
- `docs/current/architecture.md`
- `docs/current/system-diagrams.md`
