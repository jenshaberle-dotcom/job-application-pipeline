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

Canonical merged `main` at this re-entry read is `80cda242b89fee7cc56bb43f24aaa1a70c34806d` (`#767`). It contains the complete generic repository path required for the demo handoff plus the latest merged profile/source-evidence hardening:

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
- DB-backed Agent Monitor v1 remains available in the Jinja2 operational fallback, with lifecycle/gate/orchestrator provenance and explicit distinction from dedicated runtime-health telemetry;
- target-profile breadth includes ML Engineer, MLOps, ML/AI Platform, AI/ML/Data Reliability and the Data Engineer/Data Platform/Analytics bridge instead of presenting the product as Data-Engineering-only (`#759`, `#763`);
- profile-term matching is field-scoped so multi-word roles cannot be synthesized from unrelated employer/location fields (`#764`);
- Product V1 admission is recall-first before vacancy-detail assessment; role relevance is a priority/score signal and no longer an overly early false-negative admission veto (`#765`, `#766`);
- the historical strict-proven connector cohort has been re-reviewed as a 36-source admission pool, with `36/36` reviewed, `33/36` carrying current concrete detail proof on merged `main`, and `23` sources carrying at least one useful operator-review candidate (`#767`). Listing-only evidence may reach manual review but grants no detail, activation, ranking, Top-5 or application authority.

Key merged demo hardening before the overnight profile/source push includes ranking persistence `#724`, schema/readiness hardening `#725`–`#727`, provider-free review resilience/provenance `#728`–`#730`, single-fetch final-draft handoff `#731`, stale-artifact invalidation `#732`, bounded artifact deletion `#733`, cross-artifact lineage binding `#734`, duplicate live draft-probe retirement `#735`, atomic readiness publication `#736`, and presentation UX compression `#739`.

### Overnight 2026-09-02/03 delta

The post-GUI overnight work materially changed the repository/evidence frontier and therefore supersedes the older checkpoint that ended at the presentation-hardening block:

1. `#759` widened deterministic Silver relevance to the actual demo profile: ML Engineer, MLOps/ML Platform, AI Platform and AI/Data Reliability while preserving the Data Engineering bridge.
2. `#760` added a bounded read-only live detail scout for the existing demo tranche; `#761` projected deterministic review-fit on loaded jobs without changing authoritative Product V1 ranking.
3. `#762` hardened application drafts around unique exact vacancy evidence while preserving Candidate Facts/base documents as authority and `draft_for_review` only.
4. `#763` expanded the two authorized Personio profile search terms to ML/reliability families.
5. `#764` fixed a generic cross-field false-positive bug in multi-word profile matching.
6. `#765` made Product V1 contender admission recall-first before detail assessment; `#766` added a read-only audit for that wider current frontier.
7. `#767` completed the all-source strict-proven review on merged `main`: `36/36` reviewed, `33/36` current detail-proven, `23` with useful operator-review candidates. This is evidence-only by design: no source activation, DB/Bronze/Silver/Gold mutation, ranking/Top-5 authority or application authority was created.

A later branch, draft PR `#769` based exactly on `main@80cda242...`, is **pending evidence, not canonical main truth**. Its current head reports `35/36` strict-proven sources with current concrete detail proof after resolving Amadeus Fire and CGM through current official evidence/delegation; TrustYou remains the sole source without a current substantive vacancy detail. The branch explicitly preserves zero DB/Bronze/Silver/Gold writes and zero ranking/application authority. Re-entry must not silently promote this `35/36` state until the branch is qualified and merged.

The earlier presentation-only snapshot PR `#768` is not a backend truth contract and predates the completed all-source harvest. Do not use its static counts as the canonical demo metrics surface.

### Requested demo observability slice — Bronze / Silver / Gold

Operator request on 2026-09-03: add a dedicated React Control Center tab for **Bronze / Silver / Gold** with DB-backed metrics and a time trend. This is the preferred next bounded presentation/observability slice because the backend already owns the required timestamps and read models; it must not introduce demo-only persistence or synthetic history.

Truth sources already present:

- Bronze inventory: `raw_jobs.created_at` / `raw_jobs.fetched_at`;
- repeated Bronze/source activity: append-only `job_observations.observed_at`;
- ingestion execution: `ingestion_runs.started_at`, `finished_at`, `total_loaded`, `inserted_count`, `duplicate_count`, `status`;
- Silver materialization: `silver_jobs.normalized_at` / `created_at`;
- Gold / Product V1 materialization: `job_product_assessments.assessed_at` / `updated_at`;
- current Gold state: `gold_product_v1_job_readiness`, canonical Top-5/readiness views and existing Product V1 summary;
- current per-source Bronze/Silver inventory and latest-ingestion values are already projected through `source_connector_overview` into the Product V1 payload.

Preferred first version is read-only and migration-free:

1. **Inventory now** — Bronze unique jobs, Silver canonical jobs, Gold assessed jobs, current rankable jobs and authoritative Top-5 count.
2. **14-day flow** — daily `Bronze new`, `Silver normalized`, `Gold assessed`; optionally show `Bronze observations` as a separate activity series so repeated observations are not confused with new unique jobs.
3. **Coverage ratios** — Silver/Bronze materialization coverage, Gold/Silver assessment coverage, current rankable/Gold share. Label these as coverage/materialization, not quality or funnel conversion.
4. **Freshness** — latest ingestion finish, latest Bronze observation, latest Silver normalization, latest Gold assessment.
5. **Source breakdown** — reuse existing source overview for source, last ingestion, inserted/loaded, Bronze count, Silver count and lifecycle/attention state.

Historical Gold caution: a current Gold view cannot reconstruct past daily rankable/Top-5 membership. The first demo chart therefore uses `job_product_assessments.assessed_at` as **Gold assessment/materialization activity**, not a fabricated historical `rankable` series. True rankable/Top-5 history should only be added later from an explicit append-only event/snapshot authority if product value justifies it.

This metrics tab is observability only. It must perform no source execution, DB write, scheduler mutation, ranking change, application action or authority promotion.

## Current frontier

The remaining demo frontier is primarily **live local truth plus the requested DB-backed data-layer observability**, not a need for new source/ranking shortcuts.

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

The Bronze/Silver/Gold observability tab is a presentation enhancement, not authority to infer missing live DB values. Agent Monitor polish, broader approval-safe UI actions and APP-TRACK-001 remain outside core readiness unless explicitly reprioritized.

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
