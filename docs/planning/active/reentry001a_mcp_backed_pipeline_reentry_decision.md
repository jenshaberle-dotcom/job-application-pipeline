# REENTRY-001A Job Application Pipeline Re-Entry Decision

Status: current repository re-entry; deterministic acquisition evidence-exhausted for bound cohort, booster admission evidence next  
Date: 2026-08-25  
Repository: `jenshaberle-dotcom/job-application-pipeline`  
Repository ID: `1230805345`  
Current Pipeline authority before this documentation refresh: `36972bf50c787ee291e3179d9b9fd86123dabd88`  
Current Runtime authority: `f763ea905a158e964f185beedaca05b17890f8c4`  
Boundary: repository and persisted Runtime evidence are project truth; chat is not project truth

## Purpose

This file is the canonical continuation point for the Job Application Pipeline.
The previous version stopped at V29 (`30/40` dynamic deterministic proven,
`10/40` unresolved). Repository truth has advanced through V34 and a fresh static
40-cohort regression proof.

The current acquisition state has two intentionally separate truths:

1. **Static default acquisition (fresh V4): `23/40` genuine-job proven, `17/40`
   blocked.** This is the unchanged static control and remains regression-free.
2. **Accumulated bounded Runtime deterministic acquisition: `31/40` strict proven,
   `9/40` unresolved.** This includes deterministic runtime/network evidence classes
   that are not present in the static V4 observation surface.

These values must not be added together and Runtime proof must not be confused with
Product admission. The Runtime browser remains an evidence sensor; Product/source/
application authority remains outside acquisition shadow work.

The deterministic acquisition campaign is now **evidence-exhausted for this bound
40-case cohort at the current authority surface**. The exact nine-case residual is
handed to task-specific booster admission under `LLM-BOOST-001`. The ML learning
foundation remains a parallel lane.

## Required reads

Before continuing from this point, authenticate repository ID `1230805345` and read:

1. this file completely;
2. Pipeline issue `#642` (`ACQ-RUNTIME-001`);
3. `docs/reference/search-intelligence/runtime_network_acquisition.md`;
4. Pipeline issue `#522` (`LLM-BOOST-001`);
5. `docs/reference/search-intelligence/booster_admission.md`;
6. `src/search_intelligence/booster_admission.py`;
7. `src/search_intelligence/llm_booster_policy.py`;
8. `docs/planning/active/ml_learning_foundation_lane.md`;
9. Runtime repository `jenshaberle-dotcom/job-pipeline-runtime`, issue `#203`;
10. Runtime issue #203 authoritative deterministic-closure comment `5414592644`;
11. authoritative V33 run `32880015344` and persisted evidence at branch
    `carrier/203-absolute-url-runtime-replay-v33-32880015344`, path
    `carriers/connector-absolute-url-runtime-replay-v33/32880015344/result.json`;
12. authoritative V34 run `32880929572` and persisted evidence at branch
    `carrier/203-nested-job-key-provenance-v34-32880929572`, path
    `carriers/connector-nested-job-key-provenance-v34/32880929572/result.json`;
13. fresh static V4 regression run `32881331391`, evidence branch
    `carrier/203-acquisition-proof-v4-32881331391`, path
    `carriers/connector-acquisition-proof-v4/32881331391/result.json`;
14. merged Pipeline PR `#656`, which adds only normalized `absoluteurl` to generic
    runtime URL recognition.

Earlier V25-V32 evidence remains historical support, but V33/V34 plus the fresh V4
run are the current continuation authority. Do not substitute assistant memory,
chat summaries, stale PR descriptions, or retired NEXT artifacts for these sources.

## Fresh static V4 control truth

Fresh V4 run `32881331391` evaluated exact Pipeline
`36972bf50c787ee291e3179d9b9fd86123dabd88` against the immutable 40-case static
cohort.

Result:

- input: `40`;
- static genuine-job acquisition proven: `23`;
- blocked: `17`;
- blocked reasons: `{"no_genuine_job_detail":17}`;
- logical network requests: `110`;
- shared-extra-request connectors: `12`;
- metered form connectors: `9`;
- request contract unchanged: base `3`, shared extra `1`, absolute max `4`;
- proof job: success;
- evidence publish: success;
- Product/job persistence: `0`.

The fresh run proves that the current Pipeline parser hardening did not regress or
silently broaden the static default path.

