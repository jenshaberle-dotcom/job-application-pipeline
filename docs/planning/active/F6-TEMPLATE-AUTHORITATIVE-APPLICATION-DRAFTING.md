# F6 — Template-Authoritative Application Drafting

Status: ACTIVE — Slices A/B operator accepted; Slice C exact-target/product identity proven, exact-observation reuse in qualification

## Outcome

F6 is the final package of the current frozen Product campaign.

The application workflow may adapt **text only** inside two operator-approved private PDF layouts. The layouts themselves are immutable product authority. Candidate claims remain grounded in approved Candidate Facts and exact current Employer-Origin evidence. Human review is mandatory. F6 grants no automatic submission or send authority.

## Canonical private templates

The PDF bytes remain local/private. Public repository truth stores only their exact binary identities, page geometry and editable-zone contract.

| Document | Template ID | SHA-256 | Geometry |
| --- | --- | --- | --- |
| Application letter | `f6-application-letter-hornetsecurity-2026-09-17-v1` | `e533e27c8bc4ac04b64e29e8d91dcfd134d23af075f76ec179e0d9d0ab1410c8` | 1 page, Letter, 612 x 792 pt |
| CV | `f6-cv-hornetsecurity-2026-09-17-v1` | `8f67040b6ef9248e734a18e46df87fa786f33c3c8f605785baf7ad324432e041` | 2 pages, A4, 595.32 x 841.92 pt each |

Canonical machine-readable authority:

`config/application_templates/f6_template_authority_v1.json`

The mixed page formats are intentional current operator truth. No normalization to A4 or another geometry is authorized.

## Layout boundary

Immutable without a new explicit operator template approval:

- page size and page count;
- portrait/photo placement;
- navy header rules and section rules;
- signature image and its position;
- column/grid geometry;
- panel backgrounds;
- font/layout/spacing geometry outside declared zones.

Only manifest-declared text zones may change. Text overflow must fail closed rather than move graphics, resize the page, reflow into a new design or manufacture an alternate page.

## Content authority

Generated/adapted text may use only:

1. approved Candidate Facts;
2. exact current Employer-Origin vacancy evidence;
3. structural text already present in the approved template when it is not treated as a new candidate claim.

Missing evidence remains missing/unknown. Template text is not independent fact authority.

## Hard-cut regression rule

F6 removes the previous generic document-generation authority. The following legacy paths are physically absent and regression-gated against return:

- retired module basename `product_v1_application_document_export.py`;
- retired module basename `product_v1_application_document_package.py`;
- retired stylesheet basename `application-package-downloads.css`;
- their dedicated generic renderer/package tests.

The retired path created new A4/DOCX documents independent of the approved layouts. It is incompatible with F6 and has no fallback authority.

The browser/CLI intake also no longer accepts arbitrary replacement PDFs. It accepts only an exact F6 hash + page-geometry match. Installing a canonical template supersedes DB authority for the prior approved row and removes older managed upload bytes of that document type.

## Slice A — Template Authority

Status: **COMPLETE / OPERATOR ACCEPTED** on installed 1.0.68. The later 1.0.69 runtime LF hardening did not change F6 template authority.

Acceptance criteria:

- exactly two canonical templates;
- exact binary SHA-256 and page geometry are enforced;
- binaries remain private/local;
- explicit editable zones are public and bounded within their pages;
- arbitrary or visually similar PDFs fail closed;
- Product readiness requires exact template authority, not merely an `approved` DB row;
- old generic renderer/package paths are physically absent;
- Control Center explains the authority and exposes only exact-template verification;
- at Slice A completion, generation could produce grounded review text while rendering was still pending; this historical state is superseded by the accepted Slice-B renderer;
- database/application/submission/send authority remains unchanged.

### Slice A operator evidence

Installed 1.0.68 successfully verified both exact private templates through the Product surface. The generic DOCX/A4 path remained absent. This closes Slice A and authorizes Slice B only; it grants no final PDF export or submission/send authority.

## Slice B — Template-Bound Renderer — COMPLETE / OPERATOR ACCEPTED

PR #999 introduces a new F6-only renderer authority. It is not a revival of the retired generic exporter.

Acceptance criteria:

