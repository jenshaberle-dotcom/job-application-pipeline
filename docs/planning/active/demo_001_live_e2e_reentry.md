# DEMO-001 — live E2E demo re-entry

Status: **ACTIVE — DEMO MODE**  
Owner issue: `#707`  
Demo date: `2026-09-03`  
Repository: `jenshaberle-dotcom/job-application-pipeline` (`id=1230805345`)

## Canonical checkpoint

Current merged repository truth at this re-entry reconciliation:

```text
main = b5ecfdd3df563f7a16943a4898632c4d88335aca
```

This supersedes the older re-entry checkpoint that still ended around `#771`.

The remaining DEMO-001 acceptance frontier is **real local runtime / PostgreSQL truth**. Repository implementation, CI, React build and operator preparation are already qualified. No local Product/DB PASS is asserted by this file.

## Required reads

Before continuing DEMO-001 work, read:

1. this file;
2. `docs/planning/active/demo_001_operator_test_preparation.md`;
3. `scripts/prepare_product_v1_demo_operator_test.py`;
4. `scripts/run_product_v1_live_demo.py`;
5. owner issue `#707`, especially the latest operator-test preparation checkpoint.

Chat history is supporting context only and must not override these repository surfaces or live local preflight evidence.

## Product outcome

The demo must show one truthful vertical journey:

```text
Discover
-> Verify
-> Bronze / Silver / Gold evidence
-> Rank
-> authoritative current Top 5
-> select one real current job
-> Application Workspace
-> source-grounded draft_for_review
```

The presentation compresses that to:

```text
Discover -> Verify -> Rank -> Prepare
```

That compression is presentation only. It does not replace source, lifecycle, Product V1, ranking, Candidate Fact or application authority.

## Hard truth boundaries

- real current runtime/DB truth only;
- no fabricated Product V1 rows, Top-5 fill or demo-only success paths;
- employer-origin evidence remains required for application authority;
- approved hard-filter/ranking policy and read models remain authoritative;
- Candidate Facts plus exact current vacancy evidence remain factual authority for draft claims;
- application output is `draft_for_review` only;
- no automatic application submission or send authority;
- no source activation, ranking or application authority may be inferred from UI presentation;
- the React Product V1 Control Center is the canonical demo UI;
- local PostgreSQL/source/provider/scheduler/host operations remain explicit operator actions.

## Current merged implementation

The repository now contains the full generic demo path plus the final low-risk presentation and operator hardening:

- generic employer-origin source/lifecycle path into Bronze/Silver;
- Product V1 assessment, evidence-bound capability/hard-filter review and ranking-score persistence;
- authoritative Product V1 Top-5 read model;
- guarded Candidate Fact and approved base-document prerequisites;
- exact-current-vacancy Application Workspace;
- bounded provider drafter plus deterministic evidence-first provider-free fallback, both review-only;
- canonical launcher with stale-artifact invalidation, atomic diagnostics and SHA-bound preflight -> workspace -> draft lineage;
- one current vacancy-detail fetch in canonical readiness, then offline final handoff validation;
- DB-backed **Data Layers** tab from `#771` showing Bronze/Silver/Gold inventory, 14-day materialization activity, coverage, freshness and source contribution without fabricating historical Rankable/Top-5 series;
- target-profile breadth covering ML Engineer, MLOps/ML Platform, AI Platform, AI/ML/Data Reliability plus the Data Engineer/Data Platform/Analytics bridge;
- strict-proven source review checkpoint from `#767`: `36/36` reviewed, `33/36` current detail-proven and `23` with a useful operator-review candidate on that merged checkpoint. Unmerged `#769` evidence must not be promoted silently;
- `#773`: local SVG pictograms, stronger visual hierarchy, truthful empty/loading/blocked states, `Discover -> Verify -> Rank -> Prepare`, operator attention panel, explanatory layer/profile-fit tooltips and future-safe APP-TRACK lifecycle preview;
- `#775`: Data Layers navigation/recovery hardening, `Esc` recovery, correct active topline identity and reduced-motion fallback;
- `#776`: fail-closed operator DB/test preparation helper;
- `#777`: persistent presentation-only boundary ribbon: `Live DB truth · Review only · No submit / send`.

## Latest qualified repository gates

