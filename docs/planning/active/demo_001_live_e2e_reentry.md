# DEMO-001 — live E2E demo re-entry

Status: **ACTIVE — DEMO MODE**  
Owner issue: `#707`  
Demo date: `2026-09-03`

## Operator outcome

Demonstrate the existing Job Application Pipeline as one truthful product journey:

```text
discovery / market evidence
-> employer + origin
-> connector/source health
-> Bronze
-> Silver
-> Gold / Product V1
-> authoritative Top 5
-> select one current job
-> Application Workspace
-> source-grounded draft_for_review
```

The demo must end with a concrete reviewable application package, not merely a ranking screen.

## Work admission

`POST-MIGRATION-RESTART=PASS` is positive work-admission authority for this repository. Normal JAP feature work continues under fresh-current-main + declared temporary-worktree discipline. Other projects' migration state is not a blocker for this project. Portfolio all-PASS remains relevant only to separately coordinated portfolio-wide Warmrunner/DRJ/convergence work.

JAP development is runner-first. Repository code, tests, React builds, CI, re-entry and provider-free diagnostics belong on fresh branches/PRs and GitHub Actions. Live local Postgres mutation/inspection, source/provider execution, scheduler/host work and local Control Center runtime remain explicit operator work. Do not mutate the separate `job-pipeline-runtime` repository merely to make the demo pass.

## Hard truth boundaries

- real current runtime/DB truth only;
- no fake Product V1 rows, fabricated Top-5 jobs, or demo-only success branches;
- aggregator evidence never becomes employer-origin/application authority by presentation alone;
- approved ranking and hard-filter policy/read models remain authoritative;
- application generation is `draft_for_review` only;
- Candidate Facts and exact vacancy evidence remain factual authority for generated claims;
- no automatic application submission or send action;
- no proof or source-authority weakening;
- existing React Control Center remains the demo UI.

## Definition of done

1. One reliable preflight exposes live demo readiness before presentation time.
2. Control Center shows current source/connector lifecycle and Bronze/Silver presence from existing truth.
3. Current Product V1 jobs and authoritative Top-5 are visible without fabricated fill.
4. One authoritative Top-5 employer-origin job can open a bounded Application Workspace.
5. Application Workspace shows source-document readiness, Candidate Fact readiness, job evidence, and draft boundaries.
6. An operator-triggered bounded drafting path can return a validated source-grounded `draft_for_review` package when all prerequisites are present.
7. The final UI visibly presents CV assistance + application-letter assistance + evidence/uncertainty while retaining explicit REVIEW REQUIRED / NO SUBMISSION AUTHORITY semantics.
8. Current Pipeline CI and Re-entry identity remain green.

## Current repository implementation

The original first-slice description is obsolete. Current `main` now contains the complete generic repository path required for the demo handoff:

- read-only Product V1 demo preflight and cohort/source diagnostics;
- resilient generic assessment materialization from current employer-origin evidence;
- guarded private base-CV / base-letter registration;
- deterministic hard-filter evidence scout;
- executable version-bound hard-filter manual-review authority without deterministic-failure override;
- guarded local Candidate Fact profile approval;
- version-bound Candidate Fact -> capability-fit review authority;
- deterministic source-grounded ranking-evidence core;
- migration `104_create_product_v1_ranking_score_reviews.sql` and guarded ranking-score persistence with an independent ranking revision clock;
- canonical Product V1 Top-5 read model/policy remains rank authority;
- bounded Application Workspace runtime on an authoritative Top-5 job;
- explicit operator-triggered source-grounded application drafter;
- React Application Workspace presentation with REVIEW REQUIRED / NO AUTO-SUBMIT boundaries.

Key merged demo slices through the current checkpoint include PRs `#708`–`#725`, with ranking persistence in `#724` and schema-frontier preflight diagnostics in `#725`.

## Current frontier

The remaining demo frontier is primarily **live local truth**, not missing repository feature code.

The local runtime must prove, in order:

1. demo schema frontier 102–104 is applied, tracked with qualified status and structurally present;
2. current employer-origin jobs exist through Bronze/Silver/lifecycle;
3. eligible jobs have Product V1 assessment truth;
4. capability-fit and hard-filter gates are resolved without weakening policy;
5. ranking component scores are persisted from exact current vacancy evidence;
6. at least one real job reaches authoritative Top-5 truth;
7. approved Candidate Fact profile plus approved base CV/base letter are present;
8. selected Top-5 job opens the bounded Application Workspace;
9. only after context readiness, an explicit operator action may invoke the drafter and return `draft_for_review`.

The preflight is intentionally read-only and must identify the narrowest blocking gate instead of inventing success.

## Canonical local operator handoff

From canonical local `main`, first refresh and inspect only:

```bash
cd "$HOME/projects/job-application-pipeline"
git fetch origin main
git switch main
git pull --ff-only origin main
python scripts/apply_db_migrations.py --status
python scripts/run_product_v1_demo_preflight.py
```

If the preflight reports a sole pending migration `104_create_product_v1_ranking_score_reviews.sql`, the qualified exact migration runner is:

```bash
python scripts/apply_db_migrations.py \
  --apply-exact 104_create_product_v1_ranking_score_reviews.sql \
  --require-sole-pending \
  --applied-by demo-001
```

If multiple migrations are pending, checksums mismatch, a required migration is tracked with a non-successful status, or relation/column shape disagrees with tracking, do **not** guess or force through. Preserve the preflight/status artifact and repair that exact local runtime state first.

After schema readiness, continue with the narrowest blocker reported by `.runtime/demo/product_v1_demo_preflight.json`. Any command that mutates live Product V1 assessment/review/ranking truth remains explicit operator work and must use the existing guarded plan/apply token boundaries.

## Runner-first continuation

While local runtime evidence is unavailable, repository-only work may continue on demo reliability, diagnostics, presentation safety and deterministic contracts. Every repository slice must start from fresh current `main`, pass Pipeline CI + Re-entry identity, and leave durable PR/issue evidence.

ACQ-GENERALIZATION-90 / issue `#676` remains retained and resumable but is still deprioritized for the demo window. Its measured product coverage remains `36/65` until a future unchanged strict E2E proof establishes a higher numerator.
