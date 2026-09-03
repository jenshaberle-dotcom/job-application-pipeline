# Governance Current Truth

Status: current truth  
Active product track: **PRODUCT-RECOVERY-001 / issue #783**

Governance exists to keep the project truthful, operator-controlled and product-focused. The current failure mode to avoid is no longer only unsafe automation; DEMO-001 also showed that a highly governed subsystem can still fail to deliver reliable end-user value if truth does not propagate across boundaries.

## Current governing principles

- Safety, legal risk, privacy and data integrity override speed.
- Approved product intent overrides historical implementation behavior.
- Discovery evidence, Employer-Origin authority, currentness, ranking and application authority remain distinct.
- Missing required evidence stays unknown/review-required; it is never converted to success to make a demo or quota look better.
- Product-facing progress is measured by the approved end-to-end outcome, not by number of runners, tests, migrations or branches.
- CI proves repository contracts; local database/provider/live-web state requires separate operator evidence.
- Repair/demo helpers may preserve value, but they do not become the desired normal architecture by default.
- Product-visible checkpoints require GitHub Releases with features, bug fixes, known limitations and clearly labeled operator proof.
- Dry-run/apply separation remains required for material mutations where the action is not an explicit bounded product interaction.
- Historical planning and exports never override current truth.

## Product Recovery work-admission rule

While issue #783 is active, new work enters the primary product path only when it does at least one of the following:

1. improves discovery -> Employer-Origin truth propagation;
2. improves current-vacancy freshness/revalidation;
3. reduces manual repair between Product V1 stages;
4. increases evidence-complete rankable/recommendation throughput without lowering approved gates;
5. improves application-document truthfulness/layout/usability;
6. removes/consolidates complexity that obstructs the above;
7. protects the path through E2E product-value proof or release discipline.

Safety/security defects, data-integrity fixes, CI/runtime incidents and mandatory governance maintenance may proceed even when they do not directly move the product metric.

Broad deterministic hardening, ML expansion, post-application feature work and infrastructure expansion remain deprioritized unless they can demonstrate a direct current Product Recovery need.

## Product authority that must not be weakened

### Employer-Origin authority

Aggregator-only evidence is discovery evidence. It cannot become final Top-5 or Application action authority without a current Employer-Origin vacancy or another explicitly approved equivalent path.

### Freshness

Known stale/closed vacancies must not remain current/actionable/recommended. Historical observations remain valid lineage; they do not become live truth.

### Top-5

Current approved product semantics remain:

- at most five recommendations (`PD-050`);
- minimum overall quality 70/100 (`PD-051`);
- no hard-filter failure (`PD-053`);
- missing required evidence blocks authoritative ranking (`PD-054`).

The product must improve enough jobs to meet the threshold. It must not lower the threshold or reinterpret `rankable` as `recommended` merely to produce five rows.

### Application authority

Candidate Facts remain the factual authority for candidate claims. Exact current vacancy evidence remains the job-specific authority.

Provider access for application preparation occurs only through the explicit operator Generate action under the approved application contract. Approved base-document text may be used as structure/style context. Generated documents remain `draft_for_review`.

No provider success, ranking result or generated file authorizes automatic submission, email send or silent application-state mutation.

## Side-effect governance

### Source and connector mutations

Connector candidacy, artifact generation, validation, registration and controlled activation remain separate authorities. Existing standing authorization applies only where explicitly approved by current product/governance contracts.

### Ranking and evidence mutations

- assessment refresh must be bound to the current vacancy snapshot;
- capability/hard-filter review must cite the current evidence version;
- deterministic failures cannot be overwritten by convenience review;
- ranking writes must use the approved policy version;
- recommendation policy changes are product changes and require explicit operator approval, not a demo need.

### Application/provider actions

- explicit user action is required to trigger application provider calls;
- provider calls do not write application-submission state;
- output remains review-only;
- private base documents stay local except for the explicitly approved Generate provider context.

## Release governance

GitHub Releases are the product-facing history.

Canonical surfaces:

- `.github/RELEASE_MANAGEMENT.md`;
- `.github/release.yml`;
- `.github/workflows/release.yml`;
- `.github/release-requests/`;
- `.github/release-promotions/` when a visibility promotion is required.

A release must state:

- visible product changes;
- relevant bug fixes in symptom -> correction -> proof terms;
- known limitations;
- safety/authority boundaries;
- exact repository checkpoint;
- local operator evidence only when clearly labeled non-portable runtime proof.

Tags are immutable product checkpoints. Release promotion may change GitHub visibility but must not move or rewrite the tag.

## CI, E2E and operator acceptance

Three acceptance layers remain mandatory:

1. **Technical correctness** — CI, migrations, tests, build.
2. **Contract conformance** — approved PRD/PD/PA expectations.
3. **Operator acceptance** — visible product outcome is genuinely useful.

DEMO-001 demonstrated why layer 1 alone is insufficient. A green Full Suite is not evidence that the operator can find five current useful jobs or send a high-quality application.

PRODUCT-RECOVERY-001 must add a repeatable product-value proof around the cold-to-application path.

## Workspace and re-entry governance

Canonical `main` and `PROJECT-REENTRY.json` remain re-entry authority. Feature mutation starts from fresh `main` under the declared project worktree root. Branch-of-branch continuation remains forbidden.

Retention debt, DRJ availability or unrelated portfolio state do not by themselves block project work. Dirty/divergent/ambiguous state is preserve-by-default and fails closed only for directly affected work.

## Reference surfaces

- `../reference/product-contract/`
- `../reference/governance/governance_foundation.md`
- `../reference/governance/agent_governance_registry.md`
- `../reference/governance/agent_capability_audit_matrix.md`
- `../reference/governance/documentation_drift_baseline.md`
- `../decisions/adr_status_table.md`
- `.github/RELEASE_MANAGEMENT.md`

Historical MCP/re-entry and deterministic-hardening governance remains useful provenance but does not override PRODUCT-RECOVERY-001 current sequencing.