- exact F6 hash/geometry validation remains the entry gate;
- only manifest-declared text-zone IDs are accepted;
- redaction removes text only and preserves images/vector graphics;
- no automatic font/page scaling is permitted; overflow fails closed;
- every page is raster-compared against its exact source template and all pixels outside declared zones must remain identical;
- evidence contains source/output hashes and per-page outside-zone pixel hashes/counts;
- rendered bytes remain review-only and grant no application/submission/send authority;
- CI uses synthetic PDFs only; private template bytes remain local.

### Slice B operator evidence

Installed Product **1.0.71** on exact release source `a7eae418cbcc8c901070d9db65505cece086e6f7` completed the real private-template qualification successfully.

The local proof covered exactly both canonical templates (`template_count: 2`). The application-letter render changed only `body.paragraph_1`; the CV render changed only `p1.short_profile`. Every page reported `outside_zone_pixel_identity: true` and `changed_pixels: 0` outside declared zones. Rendered PDFs were not persisted and private template paths/bytes were not disclosed. The qualifier reported zero database reads/writes, provider/network requests, application actions, submission actions and send actions, and ended with `F6_TEMPLATE_RENDERER_QUALIFICATION=PASS`.

This closes Slice B and authorizes Slice C only. It does not grant draft approval, application, submission or send authority.

## Slice C — Review/Edit + Local PDF Export — IN QUALIFICATION

The first Slice-C implementation shipped as **1.0.72** from exact source `f55b8adab62337b4e0a28c3ad9bcb56186c84cc6`. It provides manifest-zone editing, source-manifest-bound local PDF rendering and the accepted Slice-B outside-zone pixel proof.

The first installed operator attempt exposed a separate pre-existing Product coupling before the new PDF surface could be exercised: the Application Workspace accepted only `gold_product_v1_top_jobs` targets while current Product truth contained **0 rankable / 0 Top-5** rows.

### Runtime diagnosis — 2026-09-24

The installed Product payload reported 80 current active jobs and 45 authoritative Affinity rows, but zero rankable jobs. Its readiness population was dominated by `hard_filter_evidence_required` plus `assessment_required`; VALUNY Silver 613 was active, Origin-validated and Affinity-authoritative while its hard-filter state remained unknown.

A separate verified RCC warm-runtime read-only proof confirmed the population-level condition without mutating authority: rankable `0`, Top-5 `0`, 65 hard-filter-evidence-required rows, 13 assessment-required rows and 2 blocked hard-filter rows. Capability Fit remained unknown for the highest-Affinity blocked rows. This is consistent with the existing PD-053/054/059 fail-closed Product contract and must not be repaired by manufacturing ranking authority.

Refresh is not a ranking/materialization action. Repeating UI refresh cannot legitimately turn unknown Fit/hard-filter evidence into Top-5 truth.

### Operator-selected drafting boundary

Candidate target: **1.0.73** on `feature/f6-c-operator-selected-target`.

F6 drafting and Top-5 recommendation authority are now separated deliberately:

- Top-5 remains unchanged and fail-closed. No row is promoted, ranked or threshold-bypassed for F6.
- An operator may explicitly select a **current, Origin-validated, authorized employer-origin job** as a review-drafting target even when it is not Top-5.
- An operator-selected target carries `authority_source=operator_selected_current_job` and **no Product rank**.
- An unknown hard-filter state remains unknown; drafting does not convert it to passed.
- A known hard-filter failure remains blocked from this path.
- Candidate claims still come only from approved Candidate Facts and exact current vacancy evidence.
- Exact F6 template/hash/zone authority, source-manifest binding, overflow fail-closed and outside-zone pixel identity remain unchanged.
- Drafting remains review-only: no application, submission, send or Product/ranking authority is created.

This boundary matches the real operator workflow: a recommendation system may honestly have an empty Top-5 while the operator can still decide to prepare material for a specific current vacancy.

### Installed 1.0.73 operator evidence

The operator-selected target boundary is now product-proven on installed 1.0.73. VALUNY Silver 613 can be opened from All jobs through **Prepare application** while Top-5 remains 0. The Application Workspace labels the target **Operator-selected current job**, shows Affinity rather than Product rank, binds employer-origin vacancy evidence, exposes 3 matched Candidate Facts and verifies both exact F6 templates.

The next operator feedback is a UX correction, not an authority change: the zone-by-zone insertion surface is too granular for the normal workflow. The desired terminal state is **one finished application document**, not manual assembly across many template fields.

