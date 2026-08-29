# ACQ-GENERALIZATION-90 — canonical re-entry

Status: **ACTIVE — BUILDER V5 MERGED; LIVE COHORT REPLAY NEXT**  
Owner issue: `#676`  
Migration delivery merge: `6af34cb54a9bbf29ffc257d1109f495d08d1678d`  
Latest qualified builder merge: `45f99c1919e6869451b6301bf41a6d3d12ba7c78`

Machine-readable companion: `docs/planning/active/acq_generalization_90_reentry.json`.

## Authority

This file is the active ACQ-676 continuation anchor. It is subordinate to
`PROJECT-HYGIENE.json`, `PROJECT-LOCAL-WORKSPACE.json`, `PROJECT-DRJ.json`, and the
product/current-truth surfaces.

Repository truth, live bounded evidence, tests and CI override chat summaries.
Every new mutating ACQ-676 slice must start from freshly observed current
`origin/main` in a declared worktree/feature branch. Historical #676 branches are
never continuation authority.

## Migration closure proof

The 2026-08-28 canonical workspace migration is fully delivered to `main`.

Qualified old #676 content from superseded PR `#678` was harvested without importing
old branch ancestry:

- old source head: `14e60cd24cfdcc37a41ef9171e6ce269553c69ed`;
- ancestry-free harvest commit: `6850f4f96186e189165ca8f588752c443847e6ad`;
- harvest parent: `main@7644f587d3bd3eb51310451608b7ceb5255ef859`;
- harvested diff: exactly 23 qualified files (`22 added`, `1 modified`);
- old PR `#678`: closed, superseded, never merged;
- delivery PR `#682`: merged;
- delivery merge: `6af34cb54a9bbf29ffc257d1109f495d08d1678d`;
- final #682 Pipeline CI `#883`: success;
- final #682 Re-entry `#1436`: success;
- unresolved review threads: `0`.

The original migration checkpoint remains immutable historical provenance:

- `acq_generalization_90_migration_checkpoint_20260828.md`;
- `acq_generalization_90_migration_checkpoint_20260828.json`.

Those files are not disposable migration debris. They preserve exact historical
cohorts, metric baselines and the pre-migration Clarios trace required for later A/B
interpretation.

## Canonical metric remains unchanged

Current product numerator:

`36 / 65 = 55.4%`

Target at current denominator:

`>= 59 / 65 = 90.8%`

Builder `recipe_ready` is diagnostic only. No V4/V5 promotion changes product
coverage until a materialized connector passes unchanged strict E2E acquisition
proof.

## Qualified engineering frontier

### Completed before migration

Do not repeat unless repository/network truth materially changed:

- fresh-10 root-cause analysis;
- balanced Origin V2 breadth-first planner;
- Origin first-failures `18 -> 8`, earlier-stage regressions `0`;
- inventory surface and bridge audits;
- V3 provider-inventory composition;
- V3 Inventory first-failures `17 -> 16`;
- exact V3 65-candidate first-failure cohorts;
- historical Workday route recovery;
- live Clarios chain through employer authority -> Workday board -> CXS inventory -> concrete public detail.

### Workday CXS proof/acquisition — merged and qualified

The public Workday SPA was identified as the strict-proof surface gap; the canonical
`genuine_job_detail_proof` was not weakened.

Generic composition:

`authorized employer/Workday root -> exact CXS inventory POST -> same-board externalPath -> exact same-host CXS detail GET -> unchanged genuine_job_detail_proof`

Properties:

- no tenant/site/job identity guessing;
- no company-specific success branch;
- public SPA job URL remains canonical output URL;
- raw `jobPostingInfo` wrapper metadata is excluded from proof projection;
- successful delegated route uses three injected requests;
- no provider/LLM/Tavily requirement;
- no DB/source/Bronze/Silver/Product writes;
- no connector materialization.

V4 may promote only an existing `inventory` first-failure after strict Workday proof.

Earlier qualified Workday checkpoint:

- code head `ae8b272f23f148df786e776b4b6caa57002a4da0`;
- Pipeline CI `#875`: success;
- Re-entry `#1420`: success.

### Evidence-bounded portal delegation — merged

The first-party -> portal residual is solved without globally widening
`LISTING_TEXT_MARKERS`.

The generic bridge requires one explicit strong portal CTA plus destination binding
by same registered employer domain or an explicit career/jobs host label. Multiple
qualifying portal URLs fail closed. Bahlsen is an observed instance, not a named
success rule.

Merged implementation:

- `src/connectors/employer_origin_portal_delegation.py`;
- `src/connectors/employer_origin_portal_delegation_acquisition.py`;
- `tests/test_employer_origin_portal_delegation.py`.

### Builder V5 — shared monotonic residual composition merged

PR `#685` merged the next architecture step on commit:

`45f99c1919e6869451b6301bf41a6d3d12ba7c78`

Exact-head gates before merge:

- Pipeline CI `#887`: success;
- Re-entry `#1454`: success.

The builder now owns a shared `rewrite_residual_suffix()` invariant. Every residual
adapter must declare:

1. the exact current `expected_first_failure` it is allowed to handle;
2. the earliest `rewrite_from_layer` whose evidence genuinely changes;
3. a complete canonical replacement suffix.

The builder preserves every earlier layer exactly and rejects any rewrite that
introduces a first failure earlier than the residual being handled.

Current ordered diagnostic composition:

```text
V3 base
  -> Workday CXS adapter, only while first_failure == inventory
  -> bounded portal-delegation adapter, only if inventory still remains
  -> remaining residual cohort
```

Workday rewrites from `provider` because it supplies provider evidence. Portal
rewrites from `delegation` because it proves an explicit cross-surface handoff; it
preserves the already-evaluated Provider layer rather than inventing classification.

Diagnostic overlay request caps remain independent measurement boundaries. They are
not authority for future materialized connectors to probe every adapter blindly.
Stable recipes must compile only capabilities supported by candidate evidence.

## Sole continuation sequence

1. In the canonical WSL runtime/database, run
   `scripts/run_deterministic_connector_builder_layer_audit_v5.py` against the same
   65-candidate cohort.
2. Record exact V3 -> V4 -> V5 transitions, including exact Workday and portal
   promotions. Do not change product coverage from diagnostic READY.
3. Re-cluster the V5 residual first-failure population.
4. Choose the next deterministic capability by reusable population lift, evidence
   strength and boundedness — never by named-employer convenience.
5. Continue until no evidence-backed bounded generic deterministic class remains.
6. Materialize only stable evidence-backed recipes and update product coverage only
   from unchanged strict E2E proof.
7. Only exhausted residuals may then enter the booster path.

The next engineering claim therefore requires **live V5 cohort evidence**, not more
unmeasured adapter code.

## Retention / DRJ semantic dispositions

### ACTIVE / KEEP

- issue `#676`;
- canonical `main` content delivered by PRs `#682` and `#685`;
- `docs/planning/active/acq_generalization_90_target.md`;
- this re-entry file and JSON companion;
- `docs/planning/active/deterministic_connector_builder_layers.md`;
- V1-V5 builder audit scripts and focused tests;
- merged Origin V2, Workday and portal-delegation source files.

These items must not become retention candidates merely because they are diagnostic,
migration-originated, or not yet credited to product coverage.

### PRESERVE — historical provenance

- migration checkpoint MD/JSON;
- issue/PR comments containing exact live 65-candidate A/B counts and Clarios traces;
- PR `#682` migration-delivery history;
- PR `#685` V5 composition history and its qualified gate evidence.

### SUPERSEDED / no continuation authority

- PR `#678` and branch `agent/676-deterministic-connector-builder`;
- PR `#682` and branch `agent/676-generalization-harvest`;
- closed Draft PR `#684` (same V5 code head as #685, closed only because the
  ready-for-review connector action failed);
- merged PR `#685` branch after delivery.

Qualified content is preserved on `main`. Branch/worktree retirement remains a
separate DRJ technical action requiring fresh local observation.

### DISPOSABLE / not repository truth

Former `/tmp/deterministic_*` audit files listed in the migration checkpoint may
disappear. Their relevant result truth is versioned in repository documents.

## DRJ effect boundary

`DRJ-RECONCILE-REQUEST.json` remains `NO_REQUEST` unless a fresh local hygiene pass
observes exact safe retirement candidates. Dirty, unpushed, divergent, checked-out,
ambiguous or closed-unmerged local state remains fail-closed/protected.

DRJ is retention/reconciliation infrastructure, not ACQ-676 work-admission authority.

## Re-entry commandment

Before editing ACQ-676, read in this order:

1. `PROJECT-HYGIENE.json`;
2. `PROJECT-LOCAL-WORKSPACE.json`;
3. `PROJECT-DRJ.json`;
4. `docs/current/README.md`;
5. this file;
6. `acq_generalization_90_target.md`;
7. live issue `#676` and current open PR state;
8. current `origin/main`, branch/worktree relationship and latest CI.

Do not resume from historical #676 feature branches or chat memory.
