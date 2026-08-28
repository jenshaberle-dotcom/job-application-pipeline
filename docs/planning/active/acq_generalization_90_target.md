# ACQ-GENERALIZATION-90 — deterministic full-population coverage target

Status: active
Date: 2026-08-28
Owner issue: #676
Active re-entry: `docs/planning/active/acq_generalization_90_reentry.md`

## Primary metric

The primary deterministic acquisition metric is no longer the historical 40-case
survivor cohort in isolation. It is strict functioning deterministic acquisition
coverage across the complete current distinct Employer-Origin candidate population.

At the 2026-08-28 market refresh:

- distinct current candidates: `N = 65`;
- connector-present cohort: `40/65`;
- strict functioning deterministic acquisition: `36/65 = 55.4%`;
- fresh out-of-sample candidates created from the market refresh: `10`;
- fresh candidates with a strict functioning deterministic connector at issue open: `0/10`.

Target:

`strict_functioning_candidates / all_current_distinct_candidates >= 0.90`

For `N = 65`, the minimum passing numerator is `59` (`59/65 = 90.8%`).
`58/65 = 89.2%` is not sufficient.

The denominator is dynamic. New valid Employer-Origin candidates increase `N`; the
target must not be met by suppressing, deleting, excluding, or reclassifying valid
candidates merely to reduce the denominator.

## What counts as success

A candidate counts in the numerator only when the deterministic stack can produce
unchanged strict genuine-job acquisition proof under the repository's existing
authority and side-effect boundaries. Merely having a generated connector, a
reachable career page, a plausible origin URL, provider recognition, diagnostic
recipe readiness, or candidate evidence does not count.

The historical `36/40` remains a regression cohort and must not regress, but it is no
longer the primary coverage claim.

Canonical product coverage remains `36/65` until materialized strict E2E evidence
proves a higher numerator. Current Workday/portal diagnostic work does not change
that number by itself.

## Root-cause phase — completed

The required fresh-10 root-cause matrix was completed before implementation work.
The 0/10 out-of-sample result was shown to cluster into reusable technical classes
rather than ten independent connector gaps.

Dimensions covered:

1. employer-identity correctness at ingest;
2. deterministic origin candidate generation and request-budget ordering;
3. corporate alias / parent-brand / acronym / compact-domain handling;
4. first-party career-page -> job-portal delegation discovery;
5. already-supported ATS recognition/delegation that failed to receive authority;
6. server-rendered listing/detail extraction already covered by generic V4 classes;
7. client-rendered/API-backed listing classes not covered by the narrow historical
   Webpack/Next.js client-code delegation class;
8. cases with no current vacancy versus genuine acquisition capability gaps.

Implementation priority remains expected reusable lift across the full current
population, not closure of one named employer.

## Qualified deterministic progress

### Balanced Origin V2

The old bounded origin planner over-spent its request budget on path variants within
one host family. The balanced planner now preserves host-family breadth and promotes
strong short-brand/acronym evidence without weakening HTTPS, aggregator, identity,
probe or selection authority.

Observed result:

- Origin first-failures: `18 -> 8`;
- prior Origin failures advanced: `10/18`;
- earlier-stage regressions: `0`.

### Inventory/provider composition V3

The builder previously discarded already-authorized provider inventory routes
between its provider and inventory layers. V3 composes only routes emitted by
existing authorized provider adapters.

Observed result:

- diagnostic READY: `21/65 -> 21/65`;
- Inventory first-failures: `17 -> 16`;
- Detail first-failures: `15 -> 16`;
- earlier-stage regressions: `0`;
- `x1F`: `inventory -> detail` through existing Personio provider inventory.

These are diagnostic builder results, not product-coverage promotion.

### Workday CXS proof/acquisition V4

The pre-migration Clarios live trace proved:

`Employer Origin -> Workday Authority -> Board -> CXS Inventory -> concrete public detail`