Candidate target: **1.0.74** on `feature/f6-c-single-finished-pdf`.

The main F6-C path therefore becomes:

`grounded review draft -> internal deterministic mapping to allowed zones -> exact-template render + pixel proof -> combine letter + CV -> one finished local PDF -> human review`

The individual zone editor remains available only under an Advanced disclosure for targeted corrections. It is no longer the primary operator step.

The same installed operator review exposed a small lifecycle UX defect: a Silver job already linked to an application in `applied`, `reply`, `interview`, `offer` or `closed` still showed **Prepare application**. The 1.0.74 candidate removes preparation from every normal UI surface once the shared F5 effective stage has progressed beyond `prepared`. The existing lifecycle status remains visible and links to **Applications** instead. `prepared` itself remains eligible because it is not submission authority.

The combined PDF is packaging only. Each component first passes the accepted Slice-B renderer; the package then concatenates application letter followed by CV and raster-hash compares every combined page against its rendered source page. Any visual drift fails closed. No new layout, text, ranking, application, submission or send authority is created.

### Installed 1.0.74 operator evidence

Installed 1.0.74 on exact source `1db8ef0f1708dff7684a21c632086abdf36344fb` confirms the lifecycle suppression works: jobs already at **Beworben** / **Interview** no longer expose **Prepare application** and retain **Open Applications**.

The same operator session exposed two remaining navigation/UX defects:

1. clicking **Prepare application** on a specific All-jobs row can open the Application Workspace on a different job;
2. the workspace shows the full selectable-job population as a permanently visible sidebar, which is too long and distracts from the explicitly selected application target.

The first defect is caused by competing open-path authority plus silent fallback behavior. The legacy `ApplicationWorkspaceEventBridge` synthetic-click path still coexisted with the direct target event, and the workspace could substitute `applicationJobs[0]` when the requested target was not in its narrower local list.

Candidate target: **1.0.75** on `fix/f6-c-exact-target-compact-picker`.

1.0.75 changes the interaction contract:

- the exact Silver ID selected in All jobs is the target that opens; the workspace may not silently substitute another job;
- a current non-hard-filter-failed target may open even if Origin evidence is incomplete, so the **same selected job** can show its own fail-closed blocker rather than redirecting elsewhere;
- the obsolete hidden launcher + synthetic click bridge is physically removed; the workspace is the single owner of `product-v1:open-application-workspace`;
- the permanent current-jobs sidebar is removed;
- the selected job is pinned as the primary workspace context;
- **Change job** is explicit and opens a compact searchable chooser, capped to the 10 highest-Affinity jobs until the operator searches;
- already-applied/downstream jobs remain excluded from preparation by the accepted 1.0.74 lifecycle invariant.

### Installed 1.0.77 exact-target diagnostic

Installed 1.0.77 preserves the operator-selected target and uses Product V1 application branding. For accompio Silver #626 it exposed the previously opaque runtime error as:

`DownstreamPreviewStop: preview detail returned HTTP 404`.

A verified read-only RCC diagnostic then proved this is a redundant-network-path defect, not missing vacancy evidence or a guessed replacement URL:

- Silver #626 source is `generic_origin:accompio`;
- Silver source URL, latest recurring observation source URL and nested normalized job source URL are exactly the same;
- lifecycle remains `active_confirmed`;
- the latest exact observation was recorded on 2026-09-22 and contains a normalized job description;
- the existing exact-observation contract reconstructs 3,994 characters of source-grounded vacancy evidence;
- `TARGET_626_EXACT_OBSERVATION_REUSE=PASS`;
- database writes remained zero.

Assessment materialization already reused this exact persisted evidence before network fallback. The Application Workspace did not: it performed a redundant detail HTTP GET unconditionally, allowing an external HTTP 404 to hide evidence JAP already held.

Candidate target: **1.0.78** on `fix/f6-origin-drift-recovery`.

1.0.78 makes the evidence boundary singular:

- exact URL-bound current observation evidence is projected by one shared read-only helper;
- both assessment materialization and Application Workspace consume that helper;
- reuse is admitted only when Silver source URL == observation source URL == normalized nested job source URL and a persisted description exists;
- exact persisted evidence performs **zero** detail HTTP GETs;
- network detail fetch remains a bounded fallback only when exact persisted evidence is unavailable;
- no alternate URL is guessed and no third-party/search evidence becomes Product authority;
- no lifecycle, Origin, Fit, ranking, application, submission or send authority is widened.

