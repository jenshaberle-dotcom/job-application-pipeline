# JAP Current Re-Entry

Status: canonical current re-entry projection + Freeze-II sequencing authority

## CURRENT ACTIVE CAMPAIGN — FREEZE II / S0 COMPLETE / S1 CONNECTOR SATURATION ACTIVE

This section supersedes older F5/updater sequencing statements retained below as historical incident evidence.

- **Freeze II — Source Truth & Connector Reliability is ACTIVE.** Canonical issue: #1038. Canonical plan: `docs/planning/active/FREEZE-II-SOURCE-TRUTH-CONNECTOR-RELIABILITY.md`. The active sequence is `S0 COMPLETE -> S1 connector saturation across every current candidate -> S2 systematic real-search/source-family evidence -> S3 metadata extraction -> S4 Bronze/Silver/Product integrity -> S5 requirement/skill semantics -> S6 cross-family acceptance`.
- **S0 is COMPLETE on exact main `fe7758d2fb7dbed4586fdc55af69969ad37f7547`, run `36187566852` SUCCESS.** Current measurement: 67 connector candidates; V6 diagnostic recipe-ready 23; first failures Origin 16 / Origin reachability 1 / Inventory 6 / Detail 13 / Proof 8. The Product metadata cohort has 75 reachable rows with 0 extractor-gap, 0 Silver->Product/CC projection loss and 0 violating rows; 16 skill-recall-risk rows remain. Historical #676 counts such as `36/65` remain predecessor evidence only and are not substituted for current Product coverage.
- **Freeze-II primary priority is now connector saturation, explicitly operator-steered.** Every current Employer-Origin candidate belongs in the S1 denominator because candidacy already records prior relevant-employer/job evidence. Each candidate must resolve to the canonical `generic_origin:<company_key>` connector family, pass one isolated non-persistent synthetic smoke-job contract, and then receive a bounded real source/search attempt. Synthetic smoke proves connector operability only; it is never Product/source/job authority.
- **S1 is denominator-driven, not cohort-driven.** Initial S0 denominator is 67 candidates. Target is 67/67 connector smoke PASS, followed by 67/67 real-source execution attempts ending explicitly in `real_jobs_observed`, `real_zero_yield`, or a named source blocker. The residual classifier remains useful supporting diagnostics for shared mechanics but no longer owns sequencing and may not narrow work to only a small high-lift subset.
- **Carried work:** #789 + CR-F1-001 enter S1; #676 supplies reusable deterministic builder architecture; F4A-R2/R3/R7 supply extraction/provenance baselines; #891 is gated behind S0-S4; #910 contributes only its Data-Layers truth-audit component during this campaign; #917/#922 remain bounded secondary inputs/backlog rather than source authority.
- **S1 search rule:** company-grounded vocabulary first, then canonical target raster for breadth. A current zero-yield does not invalidate a candidate; it records that no matching vacancy is currently observable. Real Employer-Origin jobs may proceed toward normal Bronze/Silver only under existing strict evidence gates. Metadata hardening becomes the next primary wave after this broader job population exists.

- **Current Product freeze campaign is COMPLETE / OPERATOR ACCEPTED for the available real-job cohort.** F0, F1, F2, F3, F4A, F4B, F4C, F5 and F6 have each crossed their Product/operator gate at least once through the normal bounded pipeline. F6 Slice C is accepted as good enough for the present cohort after multiple real non-Eraneos jobs exercised vacancy-specific drafting, exact-template preflight and export. No further 1.1.x polishing is authorized merely from known-cohort repetition; new F6 work requires reproducible evidence from broader connector/job coverage.
- **Next active product-learning phase is Connector Expansion / acquisition breadth**, centered on #789 plus carried residual CR-F1-001. The purpose is to produce more diverse Employer-Origin material, not to reopen the completed freeze by default.
- **Carried into the next freeze campaign:** #891 / F4B-FOLLOWUP-001 (generic skill extraction -> capability auto-fit -> numeric Fit/Combined calibration) only after the broader real cohort exists. Post-freeze UX/data items #910, #917 and #922 remain separate and do not retroactively block this freeze closure.
- **Updater incident #1035 remains an operational hardening canary, not a Product-freeze blocker.** 1.1.19 is installed and normal repeated external start behavior is operator-proven stable. The stricter adversarial case of repeated external starts specifically during a future live update handoff remains useful closure evidence for #1035, but does not reopen F0-F6 product acceptance.

- **1.1.18 updater hardening is superseded / insufficient:** it fixed Stage-vs-Stage overlap only. The subsequent real 1.1.18 cutover was disturbed by repeated external desktop starts. The target live trees were already verified, but an unauthorized desktop start entered the runtime path during the cutover window; restart verification then failed. Rollback restored the runtime first and subsequently failed deleting the target desktop tree because a loaded framework DLL remained locked, leaving `current.json=1.1.18` while the live runtime identity was 1.1.17. Issue #1035 reopens the updater slice.
- **1.1.19 updater recovery hardening candidate:** JAP itself now owns this failure boundary regardless of external launcher behavior. Stage and Apply share one installation-scoped update-operation mutex; consent creates an atomic handoff marker with a random token; normal desktop starts are rejected before any Runtime access while that handoff is active; only the token-bearing Applier restart may pass. Future staging uses the exact target desktop tree as the isolated apply helper so the target generation's Applier fixes apply to subsequent cutovers. Rollback stops exact live-host peers, retries transient directory deletion as well as moves, restores desktop/runtime independently, restores `current.json` only after both previous live identities verify, and retains the handoff fail-closed if coherent recovery cannot be proven. No external demo/watchdog implementation is part of this Product fix.