The first failing boundary was unchanged strict proof on the public SPA detail body.
Post-migration diagnosis established a generic same-host CXS detail carrier without
weakening `genuine_job_detail_proof`.

Current production-shaped deterministic composition:

`authorized employer/Workday root -> exact CXS inventory POST -> same-board externalPath -> exact same-host CXS detail GET -> unchanged genuine_job_detail_proof`

Qualified Workday checkpoint:

- `ae8b272f23f148df786e776b4b6caa57002a4da0`;
- Pipeline CI `#875`: success;
- Re-entry `#1420`: success.

The complete Workday/V4 delivery is merged on canonical
`main@6af34cb54a9bbf29ffc257d1109f495d08d1678d` through PR #682. V4 may promote only
an existing Inventory first-failure after the strict Workday path succeeds. No live
65-candidate V4 numerical lift is claimed until the canonical runtime/database
replay is executed.

### Evidence-bounded portal delegation

The next residual class is first-party career-page -> explicit external/subdomain
job portal handoff. This is intentionally not solved by globally widening listing
vocabulary.

The merged generic bridge requires:

- an explicit strong portal CTA (for example `Job finden` / `Zum Jobportal`); and
- destination binding by same registered employer domain or an explicit
  career/jobs host label;
- exactly one qualifying portal route; ambiguity fails closed.

The downstream route is handed to the existing V4 acquisition stack under the
existing request/proof authority. The class is generic; Bahlsen is one observed
instance, not a named-employer rule.

This bridge is also merged on `main@6af34cb54a9bbf29ffc257d1109f495d08d1678d`.

## Guardrails

- no company-specific success branches;
- no guessed tenant/opaque IDs/routes;
- no proof or employer-authority weakening;
- no provider/LLM/Tavily requirement for the deterministic target;
- no diagnostic DB/source/Bronze/Silver/Product writes;
- historical 40-case cohort remains a regression control;
- fresh market additions remain an out-of-sample generalization control;
- optional builder layers remain evidence-driven and may be skipped when not
  required;
- no product coverage claim from diagnostic recipe readiness alone.

## Workspace migration — fully merged 2026-08-28

The migration pause and delivery phase are closed.

Qualified #676 content was harvested from superseded PR #678 into current-main
lineage without importing old branch ancestry, then delivered through PR #682.

Final delivery identity:

- issue: `#676` remains active;
- PR `#678`: closed/superseded, never merged;
- ancestry-free harvest commit: `6850f4f96186e189165ca8f588752c443847e6ad`;
- delivery PR `#682`: merged;
- canonical delivery merge: `6af34cb54a9bbf29ffc257d1109f495d08d1678d`;
- final pre-merge Pipeline CI `#883`: success;
- final pre-merge Re-entry `#1436`: success.

The historical migration checkpoint remains retained provenance, not the active
resume authority:

- `docs/planning/active/acq_generalization_90_migration_checkpoint_20260828.md`;
- `docs/planning/active/acq_generalization_90_migration_checkpoint_20260828.json`.

The active continuation/retention authority is:

- `docs/planning/active/acq_generalization_90_reentry.md`;
- `docs/planning/active/acq_generalization_90_reentry.json`.

Do not resume from PR #678, PR #682's merged branch, or the migration-pause sole-next
action. Every new mutating slice must start from freshly observed current
`origin/main` in a declared worktree/feature branch.

## Current sequence

1. Run the same 65-candidate V4 builder replay from the canonical WSL
   runtime/database and record Workday promotion(s) without changing the product
   numerator.
2. Compose the merged evidence-bounded portal delegation class as a monotonic
   overlay on residual Inventory failures; replay the same cohort.
3. Re-cluster first failures after each measured generic lift.
4. Continue deterministic hardening until no evidence-backed bounded generic class
   remains.
5. Only then move exhausted residuals to the booster path.
6. Materialize stable connector recipes and update the canonical numerator only
   from unchanged strict E2E proof.
