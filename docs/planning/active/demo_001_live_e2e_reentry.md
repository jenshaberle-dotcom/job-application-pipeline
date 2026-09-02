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
- existing React Control Center remains the canonical demo UI.

## Consolidated presentation and observability contract

Parallel demo hardening and UI work are now one path rather than competing paths.

### Canonical presentation layer

The canonical live-demo presentation is the React Product V1 Control Center plus
the bounded `DemoApplicationWorkspace`.

The human-facing presentation compresses the internal machine into:

```text
Discover -> Verify -> Rank -> Prepare
```

This is a presentation mapping only. It does not replace or weaken employer-origin,
Bronze/Silver/Gold, lifecycle, gate, ranking, Candidate Fact or application authority.
Technical evidence remains available through progressive disclosure instead of
occupying the primary presentation surface.

The Application Workspace therefore presents:

- authoritative Top-5 master/detail selection;
- deterministic Product V1 score as `profile fit`, never as a new AI-ranking authority;
- vacancy verification, Candidate Fact and approved-source-document readiness;
- one explicit `Prepare review draft` action;
- document-like CV/application-letter review output;
- prominent `REVIEW REQUIRED` and no-auto-submit/no-send boundary;
- fingerprints, exact evidence and write/provider counters behind evidence/audit details.

### Agent Monitor placement

The Jinja2 Search Intelligence Control Center remains an operational fallback and
contains DB-backed Agent Monitor v1.

Agent Monitor v1 is useful supporting evidence, but it is **not** a second canonical
demo path and must not become a new dependency of `scripts/run_product_v1_live_demo.py`.
Its cards summarize existing lifecycle, gate-review, gate-event and orchestrator
signals. Current lifecycle state remains authoritative and newer blockers can
supersede historical passes.

`Agent health` in this surface means persisted output/signal usability. It does not
mean that JAP currently owns a dedicated runtime heartbeat, per-agent quality metric,
failure-rate or execution-telemetry model. True runtime agent health remains future
work. If Agent Monitor is shown as a backup/demo-detail surface, describe it as
DB-backed lifecycle/gate/orchestrator observability rather than real-time agent
runtime health.

### Approval-safe UI actions

Do not add a new general mutation framework to tomorrow's critical path.

The React Control Center already has narrowly allowlisted reviewed actions for:

- source-connector final approval;
- append-only Product V1 job-review labels.

The Application Workspace adds only the already-bounded explicit review-draft action;
it grants no approval, persistence, submission or send authority.

The broader UI-001 approval-safe review-actions foundation remains post-demo work.
Future actions must show evidence, current state, side effects and expected result,
require explicit confirmation, call a bounded service, write audit/provenance and
refresh from DB/read models.

### Post-application tracking

APP-TRACK-001 / issue `#737` is retained as the immediate post-demo product extension:

```text
Prepare -> operator reviews -> manual submission confirmation -> Track
```

Gmail/recruiter communication will become evidence/event-candidate input, not silent
application-state authority. It must not add Gmail/private-runtime dependencies to
DEMO-001 readiness on 2026-09-03.

## Definition of done

1. One reliable preflight exposes live demo readiness before presentation time.
2. Control Center shows current source/connector lifecycle and Bronze/Silver presence from existing truth.
3. Current Product V1 jobs and authoritative Top-5 are visible without fabricated fill.
4. One authoritative Top-5 employer-origin job can open a bounded Application Workspace.
5. Application Workspace shows source-document readiness, Candidate Fact readiness, job evidence, and draft boundaries.
6. An operator-triggered bounded drafting path can return a validated source-grounded `draft_for_review` package when all prerequisites are present.
7. The final UI visibly presents CV assistance + application-letter assistance + evidence/uncertainty while retaining explicit REVIEW REQUIRED / NO SUBMISSION AUTHORITY semantics.
8. Primary demo language stays product-oriented while deeper evidence/audit detail remains inspectable on demand.
9. Current Pipeline CI and Re-entry identity remain green.

## Current repository implementation