- canonical installed/released Product baseline: desktop **1.1.19**, source `f6a39173a9e75d7998e822312b7c9bc784ef3e5f`; operator recovery from the failed 1.1.18 cutover is complete and normal repeated external-start behavior is stable;
- integrated CGKB product-local updater remains accepted and routine;
- F5 is **operator accepted / COMPLETE**; current application linkage is shared with the All-jobs surface and remains separate from ranking authority;
- F6 Slices A and B are **operator accepted / COMPLETE**;
- 1.0.75 carries exact Silver-target preservation, no silent first-job fallback, a single workspace open-event owner and compact searchable **Change job** selection;
- 1.0.76 hardens the Windows single-instance/update handoff;
- installed 1.0.77 proves the Product V1 Application identity and exposes runtime error detail; exact accompio Silver #626 now fails transparently as `DownstreamPreviewStop: preview detail returned HTTP 404`;
- a verified read-only RCC diagnostic proved Silver #626 already has current exact URL-bound recurring Employer-Origin observation evidence for the same persisted source URL/title, including a 3,994-character normalized vacancy detail; DB writes remained zero;
- installed 1.0.78 proves the exact-observation reuse correction: accompio Silver #626 remains pinned and advances past the redundant HTTP-404, but the next boundary currently aborts too early as `origin_validation_status is required` while the canonical readiness row legitimately carries no assessment-origin state yet;
- installed 1.0.79 is operator-proven: accompio Silver #626 stays pinned, exact persisted vacancy evidence remains available, 2 Candidate Facts match, both F6 templates retain exact authority, and the workspace now stops truthfully at `origin_not_validated` instead of a low-level missing-field exception;
- a fresh read-only RCC plan for exactly Silver #626 proves one admissible initial assessment proposal with fingerprint `78d9d24f1ecfc25488c47c77e0585d54a62c0b2729b6fb417dd403be57333e19`, exact observation reuse `1`, detail-network reads `0`, DB writes `0`, provider/LLM requests `0`, ranking scores `0`, capability-fit authority `0` and Top-5 forcing `0`;
- that proof exposed stale policy coupling in the legacy materializer: ranking policy is now `product-v1-2026-09-16-affinity-v1` while job-evidence/hard-filter policy remains `product-v1-2026-08-02`; current F4A authority already versions those independently, so the F6 materializer must do the same rather than require equality;
- installed **1.0.80** carries the independent ranking/job-evidence policy contract; the integrated updater delivered it successfully to the operator;
- operator-approved F6 mutation run `36002073813` on exact source `71d6800d61251d70db8f7cd757fd4236e282be94` recomputed the frozen Silver #626 fingerprint unchanged, inserted exactly one initial assessment and post-write proved `origin_validation_status=validated`, `activity_status=active`, `hard_filter_status=unknown`, `capability_fit_status=unknown`, `product_readiness_status=hard_filter_evidence_required`, provider requests `0`, ranking scores `0` and Top-5 forcing `0`;
- a fresh post-write read-only RCC proof on the **1.1.0** candidate now returns Application Workspace `READY` for the same Silver #626 with blocked reasons `[]`, 2 grounded claim-plan entries, exact observation reuse `1`, zero detail HTTP GETs and exact F6 template authority `ready`; a provider-disabled generation probe reaches `draft_for_review` deterministically with provider requests `0` and writes `0`;
- current candidate is **1.1.0**. This intentionally starts the next minor line because the operator-visible status/readiness path has matured into a stable usable feature boundary rather than another patch-only correction;
- 1.1.0 drafting authority is now intentionally split: deterministic JAP owns exact job/Candidate-Fact/template truth and rendering; embedded **Codex** owns only vacancy-specific CV/letter text adaptation under a strict JSON schema, read-only sandbox and human-review boundary;
- design mandate: preserve the approved CV/application-letter layout **maximally** and change content only as much as the concrete vacancy requires. Codex receives no layout coordinates or layout mutation authority; renderer overflow fails closed and outside-zone pixel identity remains mandatory;
- stale application-letter content is never supplied to Codex. Recipient/date/subject/salutation/body are rebuilt from current target authority, while CV adaptation is restricted to the declared short-profile and competency zones;
- if Codex is not installed/authenticated, times out, fails validation, or reports exhausted allowance/credits, F6 returns an explicit `draft_unavailable` state and generates **no low-quality deterministic fallback prose**; application/submission/send authority remains zero;
- release-line authority: remain on **1.1.x patch releases** while embedded-Codex CV/letter creation is still under operator qualification; bugfixes, runtime/auth/capacity handling, content-quality corrections and renderer/layout-preservation fixes increment only the patch component;
- **1.2.0 is reserved for operator acceptance of the complete automatic document-preparation capability**: vacancy-specific CV adaptation + vacancy-specific application-letter creation + stale-recipient elimination + exact-template/layout preservation + overflow/outside-zone proof + graceful Codex-capacity failure, all review-first and with zero automatic submission/send authority;
- installed **1.1.0** reached the intended next fail-closed boundary on accompio Silver #626: the factual/template context is fully ready, but generation reports `Codex CLI is not available to the JAP runtime`; this is a runtime-delivery defect, not a drafting/content fallback;
- installed **1.1.1** ships one checksum-pinned official Codex CLI `0.154.0` Linux x64 binary inside the immutable JAP runtime bundle, validates its identity before startup/cutover, and exposes it to F6 through `JAP_CODEX_EXECUTABLE`; installed runtime performs no Codex download/install/update;
- Codex receives a sanitized subprocess environment rather than JAP secrets. It preflights `codex login status`; missing ChatGPT authentication becomes explicit `codex_auth_required`, exhausted included allowance/eligible credits becomes `codex_capacity_unavailable`, and neither state generates deterministic filler prose;
- the next operator observation exposed a separate Product lifecycle defect: accompio Silver #626 had disappeared from the employer site while JAP still projected its older `active_confirmed` truth as current/selectable. The existing 30-minute `product_v1_demo_live_scope` freshness contract existed only as an audit and was not wired into the served Product surface;
- current candidate **1.1.2** wires that existing freshness authority into `job_readiness`/Top-5 operator projection and F6 server-side preparation. An old `active_confirmed` label is no longer enough: Product actions require `demo_live_verified=true`, otherwise the row is visibly `live_health_refresh_required` (or the corresponding freshness reason) and cannot enter F6;
- this does **not** invent `inactive_confirmed` from age alone. Persisted lifecycle truth remains evidence-driven; stale/expired freshness removes action authority immediately, while exact-detail/complete-inventory evidence remains responsible for authoritative inactive classification;
- installed 1.1.2 exposed a UI regression caused by wiring freshness into navigation visibility: the **1.0.79-era job-detail action surface** (`Open original`, `Prepare application`, and linked `Open Applications`) disappeared whenever live-health freshness expired, even though the job remained auditable and operator-selectable in All jobs;
- current candidate **1.1.3** separates **navigation affordance** from **mutation/action authority**: persisted `active_confirmed` jobs retain the 1.0.79 job-detail controls and can always navigate into the Application Workspace, while the F6 backend independently remains fail-closed on `evaluate_demo_live_scope` before any vacancy evidence reuse or drafting;
- no freshness rule is removed by 1.1.3. The UI no longer hides the route to the authoritative blocker; stale jobs can be inspected/selected, but cannot produce a draft until the backend freshness contract passes;
- installed 1.1.3 then exposed the deeper design error behind the `Current 0` display and universal `live_health_refresh_required` blockers: the 30-minute `product_v1_demo_live_scope` helper was an audit/demo freshness heuristic, while F4C explicitly states that recurring eligibility without explicit cadence authority must remain `cadence_unknown`; using a fixed 30-minute wall-clock age as Product action authority was therefore incorrect;
- installed **1.1.4** removes that arbitrary age from the served Product surface and restores persisted evidence-driven `active_confirmed` lifecycle truth for All jobs/current counts. F6 performs one operator-triggered **exact live vacancy revalidation** on the selected job instead;
- successful exact live validation is read-only and the already persisted exact observation remains the drafting-detail source (no redundant second detail fetch). Explicit closure is different: a narrow exact-detail closure signal writes one append-only lifecycle-health observation so Gold converges to `inactive_confirmed`, then the Control Center refreshes Product truth immediately;
- the Accompio closure page text `Die Stellenanzeige konnte nicht gefunden werden` is now an explicit vacancy-closure marker. Network failures, title mismatches, generic 404s and other unverifiable outcomes still perform no lifecycle write and fail F6 closed;
- installed 1.1.4 exposed two remaining operator-visible gaps: the dead Accompio row does not converge until F6 is explicitly opened, and the UI does not prove whether bundled Codex is merely present or actually authenticated with the operator's ChatGPT account;
- candidate **1.1.5** exact-revalidates the selected persisted-active job directly in the All-jobs detail surface; an authoritative closed result appends lifecycle truth and immediately refreshes Product truth, while active/unverifiable checks remain non-mutating;
- 1.1.5 restores **All jobs** to its canonical current Employer-Origin review scope and removes the redundant/broken secondary Current filter; the sidebar badge and list count now derive from the same already-current `job_readiness` projection, so a closed vacancy disappears from this surface after lifecycle convergence;
- bundled Codex remains checksum-pinned in the immutable runtime, but 1.1.5 now exposes its runtime/version/auth state in About and F6 before drafting. JAP accepts only `codex login status = Logged in using ChatGPT`; an API-key/workload/access-token login is deliberately not drafting authority, so included ChatGPT allowance / eligible Codex credits are not silently replaced by API billing;
- the observed updater first-attempt `Access to ... desktop-host is denied` rollback is treated as a separate 1.1.5 usability defect: cutover retries transient access/sharing failures for 45 seconds, and a failed target is suppressed for 10 minutes so the old installation can recover without another prompt roughly 30 seconds later; a newer target remains immediately admissible;
- installed 1.1.5 is operator-proven on both new observability paths: dead Accompio #626 disappears after exact closure convergence + refresh, and About shows bundled `codex-cli 0.154.0` with model `gpt-5.6-sol`, usage authority `ChatGPT allowance / eligible credits`, API-key fallback disabled and current state `ChatGPT auth = Sign-in required`;
- the same 1.1.5 operator run exposes a second independent F6 authority mismatch on live **Eraneos Silver #511 — Data Engineer (all genders)**: live vacancy evidence, 3 Candidate Facts and both exact templates are present, but the context still reports `employer_origin_required`. Root cause: F6's source-role helper recognizes only the post-migration `generic_origin` registry family, while the already-reviewed legacy `personio:eraneos` recurring feed authority is proven through the stricter `personio-recurring-feed-authority.v1` + reviewed-binding observation contract used by lifecycle migration 099;
- candidate **1.1.6** composes that existing reviewed Personio authority into the F6 Employer-Origin gate without creating a generic Personio allowlist: exact Silver/observation URL binding, reviewed target binding, verified recurring feed contract, employer identity, complete inventory and authoritative lifecycle projection are all required;
- 1.1.6 also embeds the missing **operator login action**. F6 can start the official bundled Codex CLI with `codex login --device-auth`, surfaces only the public verification URL + one-time code, polls until `codex login status` reports `Logged in using ChatGPT`, and never transports OAuth tokens through the browser/UI. Device auth is available even while another F6 blocker remains so authentication can be completed independently;
- installed **1.1.6 operator evidence** proves the device-code exchange itself succeeds end-to-end: `/codex-login` reports `completed`, `/codex-status` reports `status=ready`, `auth_mode=chatgpt`, `chatgpt_authenticated=true`, bundled `codex-cli 0.154.0`, model `gpt-5.6-sol`, API-key fallback disabled and ChatGPT allowance / eligible-credit billing authority;
- the same 1.1.6 run exposes a UI reconciliation race: after the backend reaches completed ChatGPT auth, the Application Workspace can remain on `ChatGPT sign-in required` because the polling effect invalidates its own nested status request when `codexLogin.status` changes to `completed`;
- the Eraneos #511 run also proves that 1.1.6 incorrectly couples reviewed Personio **source-origin authority** to the newest lifecycle-health projection. The explicit exact live vacancy revalidation legitimately advances lifecycle evidence to `exact_detail_url_and_title_confirmed` / `exact_detail`, which must not revoke the still-exact, reviewed `personio-recurring-feed-authority.v1` Employer-Origin binding;
- candidate **1.1.7** separates those authorities: reviewed Personio origin remains bound to its exact recurring-feed observation contract while `active_confirmed` remains mandatory, and completed device login reconciles Codex runtime status in an independent UI effect;
- installed **1.1.7** passes both prior blockers and reaches the first real Codex-adapted document draft for Eraneos #511. The UI exposes a complete CV adaptation and vacancy-specific application letter, audit reports bundled `gpt-5.6-sol / codex-cli 0.154.0`, exactly one Codex/provider request, and zero DB/submission/send writes;
- the first real final-PDF render then correctly fails closed on `p1.competency_profile`: `replacement text does not fit frozen F6 zone without scaling`. This is no longer an auth/Origin/context failure; the text generator produced content larger than the already-frozen template zone;
- candidate **1.1.8** binds Codex output to conservative frozen-layout text budgets before review: CV short profile <= 520 chars, competency profile <= 180 chars, exactly four application-letter paragraphs <= 240 chars each. The exact renderer still remains final authority; no font scaling, page growth, geometry mutation or layout relaxation is introduced;
- 1.1.8 also removes the contradictory review UX where a renderer error could coexist with `Application PDF is ready to build` and an enabled build button. A blocked render is labeled as text adjustment required; editing clears the stale error and permits a new exact render attempt;
- installed **1.1.8** proves that static character budgets alone are not sufficient layout authority: the regenerated Eraneos #511 draft advances past the former `p1.competency_profile` overflow but the final exact renderer now rejects `salutation`. The Advanced zone editor can recover manually, but that is explicitly not acceptable as the normal product path;
- root cause: drafting and exact-template geometry are still separated. Codex is constrained by approximate character budgets, while only the final export currently asks PyMuPDF whether the actual source-derived font, line height and frozen rectangle fit at scale 1.0;
- candidate **1.1.9** moves that exact fit proof into generation itself. Every Codex draft is preflighted read-only against the installed private PDFs using the same source style and no-scaling rule as final rendering. Overflowing qualified zones are fed back automatically to Codex, together with the previous overflowing text, for bounded compact repair; up to three total Codex attempts are allowed;
- a draft is returned to the operator only after exact-template preflight passes. If bounded repair cannot resolve the fit, JAP returns `draft_unavailable / f6_template_fit_unresolved` instead of pushing zone editing onto the operator or generating filler. Final export still reruns the full renderer and outside-zone pixel proof;
- the Advanced zone editor remains available only as an exceptional human override, not a normal dependency of automatic document preparation;
- installed **1.1.9** reaches the renderer-in-the-loop path but still returns `draft_unavailable / f6_template_fit_unresolved` on Eraneos #511 after the bounded automatic repair attempts. The Product UI does not yet expose the final overflow-zone list, so the operator cannot see which exact zone remained unresolved;
- code inspection identifies a structural repair-authority defect: every overflowing zone is currently routed back to Codex even though `recipient.block`, `date`, `subject` and `closing.formula` are generated deterministically by JAP and therefore cannot be changed by the Codex repair request. A salutation also does not need another model call when a verified neutral professional fallback can safely fit;
- candidate **1.1.10** separates those authorities. JAP performs safe local compaction for its own metadata zones (including neutral compact salutation, compact recipient, exact-title-only subject, compact date and closing variants), then re-runs exact-template preflight. Only CV profile/competency and letter body paragraphs may consume bounded Codex repair calls;
- Codex repair feedback now includes a progressive hard character target derived from the previous overflowing zone value (65% per repair step, never below the schema minimum), so semantic repair is forced to make measurable progress instead of merely receiving a generic “shorter” instruction;
- 1.1.10 also surfaces unresolved `layout_overflows` and already-applied automatic safe repairs in the Product UI/audit so any future fail-closed state is self-diagnosing without PowerShell. Manual zone editing remains exceptional only;
- installed **1.1.10** reaches a fully rendered Eraneos package, but operator review against the accepted Hornet benchmark rejects document quality as the remaining F6 slice gate: the Eraneos letter is materially more generic, contains malformed/truncated prose, uses a neutral salutation despite a grounded contact, and the CV preserves a stale footer date even though the new application date is current;
- candidate **1.1.11** changes the quality contract rather than the template geometry. Embedded Codex remains `gpt-5.6-sol` but is explicitly pinned to **high reasoning**. The model receives the **current CV + current application letter + exact vacancy + approved Candidate Facts** together. The current letter is style/structure/quality reference only: its employer, recipient, role, date, salutation and vacancy-specific claims are declared stale and have zero factual authority;
- 1.1.11 formalizes edit authority: all pixels outside declared zones plus portrait/signature/rules/geometry remain frozen; JAP owns recipient/date/subject and replaces those fields in-place; Codex may rewrite only the semantic CV profile/competency and letter text; career history/education/projects/skills remain preserve-by-default. The CV footer date becomes an explicit deterministic replacement, preventing the previous stale date while leaving the signature image untouched;
- quality constraints now allow 4-6 coherent body paragraphs (instead of forcing four miniature 240-character blocks), require complete finished paragraphs, and keep the exact renderer as final physical-fit authority. The normal AI path remains bounded and review-only;
- privacy is now an explicit Product choice. **Quality AI** discloses that CV + letter + vacancy are shared with ChatGPT Codex. **Local only** makes zero provider/LLM requests, preserves descriptive source wording and updates deterministic target/date fields locally; semantic editing remains local human work and uses the same final exact renderer;
- users without private source documents are no longer stranded: the Application surface can generate a provider-free **fillable Word starter** containing placeholders only. It carries no F6 pixel/template authority and can be completed manually;
- final exact PDF remains the canonical layout artifact. A second **editable DOCX companion** is generated locally from the same final F6 text-zone values. Word is explicitly non-pixel-authoritative and may reflow; it does not replace the verified PDF;
- installed **1.1.11** materially improves the Quality-AI text on Eraneos #511: the letter is now coherent, vacancy-specific and evidence-rich, and the CV adaptation is bounded. Local-only mode also proves the zero-LLM path and produces the local editable Word companion;
- the remaining 1.1.11 PDF failure is now isolated to renderer/preflight parity, not Codex quality: generation reports exact-template preflight pass, but final export rejects `p1.competency_profile`. Code inspection finds that preflight derives typography from the pristine source zone, while final rendering redacts the zone first and only then re-derives style. The redacted zone has no text left, so final rendering falls back to generic 9.5pt and can overflow text that correctly fit at the original source font size;
- candidate **1.1.12** makes preflight and final render use the same pristine source-derived style by capturing zone HTML/CSS before redaction. A dedicated regression test fails if final rendering ever asks for source style after the original zone text has been removed;
- 1.1.12 also adds honest live drafting telemetry. The blocking draft request receives a client request-id; the threaded local server exposes a separate progress endpoint with actual JAP phases, provider request number (bounded 1/3..3/3), workflow percentage and message. The UI polls it while Codex runs and displays **“Deine Bewerbungsunterlagen werden erstellt”**, model/reasoning, provider request counter and elapsed time. The UI explicitly states that the percentage is JAP workflow progress, not fabricated token-level model progress;
- installed **1.1.12** operator proof is now positive for the previously blocked final PDF path. Quality-AI telemetry visibly advances through verified phases (including provider request 1/3 and bounded repair 2/3), the final exact renderer completes, and the generated Eraneos package is the intended 3-page structure: one letter plus two CV pages;
- direct visual comparison against the accepted Hornet source PDFs shows the PDF template contract now holds: header/portrait, navy rules, page geometry, CV section grid, signature graphics and footer placement remain visually stable while only declared text/date/recipient zones change. The current PDF is therefore suitable as the canonical F6 layout artifact;
- two quality observations remain after successful rendering. The generated CV short profile contains the mixed-tense phrase `strukturiere beziehungsweise koordinierte`, so the Codex quality contract is tightened to reject mixed present/past constructions when current and previous roles share one sentence. The neutral `Guten Tag,` salutation remains acceptable but less personalized than the Hornet benchmark;
- the editable Word companion is **not yet Product-quality** despite containing the final text. Real LibreOffice/Word rendering of the generated file produces five pages rather than the canonical three, an almost-empty second letter page, a three-page CV, loss of the source visual identity, and duplicated extracted Alstom thesis/documentation lines. This is now treated as a convenience-export defect, not a PDF/template defect;
- candidate **1.1.13** therefore adds a separate live local file-build progress surface for PDF + Word, replaces the technical Codex caveat with concise user-facing progress help, moves the Word companion to A4/compact typography, removes exact duplicate extraction lines before DOCX authoring, and tightens paragraph spacing so the companion targets the same 1+2 page structure without claiming pixel authority;
- the first deliberate cross-job 1.1.13 operator test exposes a more fundamental F6 generalization blocker: **Eraneos is effectively the only selectable job that reaches Ready for drafting**. Finanz Informatik / Data Platform Engineer and Hannover Re / Software Engineer both have live vacancy + validated Product context but stop at `employer origin required`; another Eraneos row can surface a transport-level fetch failure. This proves F6 was coupled to source-registry history rather than current Product truth;
- root cause: `product_v1_application_workspace_runtime._employer_origin_authority` treats membership in the **currently active recurring employer-origin profile registry** as the normal F6 authority and only has a reviewed legacy Personio exception. That registry is an upstream ingestion admission boundary, not a valid downstream requirement for an already-materialized Product vacancy. A job can therefore remain `origin_validation_status=validated` + `active_confirmed` while F6 revokes it only because its source profile is not currently in that registry;
- candidate **1.1.14** replaces that source-specific downstream gate with a source-neutral Product-origin contract. F6 now accepts any persisted `origin_validation_status=validated` + current active lifecycle + direct non-aggregator HTTPS vacancy, independent of provider/source name. Known discovery/aggregator hosts/families remain fail-closed, exact observation URL mismatches remain fail-closed, and the generation action still performs exact live vacancy revalidation immediately before any Codex request;
- the active recurring SourceRole path remains valid as a stronger upstream proof, and the reviewed Personio contract remains only as legacy compatibility. No company, source-name, job-id or Eraneos-specific application exception is introduced;
- 1.1.14 also removes a latent Application Workspace GET error handler bug that referenced draft-only `request_id` state and could itself break a fail-closed workspace response;
- installed 1.1.14 cross-job proof is positive for the generic Employer-Origin gate: Finanz Informatik / Data Platform Engineer and Heartbeat AI / (Senior) Software Engineer - Device Connectivity both reach **Ready for drafting** with verified Employer-Origin authority, proving Eraneos is no longer a source-specific prerequisite;
- the next failures occur after a successful Codex provider call and are therefore **not capacity/token failures**. Runtime status remains `ready`, ChatGPT-authenticated, `gpt-5.6-sol`, reasoning `high`. Finanz Informatik fails because the validator requires the full legal company name or full title literally, while high-quality prose can correctly use `Finanz Informatik` or omit `(m/w/d)`. Heartbeat AI fails because a safe organization/team salutation or an ungrounded personal salutation is treated as terminal instead of being normalized safely;
- candidate **1.1.15** fixes this validator overfitting generically. Target-specificity matching now normalizes employer legal suffixes and job-title gender markers/segments; truly generic prose remains fail-closed. Grounded employer/team salutations are accepted, while ungrounded personal salutations or invented contacts are deterministically scrubbed to a language-appropriate generic salutation without a second provider call. These safe local semantic repairs are surfaced in the Product audit;
- before spending another operator/provider run, **1.1.16** performs a no-provider semantic hardening pass against adversarial identity cases. Review found two latent false-accept/false-grounding risks in 1.1.15: very generic one-token company names such as `AI GmbH` could satisfy specificity merely because ordinary prose contained `AI`, and a vacancy-grounded contact name could coexist with a salutation naming a different person because only the contact field itself was checked;
- 1.1.16 therefore uses token-sequence identity matching rather than raw substring matching, rejects weak generic company identities as sole specificity proof, rejects generic one-word role titles such as `Engineer` as sole specificity proof, still accepts short distinctive brands such as IAV, and requires a grounded contact salutation either to mention that contact or to use an approved generic form. Reordered/punctuated contact names in vacancy evidence remain valid through token grounding. Mismatched contact salutations are safely normalized locally and audited;
- this hardening adds synthetic regression cases for Finanz-Informatik-style legal names, Heartbeat-style team salutations, IAV short brands, generic AI/company collisions, token-boundary collisions such as `SAP` vs `sapient`, reordered contact names, mismatched named-contact salutations, and generic fallback salutations. It adds no provider calls and no company/job-specific runtime exception;
- installed **1.1.16** blind cross-job evidence is now mixed but materially useful. A previously unused enercity role (**Operation Expert Process, Data und Automation**) reaches full Quality-AI review and produces the canonical 3-page PDF on the first blind run, proving the generic path is no longer Eraneos-bound. A different previously unused Hannover Re role (**Software Engineer Workflow and Process Automation**) still fails before drafting with `vacancy_title_not_confirmed_on_detail_page`;
- root cause of that negative case is the lifecycle exact-detail title predicate: it still requires the complete normalized Silver title as one literal substring of the fetched response. Real employer pages can represent the same title as `Workflow & Process Automation`, add gender markers, or expose it only in a structured title surface / exact-detail URL slug. This is a verification overfit, not an Employer-Origin or Codex failure;
- candidate **1.1.17** keeps fail-closed exact-detail verification but makes title identity presentation-neutral: connector/gender noise is removed, HTML/JSON title-bearing surfaces are matched by normalized token sequence. URL identity remains mandatory, but the URL slug alone never upgrades a generic careers/listing page into active-vacancy proof; arbitrary body listings remain non-authoritative;
- 1.1.17 also tightens drafting style after the blind enercity result: avoid formulaic opening sentences when the vacancy offers a specific hook, avoid repeating the employer name merely to prove specificity, and require each paragraph to add a distinct part of the argument rather than restating process/quality/structure claims;
- the enercity PDF remains visually sound and grounded, but quality is not yet final: the body is specific and evidence-based while still somewhat formulaic/repetitive; the CV competence box also retains a visible trailing source bullet from the frozen template. These are quality/polish observations, not generic-path blockers;
- F6 canonical plan: `docs/planning/active/F6-TEMPLATE-AUTHORITATIVE-APPLICATION-DRAFTING.md`.

