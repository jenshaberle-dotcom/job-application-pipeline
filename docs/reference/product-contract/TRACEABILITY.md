# Product Traceability

Status: active product-governance rule  
Active product track: **PRODUCT-RECOVERY-001 / issue #783**

## Objective

Engineering backlog, tests and implementation remain valuable, but they do not act as an implicit product specification.

Every active product-shaping story must explain which approved operator outcome it serves and how it advances the normal cold-to-application product path.

## Required links

Before implementation, a product-shaping story must reference:

- one or more approved `PRD-*` requirements;
- one or more approved `PD-*` decisions where applicable;
- one or more approved `PA-*` acceptance scenarios;
- intended visible operator outcome;
- cold-to-application stage affected;
- side-effect/rollback boundary;
- technical validation layer;
- runtime/operator proof boundary where applicable;
- expected release-note impact when product-visible.

Example:

```json
{
  "story_id": "RECOVERY-M1-ORIGIN-PROJECTION",
  "product_requirements": ["PRD-E2E-001", "PRD-SOURCE-001", "PRD-RECOVERY-001"],
  "product_decisions": ["PD-043", "PD-050", "PD-051"],
  "acceptance_scenarios": ["PA-003-aggregator-without-origin", "PA-006-stale-official-posting"],
  "product_stage": "Employer-Origin/currentness -> Product read model",
  "operator_outcome": "Recommended/application jobs open the current Employer-Origin vacancy, never the discovery aggregator URL.",
  "side_effect_boundary": "read-model/projection only unless separately approved migration is required",
  "runtime_proof": "bounded live Employer-Origin validation",
  "release_note": "Bug fix: prevent aggregator action-link leakage"
}
```

## Product Recovery critical path

While issue #783 is active, primary-path stories should normally map to at least one of these recovery stages:

1. `M0` baseline / complexity inventory;
2. `M1` Employer-Origin + freshness truth propagation;
3. `M2` single normal cold orchestration;
4. `M3` recommendation throughput/quality;
5. `M4` application quality;
6. `M5` complexity harvest + release.

Canonical plan: `docs/planning/active/product_recovery_001.md`.

## Core Product Recovery anchors

The default approved anchors for core recovery work are:

### Discovery/origin/currentness

- `PRD-E2E-001`
- `PRD-SOURCE-001`
- `PD-043`
- `PA-003-aggregator-without-origin`
- `PA-006-stale-official-posting`

### Ranking/recommendation

- `PRD-TOP5-001`
- `PRD-RECOVERY-001`
- `PD-050` through `PD-056`
- `PD-082`
- `PA-001-five-strong-jobs`
- `PA-002-fewer-than-five-qualified`
- `PA-020-hard-filter-failure`
- `PA-021-insufficient-market-results`
- `PA-027-product-recovery-cold-flow`

### Application preparation

- `PRD-APPLICATION-001`
- `PD-071`
- `PD-075`
- `PA-019-provider-only-evidence`
- `PA-025-application-prohibited`
- `PA-026-explicit-application-generation`

## Backlog classification

Every engineering item should be classified as one of:

- `required_for_approved_product`;
- `enabling_technical_work`;
- `quality_security_or_reliability_control`;
- `product_change_proposal`;
- `optional_improvement`;
- `parked_future`;
- `not_required_for_current_product`.

During Product Recovery, also classify the relationship to current complexity:

- `normal_path_capability`;
- `recovery_diagnostic_to_integrate`;
- `recovery_wrapper_to_retire`;
- `retained_independent_track`.

Items without approved product traceability may remain in the catalog, but they do not enter the primary path unless they are necessary safety, defect, operational or release controls.

## Authority boundary

Code/database/merged PRs show implementation. They do not automatically show desired product behavior.

When implementation and approved product intent disagree:

1. preserve data and operational safety;
2. record the mismatch;
3. classify implementation as product drift/technical debt;
4. propose bounded correction;
5. do not rewrite approved product intent merely to match current implementation;
6. do not lower evidence/ranking gates merely to satisfy demo counts.

DEMO-001 provides a concrete example: six locally `rankable` jobs did **not** mean six Top-5 recommendations because only one met the approved 70/100 threshold. The correct recovery action is to improve job/evidence/ranking throughput, not redefine `rankable` as `recommended`.

## PR requirements

A product-shaping PR must state:

```text
Product requirements:
Product decisions:
Acceptance scenarios:
Product Recovery milestone/stage:
Visible operator outcome:
Product semantics changed: yes/no
Operator approval required: yes/no
Local/runtime proof required: yes/no
Complexity disposition: add/integrate/retire/none
Release-note impact: yes/no
```

A technical PR with no product semantic change should explicitly say so.

## Acceptance layers

1. **Technical correctness** — code, migrations, tests/build are correct.
2. **Contract conformance** — approved PRD/PD/PA behavior passes.
3. **Runtime evidence** — when relevant, local DB/live employer/provider behavior is proven separately from CI.
4. **Operator acceptance** — Jens confirms the visible result is genuinely useful.

No lower layer substitutes for a higher one.

For application quality, text extraction or a generated PDF file existing is only technical evidence. Product acceptance requires visual/content review against the approved scenario.

## Release traceability

Product-visible checkpoints are published through GitHub Release Management.

Release notes should trace back to the product change in operator language:

- feature/outcome;
- bug symptom;
- correction;
- proof/boundary preventing recurrence;
- known remaining limitation.

Local operator facts used in release notes must be labeled as non-portable runtime evidence.

Release tags are immutable checkpoints. A visibility promotion may change GitHub's pre-release flag but must not move the tag or rewrite the underlying product history.

## Product Recovery close-out traceability

Before PRODUCT-RECOVERY-001 can close:

- `PA-027-product-recovery-cold-flow` must have automated contract coverage where feasible;
- the real operator acceptance campaign must demonstrate the normal cold-to-application path;
- at least five jobs in the controlled acceptance campaign must satisfy the approved recommendation contract without override;
- application package must pass technical and human visual/content acceptance;
- retained demo/recovery helpers must have explicit integrate/retain/retire disposition;
- current docs/re-entry and the next GitHub Release must agree.

This is progressive product recovery, not a requirement to redesign every future feature before useful work resumes.