### Installed 1.0.78 explicit-Origin blocker diagnostic

The installed 1.0.78 operator retest keeps accompio Silver #626 pinned and no longer fails on the redundant detail HTTP 404. The next failure is:

`origin_validation_status is required`.

This is a context-construction defect, not permission to infer Origin validation. `gold_product_v1_job_readiness` deliberately exposes `origin_validation_status=NULL` while a current job has no materialized Product assessment and labels that state `assessment_required`. The 1.0.75 interaction contract already requires such an explicitly selected job to stay open and show its own fail-closed blocker rather than aborting or redirecting.

Candidate target: **1.0.79** on `fix/f6-explicit-origin-blocker`.

1.0.79 therefore normalizes a missing Origin field to `unknown` **only for the operator-selected drafting projection**. The canonical context then produces `origin_not_validated`, keeps generation blocked and preserves the exact target. A Top-5 target with a missing Origin field still fails construction. No assessment is inserted, no Origin status becomes validated, and no Product/ranking/application/submission/send authority changes.

### Installed 1.0.79 operator acceptance + read-only materialization proof

The installed operator test passes the intended 1.0.79 boundary:

- the exact accompio Silver #626 target remains pinned;
- the former low-level missing-field exception is gone;
- the workspace renders **Context blocked / origin not validated**;
- 2 Candidate Facts are matched and both F6 templates retain exact authority;
- draft generation remains disabled while Origin authority is absent.

A fresh RCC read-only plan then evaluated exactly Silver #626 through the existing resilient initial-assessment materializer. It produced one proposal and zero blockers with materialization fingerprint `78d9d24f1ecfc25488c47c77e0585d54a62c0b2729b6fb417dd403be57333e19`. The plan reused the exact persisted observation once, performed zero vacancy-detail network reads, zero DB writes and zero provider/LLM requests, and created no ranking score, capability-fit or Top-5 authority.

That proof also found a stale pre-F4B coupling in the materializer. The approved ranking policy is now `product-v1-2026-09-16-affinity-v1`; the approved job-evidence/hard-filter policy remains `product-v1-2026-08-02`. Newer F4A code already treats those as independent authorities and binds assessment `policy_version` to job-evidence semantics while recording ranking-policy version separately.

Candidate target: **1.0.80**.

1.0.80 brings the initial materializer onto that same contract: both approved policy versions are required and independently frozen across preflight/apply; the assessment row binds the hard-filter/job-evidence policy version; ranking-policy identity is recorded separately in evidence metadata; equality between the two versions is no longer required. This is an authority-correction, not a relaxation.

### Approved initial assessment + post-write F6 readiness proof

The operator explicitly approved the single Silver #626 initial-assessment insert. Run `36002073813` executed against exact main `71d6800d61251d70db8f7cd757fd4236e282be94` only after recomputing the frozen materialization fingerprint `78d9d24f1ecfc25488c47c77e0585d54a62c0b2729b6fb417dd403be57333e19`.

Post-write proof is deliberately narrow:

- exactly 1 assessment inserted, 0 pre-existing/conflicting rows;
- Origin = `validated`;
- activity = `active`;
- hard filter = `unknown`;
- capability fit = `unknown`;
- readiness = `hard_filter_evidence_required`;
- all direct ranking-score fields remain null;
- provider requests = 0;
- ranking scores created = 0;
- Top-5 forced = 0;
- application/submission/send authority remains absent.

A subsequent read-only live probe using the canonical private-document root proves the same Silver #626 now yields Application Workspace `READY`, blocked reasons `[]`, 2 grounded claim-plan entries, exact observation reuse with zero detail HTTP GETs, and F6 template authority `ready`. With the provider explicitly disabled, the canonical draft path reaches `draft_for_review` in `deterministic_evidence_first` mode with provider requests 0 and all DB/application/submission/send writes 0.

### F6 design mandate — preserve layout maximally, change only what is necessary

The approved private CV and application-letter PDFs remain the visual authority. The product goal is not to redesign them per vacancy. The rule is:

> **Preserve the base layout as completely as possible; adapt only as much content as the concrete vacancy actually requires.**

Operational consequences:

- Codex may return **text values only**; it receives no layout coordinates and no layout mutation authority.
- Existing pages, geometry, photograph, graphics, lines, section placement and non-editable typography remain untouched.
- CV career-history blocks are factual authority and must not be rewritten merely for stylistic variation.
- Primary CV adaptation is limited to the already-declared short-profile / competency zones unless a later operator-approved template contract explicitly adds more.
- Application-letter recipient, date, subject, salutation and body zones may change because they are vacancy-specific.
- Text overflow fails closed. JAP must never solve overflow by moving graphics, resizing the page, manufacturing a different design or silently adding a page.
- The existing renderer proof remains mandatory: **zero changed pixels outside declared editable zones**.

This is the design rule for the whole Codex adaptation path, not only the accompio test case.

### JAP Classic 1.1.0 boundary

The operator chose this point to start the **1.1.x** minor line because the status/readiness path is now usable as an operator feature: job identity stays pinned, failure reasons are explicit, authority transitions are visible, and the workspace can move from blocked state to review-draft readiness without manufacturing ranking authority. Existing 1.0.x releases remain immutable; the next release is **1.1.0**.

### Slice-C rendering contract

- Control Center loads the two exact locally installed private templates and exposes only their manifest-declared text zones;
- source text from each declared zone is visible as the editable baseline; no undeclared page area is editable;
- explicit operator action may apply bounded draft suggestions: CV summary -> `p1.short_profile`; letter opening/fit/closing -> declared letter body zones;
- the operator can edit those zone texts before rendering;
- export is bound to the exact draft `source_manifest_sha256`; if the current job/fact/template context drifts, export fails closed and requires draft regeneration;
- final rendering delegates to the accepted Slice-B renderer, including overflow fail-closed and outside-zone pixel-identity proof;
- unchanged documents may be exported as their exact source-template bytes; changed documents carry renderer evidence and output SHA-256;
- rendered PDFs cross only the loopback Product boundary as base64 and become local browser/WebView PDF objects for explicit Open/Download actions; no public/cloud persistence is introduced;
- human review remains mandatory and no automatic submit/send authority exists.

### Next operator gate

After exact-head CI and immutable **1.1.0** release:

1. update through the integrated JAP updater and verify version 1.1.0;
2. re-open accompio Silver #626 through **Prepare application**;
3. require the same job to remain pinned and the workspace to be generation-ready;
4. require Origin validated while hard filter remains explicitly unknown;
5. require 2 grounded Candidate Fact claim entries and 2/2 exact F6 template authority;
6. require **Generate review text** to be enabled;
7. trigger it once and review the operator-visible draft. The draft may be edited/reviewed but still carries no automatic submit/send authority.

If the review text is accepted, the next gate is **Create finished application PDF** under the existing exact-template, source-manifest, overflow and outside-zone pixel-identity contract.

### Release-line gate

JAP Classic stays on the **1.1.x** line until the complete automatic CV + application-letter preparation path is operator accepted.

Until then, every correction discovered during real F6 qualification is a patch release only (`1.1.1`, `1.1.2`, ...), including:

- Codex installation/authentication/runtime bridging;
- included-allowance / paid-credit exhaustion handling;
- stale recipient/contact leakage;
- vacancy-specific content quality;
- CV adaptation scope;
- template-zone mapping;
- overflow handling;
- PDF render/layout-preservation regressions.

**1.2.0 is reserved** for the operator-accepted capability boundary where one explicitly selected vacancy can produce both a vacancy-adapted CV and a vacancy-specific application letter automatically, while preserving the approved base layout as completely as possible and changing only as much content as necessary.

1.2.0 acceptance therefore requires all of the following at once:

1. correct current-job identity and Employer-Origin evidence;
2. no stale employer/contact/application-letter content;
3. high-quality vacancy-specific CV adaptation;
4. high-quality vacancy-specific application-letter text;
5. automatic mapping into only manifest-authorized text zones;
6. exact source-template page/geometry authority retained;
7. overflow fail-closed and outside-zone pixel identity proven;
8. explicit human review before export;
9. graceful `draft_unavailable` when Codex allowance/credits/authentication are unavailable, with no low-quality prose fallback;
10. zero automatic submission/send authority.

Passing only the text-generation step does not authorize 1.2.0; the finished rendered document pair must pass the operator gate.