The 2026-09-24 installed Product truth contains **0 rankable / 0 Top-5** rows. This is not a refresh/UI failure: current capability/hard-filter evidence remains incomplete under the approved fail-closed Product contract. A verified read-only RCC diagnostic independently confirmed the same population condition. No ranking, hard-filter or Top-5 authority may be invented to unblock F6.

The 1.0.73 correction therefore separates two authorities. Top-5 stays strict and may remain empty. An explicit operator selection of a current, Origin-validated, authorized employer-origin vacancy may nevertheless open the review-only Application Workspace. Such a target carries `operator_selected_current_job`, has no Product rank, leaves unknown hard-filter evidence unknown, and is blocked by a known hard-filter failure. Candidate Facts, exact current vacancy evidence, exact F6 PDF authority, source-manifest binding, outside-zone pixel proof and the no-submit/no-send boundary remain unchanged.

The next Product gate is candidate **1.1.12** on live **Eraneos Silver #511 — Data Engineer (all genders)**. Re-run Quality AI and verify that live progress/Provider telemetry is visible during the long Codex request. The already-preflighted draft must then render directly to the verified 3-page PDF without `p1.competency_profile` divergence, and the editable DOCX companion must remain available. No Advanced zone editing is part of the acceptance path.


Read this file from canonical `refs/heads/main` before continuing Product work. During an active package, an exact package branch may carry a fresher candidate version; merge only after that package's required exact-head qualification.

