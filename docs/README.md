# Documentation

Status: current documentation entry point  
Active product track: **PRODUCT-RECOVERY-001 / issue #783**

## Purpose

The documentation separates:

- approved product intent;
- current implementation/product truth;
- practical operator/development guidance;
- detailed reference contracts;
- active planning;
- historical evidence.

The goal is that a new re-entry can understand the product and current gaps **without reconstructing months of commit/branch/chat history**.

## Read this first

1. `current/README.md` — current sequencing/re-entry truth.
2. `reference/product-contract/README.md` — product authority.
3. `current/product.md` — current product checkpoint, recovery objective and known gaps.
4. `current/architecture.md` — architecture and authority boundaries.
5. `current/pipeline.md` — acquisition + concrete-job Product V1 state machines.
6. `current/system-diagrams.md` — current visual architecture.
7. `current/governance.md` — operational/product governance.
8. `current/operations.md` — workspace, runtime, proof and release operations.
9. `planning/active/product_recovery_001.md` — active recovery plan.

## Current project story

The project is no longer accurately described as only an employer/source discovery and connector system.

The current product spans:

```text
Market discovery
-> Employer-Origin resolution
-> current vacancy verification
-> Bronze / Silver
-> Product V1 assessment / hard filters / ranking
-> React Control Center
-> Application Workspace
-> CV / letter DOCX/PDF/ZIP draft_for_review
-> GitHub Release checkpoint
```

DEMO-001 proved that these components can work together, but also exposed integration debt: stale/currentness leakage, discovery-vs-origin projection problems, low normal rankable throughput, provider integration defects and document-quality gaps.

PRODUCT-RECOVERY-001 makes the repeatable cold-to-application path the primary product truth.

## Product authority

`reference/product-contract/` defines approved and open product behavior.

The Pipeline is **Class A — Intent Locked**:

- operator-approved requirements/decisions/scenarios define desired behavior;
- code/tests/database state define implementation/runtime truth;
- implementation must not silently redefine product behavior;
- a demo requirement does not authorize weakening approved evidence/ranking gates.

Important current product constraints include:

- Employer-Origin confirmation for authoritative recommendation/application action;
- Top 5 is at most five;
- current minimum recommendation score is 70/100;
- missing required evidence blocks authoritative ranking;
- no automatic application submission;
- generated application artifacts remain review drafts.

## Current truth vs operator evidence

`current/` documents durable repository/product truth.

Local runtime evidence — PostgreSQL contents, live vacancy HTTP results, private candidate documents and provider output — must be labeled as **operator validation**, not represented as portable repository state.

DEMO-001 local operator evidence is retained in release notes/checkpoint artifacts, but it must be revalidated when current job/runtime truth matters.

## Release history

GitHub Releases are now the product-facing change history.

Canonical release surfaces:

- `.github/RELEASE_MANAGEMENT.md`;
- `.github/release.yml`;
- `.github/workflows/release.yml`;
- `.github/release-notes/`;
- `.github/release-requests/`;
- `.github/release-promotions/`.

Commit history remains engineering detail. Release notes should explain user/operator-visible features, bug fixes, known limitations and relevant proof.

Current first checkpoint: `v0.1.0-demo.1`.

## Structure

| Area | Purpose | Rule |
|---|---|---|
| `current/` | Maintained current product/architecture/pipeline/governance/operations truth. | Keep coherent and current; update when sequencing or authority changes. |
| `guides/` | Practical how-to documentation. | Commands/workflows, not competing architecture truth. |
| `reference/` | Detailed stable contracts and lookup material. | Precise detail is welcome; current-story duplication is not. |
| `decisions/` | ADRs and decision status. | Explain why; check status before treating as current. |
| `planning/active/` | Active product/engineering sequencing. | Current track first; retained tracks clearly marked paused/preserved. |
| `archive/` | Historical/superseded traces. | Evidence only, never current authority. |

## Artifact rules

- Update an existing current artifact before creating another competing summary.
- Product-contract changes must update decision/scenario/traceability surfaces when semantics change.
- Current docs must distinguish repository truth from local runtime proof.
- Planning docs must state what is active, retained and superseded.
- Demo/recovery helper scripts may be documented as retained operational tools without being promoted into steady-state architecture.
- Releases document product checkpoints; they do not replace current docs or product authority.
- Exports remain outputs, not hidden pipeline inputs.

## Docs-as-code guards

- `scripts/check_documentation_architecture.py`
- `scripts/check_documentation_references.py`
- `scripts/check_adr_rebaseline.py`

## Key reference surfaces

- `reference/product-contract/PRD.md`
- `reference/product-contract/PRODUCT_DECISION_REGISTER.md`
- `reference/product-contract/ACCEPTANCE_SCENARIOS.md`
- `reference/product-contract/TRACEABILITY.md`
- `reference/database/schema_overview.md`
- `reference/database/schema_relationships.md`
- `reference/governance/governance_foundation.md`
- `reference/security/search_intelligence_security_baseline.md`
- `reference/search-intelligence/llm_booster_cascade.md`
- `reference/search-intelligence/ml_learning_layer.md`
- `decisions/adr_status_table.md`

## ADRs

ADRs live in `decisions/adr/`. Use `decisions/adr_status_table.md` before treating an ADR as current implementation authority.

## Exports

`exports/` contains generated runtime reports/review artifacts. Exports are reports, not re-entry authority and not pipeline inputs.