### Installed 1.1.0 Codex runtime boundary / candidate 1.1.1

The first installed 1.1.0 operator run reaches a fully ready accompio Silver #626 context but fails before any model request with:

`Codex CLI is not available to the JAP runtime.`

That result is accepted as a clean runtime-delivery finding. It does not authorize restoring deterministic prose and does not change the 1.2.0 acceptance boundary.

Candidate **1.1.1** fixes only this runtime layer:

- the product release build downloads one official OpenAI Codex CLI Linux x64 archive at build time only;
- version is pinned to `0.154.0` and the upstream archive SHA-256 is frozen in release authority;
- the extracted Codex binary and a JAP-owned identity manifest are included in the immutable runtime ZIP;
- update staging, cutover verification and bootstrap all require the bundled binary/manifest before accepting the runtime;
- installed startup verifies the binary SHA-256, restores its executable bit and binds `JAP_CODEX_EXECUTABLE` directly to the immutable runtime path;
- normal installed startup does not npm-install, curl, wget, self-update or otherwise provision Codex from the network;
- F6 launches Codex with a minimal allow-listed environment so PostgreSQL, GitHub and API credentials from JAP are not inherited;
- `codex login status` is checked before drafting. Missing account authentication is an explicit product state, not a generic HTTP error;
- no API-key fallback or automatic credit purchase is permitted;
- exhausted allowance/eligible credits remains `draft_unavailable` with no low-quality fallback prose.

The planned accompio #626 drafting gate is superseded because the vacancy disappeared from the employer surface before content qualification completed. This exposed a lifecycle-serving defect: older `active_confirmed` evidence could remain operator-selectable even after it was no longer fresh enough to support a Product action.

### Candidate 1.1.2 — fresh-vacancy action authority

JAP already had a deterministic `product_v1_demo_live_scope` contract with a 30-minute maximum health-evidence age, but it was audit-only. Candidate **1.1.2** makes that contract executable Product authority:

- Control Center projects origin truth first and then live-scope freshness for every job-readiness and Top-5 row;
- `demo_live_verified=true` is required for anything presented as a **current** Product action;
- stale active evidence becomes an explicit `live_health_refresh_required` projection rather than silently remaining current;
- Overview current counts, Top-5 actions, the Application target and the Application Workspace selector all require fresh live truth;
- the F6 backend independently rechecks the same freshness contract before persisted vacancy-detail reuse, so a stale row cannot bypass the UI through a direct API call;
- the existing exact-observation reuse contract remains intact after freshness passes, so 1.1.2 does not restore redundant detail GETs merely to obtain drafting text;
- freshness expiry alone does not write `inactive_confirmed`. It removes Product action authority; authoritative closure still requires exact-detail closure evidence or verified complete-inventory absence.

The next operator gate is therefore two-part:

1. after installing 1.1.2, the expired accompio #626 vacancy must no longer be selectable/current for F6;
2. choose another genuinely current Employer-Origin vacancy and continue the first real Codex-adapted CV + application-letter review test there.

This remains a **1.1.x patch correction**. It does not satisfy or advance the 1.2.0 acceptance gate by itself.

### Candidate 1.1.3 — restore 1.0.79 application-navigation affordances

Installed 1.1.2 correctly removed stale-vacancy action authority, but it accidentally coupled that authority to **button visibility**. As soon as the 30-minute live-health evidence expired, All jobs no longer showed the application-navigation controls that were product-proven in 1.0.79.

That is a regression. Freshness decides whether F6 may continue, not whether the operator may navigate to the authoritative F6 state.

Candidate **1.1.3** restores the 1.0.79 job-detail action surface:

- **Open original ↗** remains available whenever an exact browser-safe source URL exists;
- **Prepare application** remains visible for persisted `active_confirmed`, non-hard-filter-failed jobs whose F5 stage has not progressed beyond `prepared`;
- **Open Applications** remains visible for jobs already linked to an F5 application;
- the Application Workspace target chooser again accepts persisted-active jobs so the job selected in All jobs remains the job inspected in F6;
- freshness is still enforced independently by the backend before current vacancy evidence may become drafting authority;
- stale jobs therefore reach a visible `current vacancy freshness required` blocker instead of silently losing all navigation controls.

This explicitly freezes the 1.0.79 application-navigation UX as a regression contract while retaining the newer lifecycle truth boundary.