## Updater hard cut — candidate truth on PR #987

The current updater migration is intentionally a hard generation boundary.

- installed stable anchor before migration: **1.0.59**;
- first CGKB product-local generation: **1.0.62**;
- pre-1.0.62 -> 1.0.62 is an explicit bootstrap bridge, not a routine direct update;
- new release namespace: `jap-winapp-product-v<version>`;
- immutable release contains both the self-contained Windows desktop and a source-bound runtime bundle with prebuilt frontend;
- the product-local agent performs discovery, download, checksum verification, extraction, runtime/desktop identity proof and helper staging **before consent**;
- after consent the isolated helper performs only frozen local integrity proof, desktop/runtime cutover, `current.json` adoption, restart identity proof and transactional rollback;
- routine apply has no PowerShell updater, WSL mutation, Git/checkout, CI-runner, npm build, release discovery, download or archive extraction authority;
- the retired local-deploy/updater files are physically absent and regression-gated against return.

Historical updater descriptions later in this document are retained only as incident evidence. They do not define current updater authority. The active architecture is `docs/guides/jap_control_center_windows_app.md` plus the executable contracts under `windows/JAP.ControlCenter.Desktop/`.


## Live repository checkpoint — 2026-09-21

Canonical public repository after the v1.0.48 startup recovery and installed-runtime smoke hardening:

`main@1bb7d32a2d1275c3509c4e176cfdef51c944ebca`

Current private runtime main:

`jenshaberle-dotcom/job-pipeline-runtime@4506f82bb1708b61c827ca39b3ecea0b048b8892`

MARKET-PARITY-001 / the bounded Hornetsecurity excursion is **operator accepted and
closed**. Productive main run `35578519791` proved the corrected company-only
sensor -> Employer-Origin authority chain and emitted
`HORNET_TARGET_CONTROL_CENTER_PROJECTION=PASS`. The installed v1.0.44 Product
then supplied the missing real operator proof:

- Hornetsecurity can be selected through the staged employer -> job manual fallback;
- the application date is date-only and operator-editable;
- the note/reference is optional;
- the canonical Silver schema write path works against the live DB;
- the Hornet Data Engineer appears immediately in All jobs as `Beworben`;
- the All-jobs `Beworben` count moved to `1`;
- re-recording the same Silver job does not create a duplicate application;
- `Job nicht in JAP` manual tracking is also operator-proven with the CARIAD
  external/manual path.

The Hornet excursion therefore has no remaining sequencing authority. JAP is back
on the frozen Product path `F5 -> F6`.

### v1.0.45 startup regression / v1.0.46 hardening

The v1.0.45 Product/F5 code itself qualified, but the first real post-update desktop
startup exposed a Windows/WSL runtime bootstrap regression. The GUI updater did
successfully install v1.0.45 and pin `630e550dd3cb516fa7723b9dc79caf21cd765776`.
The failure occurred after cutover while starting the managed WSL runtime.

Local diagnostics proved:

- `current.json` was already v1.0.45 / `630e550d…`;
- the managed worktree switched to the correct new source;
- the interactive startup deleted stale generated frontend state and entered
  `npm install` because no exact source-bound frontend bundle existed yet;
- the desktop startup deadline then expired, and the detached launch handoff did
  not provide a reliable first-start recovery;
- no DB, Gmail, application submission or lifecycle mutation was involved.

v1.0.46 therefore moves frontend installation/build **before update cutover**.
The update applier runs the exact target runner in a bounded `prepare` mode while
the old runtime is stopped and before the installer changes the active desktop
pin. That mode builds the React bundle, writes the exact `.jap-source-sha`
marker and exits. Normal interactive startup is now forbidden from invoking npm
or building frontend assets; it accepts only an already prepared bundle matching
the installed SHA and otherwise fails closed.

This is a startup/update-path hardening only. It does not reopen Hornet,
MARKET-PARITY-001 or the F5 product semantics.

### v1.0.46 prewarm regression / v1.0.47 direct frontend preparation

The first real v1.0.46 rollout proved the process-detection correction and reached
the intended closed-app auto-apply path, but its new frontend prewarm still called
the full Python Product launcher. That launcher imports runtime modules before
argument dispatch, so the frontend-only preparation failed with
`ModuleNotFoundError: extruct` before the installer cutover. The installed
product therefore correctly remained on v1.0.45.

v1.0.47 removes that failed Python prewarm surface instead of compensating for it.
The exact target WSL runner now prepares the frontend directly:

- select already-installed native Linux Node 22/npm;
- run the normal lockfile-aware npm dependency install;
- build the React Control Center;
- write the exact target SHA to `dist/.jap-source-sha`;
- remove generated `node_modules`;
- exit before Python venv, `.env`, DB, provider or Product runtime setup.

Interactive startup remains the inverse: it never runs npm/build work and accepts
only an exact source-bound prepared bundle. The deleted
`--prepare-frontend-only` Python path is regression-tested as absent.

The local deploy control plane also no longer encodes Windows process state as a
special PowerShell exit code. It reads a neutral process count, reserving non-zero
exit status for actual probe failure.

### v1.0.47 runtime-handoff regression / v1.0.48 WSL-native detach

The real v1.0.47 rollout then proved the direct frontend prewarm itself:
`JAP_WINDOWS_APP_FRONTEND_PREPARED=9d5ba134...`,
`AUTO_APPLY_PASS`, installed release `1.0.47`, and exact
`current.json@9d5ba134...`. However, the subsequent interactive operator start
still failed before any fresh runtime stdout/stderr was created. The popup came
from `JAP-Control-Center.ps1` at the custom Windows
`cmd.exe -> start /b -> wsl.exe` handoff with helper exit code 1.

