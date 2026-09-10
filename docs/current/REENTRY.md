# JAP Current Re-Entry

Status: canonical current re-entry projection

Read this file from canonical `refs/heads/main` before continuing product work. `docs/current/README.md` remains useful general operational context, but this file is the sequencing authority where older text conflicts with it.

## Employer-Origin product authority

The Employer-Origin acquisition architecture is version-independent and has exactly one product admission path:

`candidate -> generic evidence-driven layers -> strict proof -> valid source -> generic_origin:<company_key> -> active recurring observation -> job plausibility gate -> Bronze -> Silver -> Gold -> Product -> Control Center`

The **generic evidence-driven layer model is the sole Employer-Origin source-validity truth**.

A source is valid when the current generic layer evaluation reaches `proof=PASS`. Every such source is eligible for product activation. V1, V2, V3, V4, V5 and V6 labels are historical engineering/audit checkpoints only. They are not independent product architectures, cohorts, promotion rules, activation authorities or fallbacks.

The following must not be used to admit or activate Employer-Origin sources:

- V1..V6 audit runners or fixed historical benchmark cohorts;
- DEMO-001 source/readiness workflows or demo evidence;
- historical materialized 36/65, 40/x or similar coverage cohorts;
- provider-specific one-off registry membership;
- legacy connector-validation/final-approval gate state as an alternative to generic `proof=PASS`.

Reusable provider/navigation/feed implementations may remain as capabilities composed **inside** the generic layered path. Their historical filename or origin does not grant them admission authority.

## Source admission is not Bronze admission

Source validity and current job quality are deliberately separate decisions.

1. `proof=PASS` admits and activates the source.
2. The active source may observe zero or more current job candidates.
3. Only minimally credible current job records are admitted to Bronze. At minimum the product record must preserve a concrete HTTPS detail URL, non-generic job title, employer identity, candidate identity and genuine generic-layer job proof lineage.
4. Zero Bronze-ready jobs is a valid successful observation for an active source and must not revoke source validity.

The generic recurring profile uses `*` only as a non-semantic execution trigger. Relevance/ranking vocabulary is a later product stage and must not be smuggled into source validity.

## Durable projection

`generic_employer_origin_active_sources` is the materialized current `proof=PASS` projection used to keep source activation inspectable. It is not a second admission system. Its schema only permits authority `generic_evidence_driven_layer_model` and `proof_state='pass'`.

Search profiles and candidate `active_controlled` state are downstream activation projections of the same current generic proof cohort.

## Current repository state

PR #846 (`P1: turn generic origin proof into bounded systematic search`) established the generic read-only search/detail funnel and merged as `ee013d85152fa0f3dcb4e412fe5707b26976f2bc`.

PR #847 (`P1: bridge query-proven generic search into product ingestion`) is now merged to `main` as:

- merge SHA / activation source SHA: `49ddc067c912eac44aa1de85155adc721d617e72`
- validated PR head before squash: `170f860627791ff5ec3524400c6de2d3bd3ad486`
- Product Proof run: `34362163108` — PASS
- post-merge activation run: `34445141597` — PASS
- activation job: `102768208072`

PR #847 moved the systematic search from audit-only evidence into the normal product registry. It preserves `*` only as the neutral recurring trigger, performs bounded target-vs-impossible-control query-semantic discrimination, fetches generic local detail evidence, stamps the existing Bronze/lifecycle evidence contract, and then reuses normal ingestion and Silver/Gold/Product/Control-Center read models. It also added a requirements-bound pinned local OSS runtime layer for `extruct==0.18.0` and `trafilatura==2.2.0`, including daily RCC self-healing so the Warmrunner no longer depends on stale global/runtime imports.

No Control-Center frontend or Windows desktop-host file changed in PR #847. The persisted E2E therefore remains compatible with the already-installed Product V1 Control Center contract.

## Persisted Product E2E — proven

The exact-main post-merge activation effect on `49ddc067c912eac44aa1de85155adc721d617e72` completed the real persisted chain and emitted `GENERIC_PRODUCT_ACTIVATION_E2E=PASS`.

Verified state after the run:

- current proof-pass / active generic Employer-Origin sources: `24`
- legacy active Employer-Origin sources: `0`
- latest successful generic ingestion runs: `24`
- persisted generic Bronze rows: `121`
- query-semantically proven Bronze rows: `95`
- detail-fetched Bronze rows: `95`
- normal Silver rows: `26`
- Gold Product V1 readiness rows: `26`
- Control Center `job_readiness` rows for those Gold identities: `26`

The first concrete persisted identity proven unchanged through the downstream product read path is:

- Silver ID: `575`
- source: `generic_origin:clarios_germany`
- employer: `Clarios Germany GmbH & Co. KG`
- title: `Director Data and Analytics`
- Product V1 gate: `assessment_required`
- originating persisted raw job in this activation: `37802`

The same activation also persisted current jobs from Finanz Informatik, GFT Technologies and Hannover Rück. GFT jobs correctly did not reach Silver where current accessibility evidence was absent; this is gate behavior, not an ingestion failure.

This closes the previous sole-next-action requirement. Gold/Product/Control Center is no longer inferred from a read-only audit: it is backed by persisted PostgreSQL state and the normal Product V1 payload loader.

## Current measured search funnel

The earlier #846 read-only proof measured:

`23 proof-valid -> 9 deterministic search surfaces -> 3 query-semantically proven sources -> 67 accepted jobs -> 67 detail evidence -> 67 Bronze -> 26 Silver-relevant`

The later exact-main activation re-proved the live source cohort at `24` proof-pass sources and produced new persisted jobs from four currently delivering sources. Individual live source outcomes remain allowed to move between proof/search observations over time; the current source authority is always the fresh generic proof projection, not the historical 23-source cohort.

The dominant engineering opportunity remains **before detail extraction**: generic deterministic search-surface detection and query-semantic generalization. The reached-job detail/Bronze/Silver path has now been proven both read-only and persisted.

Do **not** reopen portal-specific hardening, company allowlists, vocabulary/taxonomy tuning, provider introduction or cosmetic location/remote extraction merely to increase counts unless fresh evidence identifies one of those as the next product bottleneck.

## Effect authority

`.github/workflows/p1-generic-origin-product-activate.yml` remains the sole bounded Employer-Origin activation effect path for this source-admission/product cutover. PR validation stays read-only. The activation workflow must use exact main, the verified local Product/PostgreSQL runtime, generic proof projection, normal `generic_origin` registry and normal Bronze/Silver/Gold/Product read path.

No demo workflow, V6 runner, manual fixed cohort or provider-specific registry path may substitute for it.

## Operator-visible Control Center checkpoint

The persisted backend E2E is complete. The remaining checkpoint is only interactive operator inspection in the already-installed Windows Control Center.

Installed desktop release observed before this activation:

- version: `1.0.15`
- release source SHA: `afbeb50f0f1bce9902e6be46bbaf0f7f8f6784c7`
- executable: `C:\Users\jensh\AppData\Local\JAP-Control-Center\desktop-host\JAP.ControlCenter.Desktop.exe`
- local Product V1 runtime port: `8780`

The scheduled local-deploy workflow correctly refuses to replace that release with arbitrary unreleased `main`. A new Windows release is **not required merely to view this E2E**, because #847 did not alter the frontend/desktop Product V1 contract and the existing UI already consumes `job_readiness` from the live Product V1 payload.

Operator check:

1. Launch the installed JAP Control Center interactively on Windows.
2. Open `All jobs`.
3. Keep the default `All observed` filter or ensure it is selected.
4. Search for `Director Data and Analytics` or `Clarios`.
5. Open the result and verify the detail pane shows `Silver #575` and Product gate `assessment required`.

The GitHub/Warmrunner path must not be used to force an interactive Desktop window: the desktop host intentionally rejects noninteractive/headless runner launch. That boundary is expected behavior.

## Sole next action

**Operator-visible inspection of the already-persisted E2E job in the local Windows Control Center is the sole immediate action.**

Once Silver `575` / `Director Data and Analytics` / Clarios is visible there, the Employer-Origin persisted E2E milestone is closed end-to-end from source proof through operator UI.

After that confirmation, return to the measured upstream bottleneck: improve generic deterministic search-surface/query-semantic coverage from the current live proof-valid source cohort without weakening source proof, Bronze admission, accessibility or Product V1 gates.