## Current dynamic deterministic truth

The accumulated bounded Runtime campaign is:

- V4 static control: `23/40`;
- deterministic rescues through V24: `+5`;
- V25 visible interaction: `+1` — candidate `37` / E.ON Grid Solutions;
- V26 interaction harness hardening: `+0`;
- V27 exact Personio public-feed inspection: `+0`;
- V28 canonical provider-root detail inspection: `+0`;
- V29 observed ATS listing replay: `+1` — candidate `40` / Compugroup Medical;
- V30 observed public-route replay: `+0`;
- V31 bounded oversized same-authorized jobish JSON inspection: `+0`;
- V32 structural provenance diagnostic: `+0` by construction;
- V33 `absolute_url` parser-blind-spot replay: `+1` — candidate `56` / Zscaler;
- V34 nested job-key provenance diagnostic: `+0` by construction;
- **current accumulated Runtime deterministic proven: `31/40`**;
- **current unresolved: `9/40`**.

### V31-V33 parser evidence

V31 exposed a same-authorized Zscaler `POST /api/get-greenhouse-jobs` response of
`2,568,911` bytes. The bounded recognizer found job-shaped records but could not
produce runtime proof because their URL field was not recognized.

V32 inspected structural provenance without persisting field values. It proved:

- top-level `jobs` contains `342` direct records;
- all `342` contain normalized keys `title`, `id`, `locations`, and `absoluteurl`;
- the then-current URL recognizer recognized `0/342` of those URL fields;
- all bounded recognized candidates had explicit `jobs`-container provenance;
- sibling `departments` and `locations` containers provided negative controls and
  contained no current title/identity/URL-key combination that could masquerade as
  job records.

Pipeline PR `#656` therefore made one minimal generic parser correction: normalized
`absoluteurl` was added to `URL_KEYS` only. It was deliberately **not** added to
`EXPLICIT_JOB_KEYS`; scoring thresholds, host/delegation semantics, Runtime proof
semantics, and final downstream authority were unchanged. Positive and negative
regressions keep `products[].absolute_url` fail-closed.

V33 replayed the exact prior Runtime surface with only that Pipeline parser delta.
Candidate `56` / Zscaler was rescued through the existing
`runtime_authorized_inventory_record` authority. The oversized response produced
`30` bounded candidates and `20` existing runtime proofs at score `8`, with observed
delegated host `job-boards.greenhouse.io`. No URL-less proof or new host/proof rule
was introduced.

### V34 exhaustion evidence

V34 was a diagnostic-only final parser-surface inspection over the exact V33
nine-case residual. It credited zero rescues by construction.

Findings:

- only `4` residual cases / `7` already-observed seeds remained replay-eligible;
- five residual cases had no admissible seed on this deterministic surface;
- `3` same-authorized jobish JSON structural events were inspected;
- diagnostic failures: `0`;
- response-drain timeouts: `0`;
- context-close failures: `0`;
- incidental existing Runtime proofs: `0`;
- remaining unrecognized URL-shaped keys were `contactlink`, `getreferrallink`, and
  `ncdrejectbannerlinktext`;
- remaining identity/job/title-shaped keys were UI/content/search/preferences/
  opening-hours labels;
- six `title + location` structures without identity/URL were office/contact
  structures, not job records.

No reusable parser/protocol gap remains without guessing semantics, inventing
routes/IDs, broadening interaction heuristics, reconstructing requests, or weakening
proof. Those moves are outside deterministic evidence authority.

## Exact unresolved residual

The nine cases handed forward are:

- `32` — `genoverband_e_v`;
- `33` — `x1f`;
- `35` — `msg_systems`;
- `45` — `bridgingit`;
- `47` — `commercetools`;
- `48` — `freenet_dls`;
- `52` — `prodyna`;
- `63` — `the_associated_engineers`;
- `72` — `bjak`.

This residual is not evidence that deterministic proof should be weakened. It is the
input set for the next residual layer.

## Deterministic authority and hard boundaries

ACQ-RUNTIME-001 remains the deterministic Runtime contract:

```text
authorized public career/listing page
-> bounded browser observation
-> optional bounded visible listing interaction
-> transient structured response
-> generic runtime payload recognition
-> runtime job-record proof
-> bounded observed inventory/delegated-host authority where proven
-> unchanged downstream authority
```

Keep the following boundaries:

- no company-specific success branch merely to increase recall;
- no guessed ATS token, tenant, endpoint, selector, route, board, site, or job ID;
- no reconstruction of unknown POST bodies;
- no widening of visible-click semantics merely to chase the nine residuals;
- no URL-less job authority introduced from weak structured records;
- no weakening of final genuine-job/content proof;
- provider detection or historical observation alone is never authority;
- no model/provider output as Product truth;
- no raw HTML/API/XML body, credential, cookie, header, form value, request body, or
  secret persistence;
- no DB/Product/source activation/scheduler/application mutation in acquisition
  shadow work;
- ambiguous evidence fails closed.

## Booster handoff

Pipeline issue `#522`, `docs/reference/search-intelligence/booster_admission.md`,
`src/search_intelligence/booster_admission.py`, and
`src/search_intelligence/llm_booster_policy.py` are now the next residual authority.

The current admission code evaluates one explicit task-local surface using
`BoosterOpportunityEvidence` and caller/operator-owned `BoosterAdmissionPolicy`
thresholds. It does **not** contain a synthetic `deterministic_exhausted` switch and
it does not authorize provider execution.

Facts established by the deterministic campaign for the candidate acquisition
surface are:

- deterministic baseline is measured;
- bound decision volume is `40`;
- current accumulated deterministic residual is `9/40 = 0.225`;
- the exact residual identities are listed above;
- observability and deterministic downstream authority boundaries exist in the
  repository.

The campaign does **not** by itself establish safe numeric values for:

- expected LLM/search rescue rate on this exact nine-case post-V34 residual;
- expected value per rescued acquisition;
- surface-specific incremental provider/search cost;
- fixed validation/operational setup cost;
- problem-fit/evidence-quality/repeatability/operational-risk scores;
- operator/product admission thresholds.

Those inputs must not be invented from old origin campaigns or test fixtures. The
empirical costs in `llm_booster_policy.py` are explicitly planning observations for
a different compact origin-hypothesis prompt family and require per-surface smoke
evidence before promotion.

A positive `BOOSTER-ADMISSION-001` result means only that offline/shadow evidence is
worth collecting. `execution_authorized` and `product_authority` remain false.
Provider/search/LLM output remains advisory and any candidate must still pass
deterministic validation/proof before downstream authority.

## ML boundary

`docs/planning/active/ml_learning_foundation_lane.md` remains parallel. Runtime
acquisition exhaustion neither replaces nor demotes the ML lane. Learned scoring may
only influence decisions where its own evidence contract admits it; it does not
retroactively redefine acquisition truth.

## Sole next safe action

Build a **provider-free nine-case LLM booster-admission evidence record** for the
explicit post-V34 acquisition residual:

1. bind it to Pipeline `36972bf50c787ee291e3179d9b9fd86123dabd88`, Runtime
   closure V33/V34, fresh V4 `32881331391`, and the exact nine residual identities;
2. record only the measured common admission inputs that repository evidence already
   supports (`baseline_measured=True`, decision volume `40`, deterministic residual
   rate `0.225`, explicit authority boundary and evidence provenance);
3. explicitly represent every still-unknown admission/economic input rather than
   substituting fixture thresholds or old origin-model means;
4. classify what additional **provider-free** evidence or explicit operator/product
   policy is required to complete those unknown inputs;
5. do **not** call `evaluate_booster_admission` with fabricated numbers and do not
   infer an admitted result while required policy/evidence inputs are unknown;
6. once all required evidence and policy thresholds are genuinely supplied, evaluate
   `BoosterOpportunityEvidence` through the existing pure admission module; only an
   admitted result may proceed to a separate surface-specific offline/shadow smoke;
7. no Tavily/OpenAI/provider call is authorized by this handoff. Existing
   LLM-BOOST-001 budget/search-first/replay/validation gates remain separately
   authoritative if a later shadow is admitted.

Do not return to more acquisition heuristics unless new external evidence creates a
new generic deterministic class. Do not start paid booster execution merely because
the nine-case handoff exists.

## Re-entry status

Repository work is active. Deterministic acquisition is **closed/evidence-exhausted
for the bound cohort**. Fresh static truth is `23/40`; accumulated bounded Runtime
deterministic truth is `31/40`; exact residual is `9/40`.

The sole next safe action is the provider-free nine-case `BOOSTER-ADMISSION-001`
evidence record above.