That evidence separates update/install from runtime launch:

- v1.0.47 installation and source pin are correct;
- the exact frontend bundle is already prepared;
- no managed Product runtime process reaches its own logging on the failed click;
- the remaining defect is the Windows detached-launch helper, not npm, DB, Gmail,
  Product truth or the updater payload.

v1.0.48 removes the custom generated `.cmd`/quoting layer completely. Windows now
performs only one short, tokenized WSL call. The WSL runner's bounded `launch`
action uses Linux `nohup + setsid` with explicit stdout/stderr files to detach the
long-lived Product runtime, verifies the detached helper remains alive, and exits.
The normal WSL `start` path then owns all existing source, frontend, Python,
environment, local-OSS and DB readiness checks. PowerShell retains the same
75-second exact-source endpoint readiness proof.

The v1.0.48 recovery is now **operator accepted and closed**. Exact released source
`88945bb7eda3e64df9d4b236b9300360c8438754` was installed as desktop
`1.0.48`. Local deploy run `35602078710` then executed the newly permanent
installed-runtime smoke through the real installed
`JAP-Control-Center.ps1 -NoBrowser` path and proved:

- `JAP_WINDOWS_APP_DETACHED_HANDOFF=PASS`;
- loopback Product runtime became ready on `127.0.0.1:8780`;
- `/app-info.json.source_revision` exactly matched `88945bb7…`;
- `JAP_INSTALLED_RUNTIME_SMOKE=PASS`;
- managed runtime shutdown completed with `JAP_INSTALLED_RUNTIME_STOP=PASS`;
- port 8780 was closed again after cleanup.

The subsequent real operator launch also succeeded. The native JAP Control Center
opened normally and About displayed desktop `v1.0.48`, source revision
`88945bb7eda3...`, WebView2 WinForms, WSL-backed local runtime and PostgreSQL /
DB-backed truth. The updater/startup incident therefore has no remaining
sequencing authority.

F5 itself is **not yet operator complete**. PR #951 already merged the final
application-linkage/correction implementation; v1.0.48 carries it together with
the now-accepted startup recovery. The remaining operator feedback is therefore
purely the final Product interaction gate, without reopening mailbox authority:

1. a mistaken local operator submission can be explicitly undone;
2. only the operator-owned submission confirmation is removed;
3. an application identity is physically deleted only when that identity was
   created by the same local manual action and has no mailbox/evidence attachment;
4. Gmail/evidence rows are never deleted by this correction;
5. any authoritative lifecycle history blocks the correction;
6. All jobs gives active linked applications an explicit green row state instead
   of the ordinary blue selection treatment, while closed applications remain
   visually distinct.

The installed-runtime smoke is now a permanent pre-operator regression gate and
has passed on v1.0.48. The final F5 operator gate is therefore reduced to Product
behavior only:

`All jobs green linked Beworben state -> click linked Beworben -> same Applications record -> safe correction control visible -> bounded mistaken-entry removal proof -> All jobs link/count removed after shared Product-truth refresh`

Only after that bidirectional/visual linkage and correction loop is accepted may
F5 be marked complete and sequencing advance to F6.

The accepted v5 Gmail read-only freeze-resume preflight remains evidence only. It
predicted a bounded delta but did not authorize or perform a new mailbox
persistence apply. No Gmail write, email send, automatic application submission or
authoritative lifecycle mutation is introduced by this final UI/correction slice.

## Retained repository checkpoint — 2026-09-18

Canonical public repository state before this re-entry refresh:

`main@560417bd83e452d880e2c0e327c16c590de4fd9e`

Canonical private runtime state:

`jenshaberle-dotcom/job-pipeline-runtime@805ff8a751c3a3630879d9765658ec5c17ceec22`

Public PR `#925` and runtime PR `#381` completed the pre-persistence mailbox outcome hardening. Public PR `#927` then fixed the real direct-CLI preflight import path, and public PR `#928` decoupled the read-only preflight from PostgreSQL-driver availability. PR `#928` exact candidate `49f8466fa47e8cb6c1d7e07707e473394d3345e5` passed F5 application lifecycle qualification `35250071633`, Pipeline re-entry target identity `35250071679` and Pipeline CI `35250072571`, all SUCCESS, before merge as `1a2de9e9feefc35d42cb16c82ab5cddde5c78331`.

The current operator-visible Product is `jap-winapp-desktop-v1.0.40` from exact source `d725b7de482721cb83176e1ea1e643210a02df51`. Operator review confirms the precise-warning/status-cluster presentation is materially improved. F5 remains open for one final read-only UX linkage slice: compact portfolio rows plus `silver_job_id -> effective_stage` application status inside All jobs.

## Frozen campaign sequence — current

`F5 -> F6`

Completed current-campaign packages are F0, F1 capability delivery, F2, F3, F4A, F4B and F4C. F5 schema, mailbox-first correction, first bounded persistence write, shared Product-truth/linkage architecture and the v1.0.42 operator surface are complete. The later mailbox recall findings reopened only the **evidence cohort**, not the F5 authority model. After cross-layer semantics hardening and accepted v5 anchor audit, F5 is now at the **read-only v5 batch + live-DB persistence-plan gate**. No persistence apply is authorized until that plan is inspected.

## Product authority that remains invariant

Employer-Origin admission retains one authority path:

`company candidate -> generic evidence-driven origin layers -> strict source proof -> valid source -> query-proven vacancy -> Origin Bronze -> Silver -> lifecycle/identity truth -> Gold -> Product -> Control Center`

Rules:

1. Current generic `proof=PASS` is the sole Employer-Origin source-validity authority.
2. Source admission and job admission remain separate.
3. Market sensors are discovery/freshness evidence only.
4. Only credible vacancies with exact Origin evidence enter Bronze.
5. Learned observers may improve discovery/understanding but create no source/Fit/ranking/application authority without separate qualification.
6. Product/Control Center consumes upstream truth; UI-only repair is not authority.
7. No employer-specific identity/ranking exception, fuzzy merge, weak URL rewrite or invented missing requirement is allowed.
8. Missing evidence stays missing/unknown unless an approved deterministic or reviewed authority resolves it.

## Frozen package execution policy

Normal product-changing package flow remains:

`implementation -> focused tests -> Full Suite/Ruff/React/Windows contracts -> real Product/Origin proof -> merge exact tested head -> immutable Windows release -> automatic local deploy -> interactive operator test -> record evidence -> next package`

Read-only diagnostic/private-preview slices that do not change installed Product behavior may merge after exact-head qualification without manufacturing a no-op Windows release.

Exact-head discipline remains mandatory. Tracked migrations are immutable; every branch change invalidates earlier final qualification authority; Gmail/runtime evidence remains evidence rather than authoritative lifecycle state; no automatic email reply/send or application submit is introduced by F5.

## F4C — OPERATOR ACCEPTED / COMPLETE

Canonical item `#898 / F4C Source Health + Operator Surface Consolidation` is closed. Accepted truth dimensions remain separate:

`lifecycle eligibility != scheduler/run history != current reachability != evidence freshness != delivery/product yield`

Post-freeze operator simplification/Data-Layers truth audit remains isolated in `#910` and is not a blocker for F5/F6.

## F5 — COMPLETE / OPERATOR ACCEPTED (historical detail retained)

Canonical item: `APP-TRACK-001` / issue `#737` and `docs/planning/active/F5-APPLICATION-LIFECYCLE-TRACKING.md`.

F5 extends the Product journey beyond `draft_for_review` into evidence-first post-application tracking:

`application prepared -> operator confirms submitted -> communication evidence observed -> event candidate -> reviewed/authoritative lifecycle state -> next action`

Authority rules:

