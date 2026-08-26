# ACQ-RUNTIME-001 Runtime / Network Acquisition

Status: deterministic implementation contract; evidence-exhausted for bound 40-case cohort  
Date: 2026-08-25  
Authority: Pipeline issue #642  
Current Pipeline acquisition authority: `36972bf50c787ee291e3179d9b9fd86123dabd88`  
Current Runtime campaign authority: `f763ea905a158e964f185beedaca05b17890f8c4`

## Why this layer exists

The static V4 acquisition surface reaches `23/40` genuine-job proofs and `17/40`
`no_genuine_job_detail` residuals under the fixed four-request contract. Fresh V4
run `32881331391` reproduces that result on the current Pipeline authority and is
the regression control for the static default path.

Runtime evidence proved that additional deterministic information is often absent
from static responses and appears only after bounded client execution through
XHR/fetch/POST traffic, public inventory widgets, runtime-rendered listing routes,
or visible listing interaction.

The browser is therefore an **evidence sensor, not an authority mechanism**.
Runtime observation can unlock only explicitly bounded deterministic transitions.

## Two current acquisition truths

Do not conflate these metrics:

### Static default truth

Fresh V4 run `32881331391` on Pipeline
`36972bf50c787ee291e3179d9b9fd86123dabd88`:

- input: `40`;
- genuine-job proven: `23`;
- blocked: `17`;
- blocked causes: `{"no_genuine_job_detail":17}`;
- logical network requests: `110`;
- request budget unchanged: base `3`, shared extra `1`, absolute max `4`;
- Product/job persistence: `0`.

### Bounded Runtime deterministic truth

Accumulated Runtime campaigns through V34:

- static baseline: `23/40`;
- deterministic rescues through V24: `+5`;
- V25 visible interaction: `+1`;
- V26: `+0`;
- V27: `+0`;
- V28: `+0`;
- V29 observed ATS listing replay: `+1`;
- V30: `+0`;
- V31 oversized jobish JSON inspection: `+0`;
- V32 structural provenance diagnostic: `+0` by construction;
- V33 `absolute_url` parser repair replay: `+1`;
- V34 nested key provenance diagnostic: `+0` by construction;
- **Runtime deterministic proven: `31/40`**;
- **unresolved: `9/40`**.

Runtime proof is acquisition evidence. It is not automatically Product/source/
application authority and must not be arithmetically added to the static V4 count.

## Target flow

```text
authorized career/listing page
    -> bounded browser execution
    -> optional bounded visible listing interaction
    -> transient network observation
    -> structured response recognition
    -> deterministic runtime job-record proof
    -> bounded one-hop delegated inventory authority when proven
    -> candidate detail/runtime evidence
    -> unchanged downstream authority
```

No interaction, provider marker, candidate object, historical URL, or browser event
is Product truth by itself.

## Runtime structured-response authority

`src/search_intelligence/runtime_network_acquisition.py` owns the pure Runtime
network contract. It:

- sanitizes persistable request/response/page URLs;
- redacts secret-like query values;
- traverses transient JSON with explicit node/depth/candidate bounds;
- recognizes provider/company-agnostic job-shaped records;
- gives explicit non-job containers precedence over endpoint job context;
- separates recognition from `runtime_job_record_proof`;
- permits `runtime_authorized_inventory_record` only after the existing strong
  structured-record checks succeed on an authorized Runtime surface;
- permits `runtime_page_delegated_inventory_record` for the bounded observed
  cross-host inventory case;
- permits one-hop candidate-host delegation only after Runtime job-record proof;
- persists no raw response body, cookies, headers, form values, credentials, or
  browser state.

Pipeline PRs #645, #646, and #650 established the core generic contract. Provider or
company-specific success exceptions are not encoded.

## Generic URL recognition and `absoluteurl`

V31-V33 exposed and repaired one evidence-backed parser blind spot without changing
proof authority.

V31 observed a same-authorized Zscaler `POST /api/get-greenhouse-jobs` response of
`2,568,911` bytes. The response contained recognizable job-shaped records but no
candidate URL under the then-current URL-key vocabulary.

V32 structural provenance run `32875715254` proved:

- top-level `jobs` contains `342` direct records;
- all `342` contain normalized `title`, `id`, `locations`, and `absoluteurl`;
- `absoluteurl` was the sole unrecognized URL-shaped key on those job records;
- negative sibling `departments` and `locations` containers did not carry the same
  title/identity/URL structure.

Pipeline PR #656 added normalized `absoluteurl` to `URL_KEYS` only. It was **not**
added to `EXPLICIT_JOB_KEYS`, so an `absolute_url` field alone never makes an object
a job. Existing job context, scoring, authorization, and proof requirements remain
mandatory.

V33 run `32880015344` replayed the same Runtime surface with that one parser delta:

- candidate `56` / Zscaler rescued;
- bounded candidates: `30`;
- existing Runtime proofs: `20`;
- proof kind: `runtime_authorized_inventory_record`;
- observed delegated host: `job-boards.greenhouse.io`;
- diagnostic/drain/context failures: `0/0/0`;
- no acceptance, host, or proof rule changed.

## Bounded visible listing interaction

`src/search_intelligence/runtime_listing_interaction.py` owns the pure interaction
selection policy. Runtime browser execution remains outside the module.

Default per-page budget:

```text
max_total_actions = 3
max_click_actions = 2
max_scroll_actions = 1
```

Generic families remain:

1. explicit load/show/view-more jobs or positions;
2. explicit next-page/jobs controls, with plain `next` only in job context;
3. explicit jobs/open-jobs/search-jobs/view-jobs controls;
4. one bounded scroll probe if no fresh eligible click exists.

The caller must rescan visible controls after every action. Hidden/disabled controls,
apply/login/register/upload/contact/filter/sort/privacy/cookie noise, disallowed
roles, non-HTTPS absolute hrefs, repeated fingerprints, inconsistent progress, and
post-budget actions fail closed.

V25 proved this surface can add recall; V26 removed harness artefacts and added no
further rescue. **Do not broaden interaction semantics merely to chase the current
nine residuals.**

## Historical/provider route observations

Later campaigns established additional bounded principles without creating guessed
provider routes:

- V27: the exact current X1F Personio feed was real but empty; do not guess another
  tenant/locale/feed;
- V28: canonical provider-detail shape alone is not proof when unchanged content
  proof fails;
- V29: an exact historically observed provider/listing route may be replayed as a
  sensor entry when it remains authorized and otherwise admissible; historical
  observation itself grants no job authority;
- V30: broader already-observed public route replay added no rescue;
- V31: a transient body-cap lift may inspect a same-authorized jobish JSON response
  when bounded by the explicit campaign contract; the cap lift itself grants no
  proof.

No direct endpoint invention, token reconstruction, tenant guessing, POST-body
reconstruction, or company-specific protocol branch is authorized by these results.

## V34 deterministic exhaustion evidence

Authoritative V34 run `32880929572` inspected the exact V33 nine-case residual for a
final generic nested parser/protocol blind spot. V34 was diagnostic-only and could
not rescue a case by construction.

Result:

- `9` residual cases bound;
- only `4` cases / `7` already-observed seeds remained replay-eligible;
- five cases had no admissible deterministic seed on this surface;
- `3` same-authorized jobish JSON structural events inspected;
- diagnostic failures: `0`;
- response-drain timeouts: `0`;
- context-close failures: `0`;
- incidental existing Runtime proofs: `0`;
- remaining unrecognized URL-shaped keys: `contactlink`, `getreferrallink`,
  `ncdrejectbannerlinktext`;
- remaining unknown identity/job/title-shaped fields were UI/content/search/
  preference/opening-hours structures;
- six `title + location` mappings without identity/URL were office/contact
  structures rather than job records.

This evidence does not justify another parser alias, protocol adapter, interaction
rule, URL-less proof, or route reconstruction. Such a change would move from
observed generic evidence to heuristic recall chasing.

**Deterministic Runtime/parser acquisition is therefore evidence-exhausted for this
bound 40-case cohort at the current authority surface.**

## Exact residual after deterministic exhaustion

- `32` — `genoverband_e_v`;
- `33` — `x1f`;
- `35` — `msg_systems`;
- `45` — `bridgingit`;
- `47` — `commercetools`;
- `48` — `freenet_dls`;
- `52` — `prodyna`;
- `63` — `the_associated_engineers`;
- `72` — `bjak`.

## Relationship to booster admission and ML

The nine residual cases now move to the separate task-specific booster admission
path under Pipeline issue #522, `docs/reference/search-intelligence/booster_admission.md`,
and `src/search_intelligence/booster_admission.py`.

The deterministic campaign supplies a measured baseline and residual, but it does
not itself produce a positive booster-admission decision. The current admission
module requires one explicit `BoosterOpportunityEvidence` plus caller/operator-owned
`BoosterAdmissionPolicy` thresholds. It remains pure and always leaves provider
execution and Product authority false.

For this exact bound acquisition surface, repository evidence supports decision
volume `40` and deterministic residual rate `9/40 = 0.225`. It does **not** establish
surface-specific expected rescue rate, value per rescue, incremental provider cost,
fixed validation cost, problem-fit/evidence-quality/repeatability/operational-risk
scores, or product/operator thresholds. Those values must not be copied from test
fixtures or from the old origin-hypothesis empirical means in
`llm_booster_policy.py`.

The next provider-free step is therefore to materialize the measured admission
record with explicit unknowns and identify what evidence/policy is still needed
before calling `evaluate_booster_admission`. Only a genuinely admitted result may
proceed to a separately governed offline/shadow LLM/search smoke. Provider/search/
LLM output remains advisory and must still pass deterministic validation before
downstream authority.

The ML learning foundation remains parallel and is not redefined by acquisition
exhaustion.

## Hard boundaries after exhaustion

- no company-specific success branch;
- no weakening of final genuine-job/content proof;
- no provider/model result as authority;
- no guessed ATS token, endpoint, tenant, route, selector, board, site, or job ID;
- no reconstruction of unknown POST bodies;
- no URL-less job proof added merely to increase recall;
- no broadening of visible interaction merely to chase residual cases;
- no credential/token/cookie/form-value persistence;
- no raw Runtime response or HTML persistence by default;
- no DB/Product/source activation/application mutation in acquisition shadow work;
- no fabricated booster economics, fit/risk scores, rescue rates, or policy
  thresholds merely to force an admission result;
- new deterministic work requires genuinely new reusable external evidence, not a
  reinterpretation of the exhausted V34 surface.

## Current continuation

ACQ-RUNTIME-001 remains implemented and available as a bounded deterministic
acquisition layer, but active recall hardening for this cohort is closed. The next
safe repository action is the provider-free exact nine-case booster-admission
evidence record, while retaining `23/40` fresh static V4 and `31/40` accumulated
Runtime deterministic truth as separate metrics.