- `#775` merged after Re-entry `#2048` and Pipeline CI `#1108` PASS;
- `#776` merged after Re-entry `#2056` and Pipeline CI `#1112` PASS;
- `#777` merged after Re-entry `#2063` and Pipeline CI `#1114` PASS;
- React Control Center build and full Python/Ruff/migration-governance suites passed on the exact heads before merge.

These gates prove repository integrity only. They do **not** prove current local DB/Product readiness.

## DB migration frontier

Demo-required schema truth still includes migrations `102`–`104` and their required relations/column shape.

Current repository also contains:

```text
105_allow_exact_script_migration_tracking_mode.sql
```

Migration 105 only repairs the migration-tracking execution-mode vocabulary so guarded exact script applies can be recorded as `script_apply_exact`; it does not change Product V1 data, ranking, sources or applications.

Because 105 now exists, do not assume the local machine still has **sole pending 104**. The local pending set must be observed first.

Never force through:

- multiple unexpected pending migrations;
- checksum mismatches;
- failed required migration tracking;
- missing migration files;
- relation/column shape disagreement.

Do not use a broad migration apply merely to make the demo pass.

## Sole next action

On the operator machine, refresh canonical repo truth first:

```bash
cd "$HOME/projects/job-application-pipeline"
git fetch origin main
git switch main
git pull --ff-only origin main
```

Then run the new default **read-only** preparation helper:

```bash
python scripts/prepare_product_v1_demo_operator_test.py
```

Interpret only its explicit state:

### `READY_FOR_PREFLIGHT`

Run:

```bash
python scripts/prepare_product_v1_demo_operator_test.py --run-preflight
```

### `QUALIFIED_EXACT_104`

Only in that exact state, run:

```bash
python scripts/prepare_product_v1_demo_operator_test.py \
  --apply-qualified-104 \
  --run-preflight
```

The helper re-checks exact clean local `main`, requires 104 to be the sole clean pending target, delegates the write to the existing exact migration runner with `--require-sole-pending`, re-inspects schema truth, and only then delegates to the canonical demo preflight.

### `BLOCKED`

Do not guess and do not run broad migration apply. Preserve the complete helper output and continue only from the exact reported local blocker.

## Canonical readiness authority

`scripts/run_product_v1_live_demo.py --preflight-only` remains the sole full demo readiness path.

A genuine READY requires regenerated current artifacts:

```text
.runtime/demo/product_v1_demo_preflight.json
.runtime/demo/product_v1_demo_workspace_probe.json
.runtime/demo/product_v1_demo_draft_probe.json
```

and terminal result:

```text
PRODUCT_V1_LIVE_DEMO=READY
```

The launcher must continue to prove:

- coherent schema/tracking truth;
- real current employer-origin Product V1 data;
- authoritative Top-5 selection;
- approved Candidate Fact and source-document readiness;
- exact current vacancy binding;
- non-empty Candidate Fact claim plan;
- source-grounded provider-free draft proof;
- zero preflight provider/write/submission/send authority.

## Presentation start after READY

After a real successful preflight, start the Control Center with the already-qualified frontend build:

```bash
python scripts/run_product_v1_live_demo.py --reuse-frontend
```

Operator test route:

```text
Overall
-> Data Layers
-> Jobs / Top 5
-> Application
-> Applications
-> Sources
```

Verify particularly:

- `Discover -> Verify -> Rank -> Prepare` reads naturally;
- Data Layers can always be exited via normal navigation and `Esc`;
- Bronze/Silver/Gold values remain honest/null-preserving;
- Top 5 never fabricates missing slots;
- Application Workspace remains `REVIEW REQUIRED` / no-auto-submit;
- top-line truth ribbon remains visible on normal-width presentation surfaces.

## After the operator test

Do not open another backend-critical feature path before the real operator result is known.

If the local preflight is READY and the E2E walkthrough has no material defect, only bounded presentation/UX polish is appropriate before the demo.

If a real blocker appears, fix the **narrowest proven blocker** only.

Post-demo immediate product extension remains `APP-TRACK-001` / issue `#737`:

```text
Prepared -> Applied -> Reply -> Interview -> Offer -> Closed
```

Email/recruiter communication is evidence, not silent application-state authority.