- submission authority comes only from explicit operator confirmation or another separately approved authoritative submission record;
- Gmail/runtime communication is evidence only and may not silently rewrite lifecycle state;
- Gmail credentials/raw private messages remain private-runtime/secrets-bound;
- public Pipeline owns schemas/read models/provider-free contracts/tests/UI semantics;
- no automatic email reply/send and no automatic application submit;
- lifecycle/status history is append-only or explicitly superseding, never destructive rewrite;
- deterministic identity/thread/domain/rule evidence precedes any future model assistance.

### Slice A — COMPLETE

PR `#911` established the read-only real Product reconciliation. It proved zero historical submitted-application/event authority before F5 mutation.

### Slice B — COMPLETE

Migration `112_create_authoritative_application_lifecycle.sql` established four deliberately separated layers:

1. `applications`: prepared/discovered application identity; presence is not submission authority.
2. `application_submissions`: sole submission authority.
3. `application_lifecycle_events`: append-only authoritative post-submit events.
4. `application_event_candidates`: communication evidence only and excluded from direct authoritative stage derivation.

`gold_product_v1_application_tracking` derives only `prepared -> applied -> reply -> interview -> offer -> closed` from prepared identity + explicit submission + active authoritative events.

### Mailbox-first correction — COMPLETE

Migration `113_enable_mailbox_first_application_tracking.sql` made mailbox-first discovery possible without inventing a JAP job or submission authority. Exact migration apply `35186715621` and independent post-apply/Product proof `35186749692` were SUCCESS with checksum drift `0`, pending migrations `0`, and zero seeded application/submission/lifecycle/candidate truth.

### Real Gmail preview + observation hardening — COMPLETE THROUGH ACCEPTED SIGNAL RE-PREVIEW

The private runtime OAuth/read boundary is established and remains exact `gmail.readonly`. Gmail per-message reads remain `format=metadata`; normalized output contains bounded Subject/Snippet, deterministic identity hints and hashed mailbox/thread/message references. Gmail writes, JAP/PostgreSQL writes and provider cost remain zero in the preview bridge.

The historical pre-hardening annual batch produced `203` input rows, `93` rows in the selected 2026 window, `8` discoverable rows, `10` review-worthy rows, `83` other, `2` ambiguous, `8` unique application keys and `0` duplicate evidence rows. That batch exposed the HDI acknowledgement+rejection conflict, the Capgemini snippet-boundary rejection and the low-impact acknowledgement+recruiter ambiguity pattern.

Public PR `#925` hardened deterministic precedence and validates bounded `gmail_search_signals`. Runtime PR `#381` adds server-side Gmail `messages.list` searches for strong lifecycle-specific phrases only, hashes provider message IDs, downloads no full/raw body and emits only whitelisted signal labels.

The **new signal-enhanced real annual preview is now accepted**. Operator run on 2026-09-17 used private JSONL SHA-256 `33265bb4da98ce422ff8df9318b8279651cc5231d45f3a6e948628ed2ccdc4b5` and public `main@1a2de9e9feefc35d42cb16c82ab5cddde5c78331`. Public preflight result:

- input rows `203`;
- 2026 window rows `93`;
- valid rows `93`, invalid rows `0`;
- discoverable rows `11`;
- review-worthy rows `11`;
- other rows `82`;
- ambiguous rows `0`;
- unique application keys `9`;
- duplicate evidence rows `0`;
- class counts: `8` application acknowledgements, `3` rejections;
- Gmail network requests from public preflight `0`;
- database connections/writes `0`;
- application submission actions `0`.

The critical regressions are resolved in real evidence:

- HDI 2026-07-23 is now `rejection` while HDI 2026-07-01 remains `application_acknowledgement` for the same application identity;
- Capgemini 2026-06-21 is now `rejection` while Capgemini 2026-03-14 remains `application_acknowledgement` for the same application identity;
- the former ambiguity count drops from `2` to `0`;
- MODULAT 2026-01-12 is additionally discovered as a deterministic rejection;
- `11` discoverable evidence rows collapse to `9` unique application keys, confirming that multiple lifecycle messages for one application must remain distinct evidence rows under one application identity.

### Candidate source identity + migration 114 — COMPLETE

PR `#930` implemented the source-message identity/supersession contract and a provider-free persistence planner. PR `#931` added the exact-main real DB preflight trigger. The stable Gmail source identity is now independent of classifier interpretation: `source_kind + mailbox_account_fingerprint + source_message_reference`. Reclassification preserves audit history while migration 114 enforces exactly one active interpretation per source message; different Gmail messages for the same application remain independent evidence.

The accepted private annual preview remains exactly:

- JSONL rows `203`;
- SHA-256 `33265bb4da98ce422ff8df9318b8279651cc5231d45f3a6e948628ed2ccdc4b5`.

The operator persistence planner on exact public `main@a5a98205e7a6eec253e0a78ea5ba8e16bc439170` is accepted:

- input rows `203`;
- 2026 window rows `93`;
- valid / invalid `93 / 0`;
- persistence candidate rows `11`;
- skipped first-seen `other` rows `82`;
- predicted application inserts `9`;
- predicted candidate inserts `11`;
- predicted no-ops `0`;
- predicted supersessions `0`;
- classes: `8` acknowledgement, `3` rejection;
- plan SHA-256 `741f00096e44d8ea020819697ae335ae0ee8a9839beace6386fd3e13957eb3c5`;
- Gmail requests, DB writes, submission actions and authoritative lifecycle mutations all `0`.

Migration `114_application_event_candidate_source_identity.sql` is now **applied and independently post-apply qualified** on that same exact source:

- exact-main preflight run `35274669336`: SUCCESS;
- first apply attempt `35308823088`: fail-closed before mutation because RCC runtime context was stale; apply step skipped;
- operator RCC refresh then proved repository identity, checkout, env, interpreter and PostgreSQL `SELECT 1` capability `PASS`;
- exact apply run `35311387470`: SUCCESS;
- independent read-only post-apply run `35311424361`: SUCCESS;
- post-apply artifact `10533103923`, digest `sha256:b78bd0b142e5a7929b08864b3aaa5437d0d01ecc9f872f163510144c42b74e2b`;
- migration 114 tracked successful, pending migrations `0`, checksum drift `0`, duplicate active source identities `0`;
- post-apply proof performed no DB writes, Gmail reads, email actions, submission actions or authoritative lifecycle mutations.

The accepted Gmail batch is now persisted under explicit operator authority and independently post-write qualified.

### Bounded first persistence apply — COMPLETE / TERMINAL PASS

PR `#932` added the atomic hash-bound apply path and live-DB preflight. PR `#933` fixed the Git-source-SHA validator after the first operator preflight failed closed before any DB connection. The accepted live read-only preflight on exact `main@19fb4b7e1a36830d895161e19922dfa398e49bfd` proved:

- input rows `203`, window `93`, valid `93`, invalid `0`;
- input SHA-256 `33265bb4da98ce422ff8df9318b8279651cc5231d45f3a6e948628ed2ccdc4b5`;
- plan SHA-256 `741f00096e44d8ea020819697ae335ae0ee8a9839beace6386fd3e13957eb3c5`;
- planned application inserts `9`;
- planned candidate inserts `11`;
- candidate no-ops / supersessions `0 / 0`;
- classes `8 application_acknowledgement`, `3 rejection`;
- DB connections `1`, DB writes `0`;
- Gmail/email/submission/authoritative-lifecycle actions `0`.

The operator then explicitly authorized exactly that batch. Atomic apply completed with:

- `F5_MAILBOX_PERSISTENCE_APPLY=PASS`;
- transaction `committed`;
- exact effects `9 applications + 11 candidates`;
- apply report SHA-256 `51599f3848ae4befd78712c4f34c0badabef075ed4f062082ad9a52845b25e8e`;
- no Gmail action, application submission action or authoritative lifecycle mutation.

PR `#934` added the independent read-only post-write qualifier. PR `#935` separated historical apply source from current proof source. The terminal operator proof on current `main@560417bd83e452d880e2c0e327c16c590de4fd9e` produced report SHA-256 `9cc4626b6296f6bd90bb7a23e4ef83a676e1492e7e6cc7d28ec4e29cfbd3e96f` and proved:

- verified application rows `9`;
- verified candidate rows `11`;
- verified Product tracking rows `9`;
- active Gmail candidates `11`;
- scoped/global submission rows `0 / 0`;
- scoped/global authoritative lifecycle rows `0 / 0`;
- `authoritative_stage=prepared` remains separate from mailbox-observed/effective state;
- post-write DB writes `0`, Gmail network requests `0`, email/submission/lifecycle mutations `0`.

Issue `#737` terminal evidence comment: `5731105594`.

### Control Center lifecycle UX — IMPLEMENTED ON MAIN / DELIVERY PENDING

The public Product runtime and React surface already implement mailbox-first tracking:

`Prepared -> Applied -> Reply -> Interview -> Offer -> Closed`

Current `main` exposes `observed_stage`, `effective_stage`, mailbox-discovered application counts, external/mailbox-only application identities, bounded evidence detail and the explicit observed-vs-authoritative distinction.

Published desktop v1.0.38 predates that mailbox-first projection. Therefore a new immutable v1 release is required; changing only live DB truth is insufficient because v1.0.38 does not contain the current tracking surface.

The installed v1.0.39 operator review proved the real mailbox cohort is visible, but exposed two completion defects: attention semantics were over-broad and the list lacked status clustering; several mailbox-only cards also lacked useful job identity. v1.0.40 is the corrective Product slice. It narrows attention to true review-required evidence, groups cards by effective lifecycle stage, surfaces bounded job identity metadata, and adds a read-only accepted-preview-vs-DB enrichment preflight before any metadata repair write.

### v1.0.39 operator acceptance — PARTIAL / FOLLOW-UP OPEN

The installed v1.0.39 About screen proved version `1.0.39` and source `27c0c27b...`. The Applications screen proved the real persisted cohort is visible. Operator feedback found:

- HDI/other correctly classified high-confidence evidence still received the same amber warning because storage `unreviewed` state was conflated with actual review need;
- applications need lifecycle-stage clustering;
- some mailbox-only cards lack job title/employer detail.

Issue #737 comment `5740140017` records the defect boundary. No new Gmail or lifecycle authority is implied.

### v1.0.40 operator review — ACCEPTED WITH FINAL UX FOLLOW-UP

The operator confirms the corrected warning semantics, status clustering and richer job metadata are substantially better. Final F5 UX feedback is tracked in issue #737 comment `5740425082`:

- Applications should default to a compact row containing current effective status + job identity and expand on demand;
- All jobs should show the linked F5 application status for Silver-backed applications;
- the `Beworben` filter must exclude `prepared/Erkannt` identities;
- linked job detail should navigate directly to Applications;
- all linkage remains read-only and reuses F5 `silver_job_id -> effective_stage`.

Target release is `v1.0.41`.

### v1.0.42 final operator-linkage architecture — ACTIVE / PR #941

The v1.0.41 operator check exposed two separate completion items: current All-jobs warning density regressed after the Application column was inserted, and the job/application navigation remained a loose UI handoff rather than one coherent application state.

PR #941 / v1.0.42 now keeps these boundaries explicit:

- required/unknown/insufficient evidence is neutral pending presentation; stale/ambiguous/unsure remains amber and failed/blocked/rejected remains red;
- safe mailbox->Silver reconciliation remains read-only; unresolved linkage remains `Ungeklärt` rather than being treated as a negative application fact;
- Jobs and Applications consume one centrally owned Product-truth snapshot distributed inside the React application;
- refresh is owned by one ProductTruth provider and concurrent refresh requests are deduplicated;
- F4C, review controls, application preparation support and evidence preview no longer maintain independent Product-truth read/update paths;
- Jobs -> Applications uses persistent application state (`selectedApplicationId`) rather than a one-shot browser event;
- Applications -> Jobs uses the same application/Silver identity, including exact projected linkage, and navigates back only when that Silver job is actually present in the current All-jobs snapshot;
- a linked historical/stale job outside the current review scope is shown as such and never redirects to an unrelated visible row;
- the manual tracking fallback refreshes the shared Product truth after its explicit write instead of reloading the page.

The current live reconciliation still has exactly one deterministic HDI -> Silver #2 match, and that job remains outside the current Employer-Origin All-jobs review scope. Therefore bidirectional navigation is implemented generically but correctly fails closed for that historical live case.

No DB link persistence, Gmail action, automatic submission, authoritative lifecycle mutation, or second application-status heuristic is introduced.

### v1.0.44 manual-application convergence — PR #949

PR #949 is the F5 corrective Product slice discovered through the real
Hornetsecurity case. It keeps manual operator truth and later mailbox evidence in
one application identity instead of producing duplicate visible applications.

The operator-facing manual fallback now:

- records a date only; no irrelevant application time input is required;
- requires employer selection before offering only that employer's untracked JAP
  jobs;
- supports an explicit `Job nicht in JAP` path with bounded employer, title and
  optional source URL;
- refreshes the shared Product truth after the write so a known Silver job is
  immediately eligible for the All-jobs `Beworben` marker.

Later deterministic Gmail evidence first attempts conservative convergence onto an
existing operator-confirmed application. Exact source URL wins; otherwise company
identity must be exact after legal-form normalization and the title must be exact
or a sufficiently specific prefix-family match. Short generic role names do not
auto-link. Ambiguity fails closed. The operator submission record remains audit
provenance; the Product shows one application record with added mailbox evidence.

The Hornet title family is a regression fixture: a later title such as
`AI Automation Architect Software Development Lifecycle Germany Europe` must
converge onto the already tracked
`AI Automation Architect Software Development Lifecycle` application without a
second application insert.

Desktop release target: `v1.0.44`.

Runtime automation truth: the private F5 Gmail workflow has a daily schedule, but
that schedule currently runs only compile/tests/contract and boundary checks. It
does **not** execute a real Gmail scan or persist mailbox evidence. A recurring
read-only Gmail scan remains an F5 follow-up after the current manual/mailbox
identity convergence is accepted.

## Sole next action

After PR #949 is exact-head qualified, merge and release/install desktop
`v1.0.44`. Then run the canonical F5 lifecycle workflow in
`v5_resume_preflight` mode on exact current `main`. It must consume the already-generated private v5 JSONL only on
the verified runtime host, run the public batch preflight with findings suppressed
from logs/artifacts, derive the current live persistence plan under a read-only
PostgreSQL transaction, and independently re-run the existing hash-bound live
preflight.

Only safe aggregate/hash reports may be uploaded. The private JSONL must not be
uploaded or committed. Expected side effects remain exactly zero: Gmail writes,
DB writes, email actions, application submissions and authoritative lifecycle
mutations.

If that read-only gate passes, inspect its exact predicted delta. Any subsequent
persistence apply is a separate operator gate; F6 remains queued until F5 data
truth is accepted.

## F6 — ACTIVE

Template-Authoritative Application Drafting is the active final frozen package. Slice A is **COMPLETE / OPERATOR ACCEPTED**. Current Slice B candidate is PR #999 on `feature/f6-b-template-bound-renderer`: exact-template entry validation, declared-zone-only text mutation, overflow fail-closed, and strict raster outside-zone identity proof. A local qualification command uses both already-installed private templates, persists no rendered output, and is the next operator gate after exact-head qualification/merge/release. Slice C review/edit + final local PDF export remains queued. Human review remains mandatory; no automatic submit/send.

## Cascading residual rule

Active carried residuals remain:

- `CR-F1-001`: fresh company -> F1 discovery -> CAND-001 persistence -> proof/activation;
- `#891 / F4B-FOLLOWUP-001`: generic skill extraction, capability auto-fit, numeric Fit and Combined calibration in the next freeze campaign;
- `#910`: post-freeze operator UX simplification + Data Layers truth audit.