### Candidate 1.1.4 — exact live vacancy revalidation, no invented 30-minute cadence

The next operator run showed that 1.1.3 restored the buttons but the Product truth surface itself was still inconsistent: All jobs contained the persisted current cohort while the sidebar and `Current` filter rendered zero, and a genuinely interesting replacement target failed F6 only because its last health timestamp was older than 30 minutes.

That exposed the actual authority mistake. `product_v1_demo_live_scope` was created as a bounded demo/audit freshness helper. F4C later made the stronger rule explicit: recurring-ingestion eligibility is **not cadence authority**, and a successful historical run without an explicit cadence must not be labeled stale merely because a fixed wall-clock interval elapsed.

Candidate **1.1.4** therefore changes the boundary rather than tuning the number:

- All jobs/current counts return to persisted evidence-driven lifecycle truth (`active_confirmed`);
- the 30-minute demo-live helper is removed from the served Product action projection;
- F6 does not trust age alone. When the operator explicitly chooses **Prepare application**, JAP probes exactly that Silver job's employer-origin URL once;
- exact URL + expected title => current vacancy confirmed; no lifecycle write is needed and the already-bound persisted vacancy observation remains the drafting-detail source;
- explicit vacancy-unavailable content => append one lifecycle-health `closed/exact_detail` observation, block drafting, and refresh Product truth so the dead job leaves the current cohort;
- unverifiable transport/content outcomes => no write and fail closed;
- generic 404 remains non-authoritative unless source-specific/explicit closure content proves the vacancy itself is gone;
- Accompio's exact message `Die Stellenanzeige konnte nicht gefunden werden` is accepted as explicit vacancy-unavailable evidence.

This restores coherent counts and prevents a dead job from remaining current after it is actually revalidated, without inventing cadence policy or weakening lifecycle evidence requirements.

A mismatch between persisted observation URL and Silver URL, missing persisted description, known hard-filter failure, source/context drift, overflow, unexpected layout change or missing pixel proof remains fail-closed.

### Candidate 1.1.5 — converge selected-job lifecycle truth and expose real Codex authority

Installed 1.1.4 proves the correct exact-revalidation boundary but still hides two operational truths.

First, the dead Accompio #626 row remains visible until the operator enters F6. Candidate 1.1.5 moves the same bounded exact-detail revalidation to the **selected All-jobs detail**. Selection itself may not manufacture activity or closure: active and unverifiable probes are read-only; only an authoritative exact closure appends one lifecycle-health observation and then refreshes Product truth. This lets dead rows leave Current authority as soon as the operator inspects them, while historical/audit truth remains available according to the Product read model.

Second, the presence of a bundled Codex binary is not equivalent to the operator's ChatGPT account being connected. Candidate 1.1.5 therefore exposes a read-only Codex status endpoint and renders the result both in About and in the F6 readiness card:

- bundled executable present / version;
- ChatGPT authentication connected vs sign-in required;
- selected drafting model;
- usage authority = ChatGPT included allowance / eligible Codex credits;
- API-key fallback disabled;
- automatic credit purchase disabled.

JAP accepts only the official CLI status **Logged in using ChatGPT** as F6 drafting authority. API-key, workload-identity or access-token auth is visible diagnostically but does not enable drafting. If ChatGPT auth is missing, **Generate review text** remains disabled before any model request. There is still no deterministic filler fallback.

1.1.5 also fixes the job-count UX exposed by the same operator run: the full inventory is labeled **All jobs**, Current stays a distinct lifecycle filter, and the sidebar All-jobs badge reflects the inventory rather than an unrelated current count.

The updater is hardened in the same patch after a real first-attempt rollback on `desktop-host` access denial: transient access/sharing failures receive a bounded 45-second cutover retry, and a failed exact target receives a 10-minute retry cooldown instead of being offered again roughly 30 seconds after rollback. Superseding releases are not blocked by that cooldown.

The 1.2.0 acceptance boundary is unchanged. 1.1.5 only makes lifecycle truth, Codex authority and updater recovery observable/stable enough to continue the real CV + letter qualification.


## Explicit non-goals

- no alternate template chooser;
- no free-form layout generation;
- no DOCX as template authority;
- no automatic page reflow;
- no automatic application submit;
- no automatic email send;
- no silent replacement of the canonical templates.