Current `main` contains the complete generic repository path required for the demo handoff:

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
- provider-validated application drafter plus deterministic evidence-first provider-free fallback, both review-only;
- React Application Workspace presentation with explicit draft provenance, REVIEW REQUIRED and NO AUTO-SUBMIT boundaries;
- presentation-focused UX compression with `Discover -> Verify -> Rank -> Prepare`, authoritative Top-5 master/detail selection, compact profile-fit visualization, progressive evidence/audit disclosure and document-like review output (`#739`);
- one canonical live-demo launcher that invalidates stale diagnostics, builds/reuses the React UI, requires Product/Schema preflight PASS, performs one current vacancy-detail fetch for the selected Top-5 Application Workspace, carries the provider-free review-draft proof forward from that same context, and validates the final draft handoff offline before READY/server startup;
- exact SHA-256 lineage binds workspace proof to its preflight artifact and final draft proof to the exact preflight/workspace artifacts;
- readiness artifact invalidation is restricted to JSON diagnostics under `.runtime/demo/` and cannot unlink arbitrary operator paths;
- child readiness diagnostics are staged, validated and atomically published so an interrupted/truncated write cannot masquerade as a current readiness artifact (`#736`);
- DB-backed Agent Monitor v1 remains available in the Jinja2 operational fallback, with lifecycle/gate/orchestrator provenance and explicit distinction from dedicated runtime-health telemetry.

Key merged demo hardening through the current checkpoint includes ranking persistence `#724`, schema/readiness hardening `#725`–`#727`, provider-free review resilience/provenance `#728`–`#730`, single-fetch final-draft handoff `#731`, stale-artifact invalidation `#732`, bounded artifact deletion `#733`, cross-artifact lineage binding `#734`, duplicate live draft-probe retirement `#735`, atomic readiness publication `#736`, and presentation UX compression `#739`.

The former standalone live draft-readiness probe that predated the single-fetch handoff is retired. Its unique deterministic-draft assertions are already covered by `test_product_v1_evidence_first_draft.py` and the canonical single-fetch handoff tests. The only canonical full readiness entrypoint is `scripts/run_product_v1_live_demo.py`.

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
8. selected Top-5 job exact-binds to current vacancy detail, a non-empty Candidate Fact claim plan, approved source documents and zero-write/provider boundaries in the Application Workspace;
9. the same exact-bound workspace produces a provider-free evidence-first `draft_for_review` proof before READY;
10. during the presentation, an explicit operator/UI action may use provider polishing when available or the visibly labelled evidence-first fallback; neither grants approval/submission/send authority.

The readiness path is intentionally fail-closed and must identify the narrowest blocking gate instead of inventing success.

Agent Monitor polish, broader approval-safe UI actions and APP-TRACK-001 are not demo-readiness blockers.

## Canonical local operator handoff

From canonical local `main`, refresh and inspect migration truth:

```bash
cd "$HOME/projects/job-application-pipeline"
git fetch origin main
git switch main
git pull --ff-only origin main
python scripts/apply_db_migrations.py --status
```

If and only if the status/preflight reports a sole pending migration `104_create_product_v1_ranking_score_reviews.sql`, the qualified exact migration runner is:

```bash
python scripts/apply_db_migrations.py \
  --apply-exact 104_create_product_v1_ranking_score_reviews.sql \
  --require-sole-pending \
  --applied-by demo-001
```

If multiple migrations are pending, checksums mismatch, a required migration is tracked with a non-successful status, or relation/column shape disagrees with tracking, do **not** guess or force through. Repair that exact local runtime state first.

Once schema state is coherent, use the single canonical full readiness path:

```bash
python scripts/run_product_v1_live_demo.py --preflight-only
```

That command builds the existing React Control Center, runs Product/Schema preflight, selects only real authoritative Top-5 truth, probes the exact selected Application Workspace with at most one current vacancy-detail fetch, builds the deterministic evidence-first review package from the same in-memory context, then validates the final handoff offline. READY requires exact job/evidence/artifact lineage plus zero provider/write/submission/send authority in preflight.

For presentation startup after a previously qualified frontend build:

```bash
python scripts/run_product_v1_live_demo.py --reuse-frontend
```

Durable local artifacts, regenerated for the current launcher attempt only:

- `.runtime/demo/product_v1_demo_preflight.json`;
- `.runtime/demo/product_v1_demo_workspace_probe.json`;
- `.runtime/demo/product_v1_demo_draft_probe.json`.

Any command that mutates live Product V1 assessment/review/ranking truth remains explicit operator work and must use the existing guarded plan/apply token boundaries. Draft generation itself remains an explicit UI/operator action after workspace readiness and never grants approval/submission/send authority.

## Runner-first continuation

While local runtime evidence is unavailable, repository-only work may continue on demo reliability, diagnostics, presentation safety and deterministic contracts. Every repository slice must start from fresh current `main`, pass Pipeline CI + Re-entry identity, and leave durable PR/issue evidence.

ACQ-GENERALIZATION-90 / issue `#676` remains retained and resumable but is still deprioritized for the demo window. Its measured product coverage remains `36/65` until a future unchanged strict E2E proof establishes a higher numerator.
