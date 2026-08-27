# REENTRY-001B Job Application Pipeline — Deterministic V41 Frontier

Status: current canonical repository re-entry; deterministic acquisition active, V41 manual diagnostic continuation after CI disturbance  
Date: 2026-08-27  
Repository: `jenshaberle-dotcom/job-application-pipeline`  
Repository ID: `1230805345`  
Pipeline main before this refresh: `187fb989ef08674d24c66b99cee3d944cdbe2d54`  
Runtime repository: `jenshaberle-dotcom/job-pipeline-runtime`  
Runtime main: `7696918f17a3126f63f2ebc38486a3630effc7b7`  
Runtime control issue: `#203`  
Boundary: repository plus persisted Runtime evidence are project truth; chat and assistant memory are not project truth

## Purpose and supersession

This file is the canonical continuation point after REENTRY-001A.

REENTRY-001A remains historical evidence for the V37-V39 transition and must not be
rewritten as if those states never existed. Its former sole-next-action statement
(`V40 next`) is stale because V40 completed successfully and produced the current
repo-supported deterministic diagnostic frontier.

The previous 2026-08-26 version of this file is also partially stale: it treated the
next V41 step as blocked on a trustworthy GitHub Actions Chromium smoke. The operator
has now explicitly placed CI execution in a temporary disturbance mode and is running
the same contracts manually from isolated worktrees. CI/startup failures remain
infrastructure-only non-evidence; manual execution may advance deterministic diagnosis
only when exact refs, bindings and boundaries are preserved.

Current continuation authority is therefore:

1. this file for current frontier and stop/continue criteria;
2. Runtime issue `#203` for persisted campaign evidence and execution checkpoints;
3. immutable successful acquisition evidence runs for cohort truth;
4. current Runtime/Pipeline repository state for implementation truth;
5. operator-captured manual diagnostic output only as technical evidence until a
   durable repository checkpoint is persisted.

## Current truth — two intentionally separate controls

1. **Static default acquisition control remains `23/40` genuine-job proven.**
2. **Accumulated bounded Runtime deterministic acquisition is `33/40` strict proven,
   `7/40` unresolved.**

These values are separate controls and must not be added together.

The latest successful authoritative acquisition evidence is **V40 run
`32977904600`**. V41 has not yet produced acquisition evidence. Technical failures,
startup failures, skipped executions, CI disturbances and failed manual diagnostics
are not `+0` acquisition evidence.

## V40 — browser-triggered Runtime Network replay

V40 successfully executed the exact post-V39 residual replay:

- Runtime run: `32977904600`;
- Pipeline acquisition snapshot: `4ada550e4a0ec0d84b62217528408e6e3d8b2956`;
- V37 / V38 / V39 lineage: `32971101384 / 32973049347 / 32974128089`;
- page-surface cases: `4`;
- runtime-event cases: `3`;
- runtime events: `45`;
- inspected JSON responses: `19`;
- candidate cases: `1`;
- runtime recognition candidates: `30`;
- candidate case: `72 / bjak`;
- strict proofs: `0`;
- diagnostic failures: `0`;
- strict rescues: `0`;
- effective truth remains **`33/40`, residual `7/40`**.

V40 is valid clean zero-rescue evidence for the exact browser-triggered network replay
class it executed. It is not deterministic exhaustion because it exposed structured
Bjak records that the current generic recognizer could partially understand but could
not turn into URL-bearing proof candidates.

## Bjak signal and why V41 exists

The post-V40 inspection exposed a generic parser/protocol question around literal
record URL fields named `applylink` and `externallink`.

The current decision remains deliberately **not** to add those names to Pipeline
`URL_KEYS` from field names alone. A field name is not sufficient authority.

V41 is diagnostic-only. Its job is to classify the already-observed Bjak field shapes
without persisting raw values and answer whether the fields have reusable URL
semantics:

- null / empty;
- absolute HTTPS;
- relative;
- other;
- destination class: response host / already-authorized host / other host.

Only if the diagnostic proves genuine generic URL semantics may the smallest reusable
Pipeline parser change be considered, followed by exact replay under unchanged proof
authority.

## V41 execution history — technical non-evidence

V41 has not produced acquisition evidence yet.

Known technical attempts:

- run `32982443750`: skipped; no target execution; not acquisition evidence;
- PR `#351`, run `32983583479`: bindings and temporary Playwright/Chromium setup
  reached execution preparation, but Chromium could not launch because the
  self-hosted Linux host lacked `libnspr4`, `libnss3`, and `libasound2t64`; engine did
  not run; technical non-evidence;
- Runtime PR `#352`, head
  `1c19f434a1e8c64e9c941df6b7e19ed92118452f`, contains a runner-local dependency
  overlay candidate using exact Playwright `1.55.0`, `apt-get download`, local
  `dpkg-deb -x`, and `LD_LIBRARY_PATH`; it performs no `sudo`, no package installation
  and no system-package mutation;
- V41 smoke run `32985119975` ended in `startup_failure` before any job started;
- current-head Runtime identity retry `32984862438` later completed green on both
  Linux and Windows after RCC/runner recovery, proving that dispatch recovered at
  least once but not repairing the broader CI structure.

### Manual V41 continuation — 2026-08-27

Because CI structure is currently disturbed, the operator temporarily returned this
campaign to manual tests. The manual run used isolated detached worktrees and exact
refs:

- Runtime candidate head: `1c19f434a1e8c64e9c941df6b7e19ed92118452f`;
- Pipeline acquisition snapshot: `4ada550e4a0ec0d84b62217528408e6e3d8b2956`;
- V40 evidence branch: `carrier/203-runtime-network-residual-v40-32977904600`;
- V40 evidence run: `32977904600`;
- exact Playwright: `1.55.0`;
- browser dependency overlay: runner/local-user temporary extraction only.

The manual overlay smoke **passed**: Chromium downloaded and launched successfully
with the local `libnspr4`, `libnss3`, and `libasound2t64` overlay. This closes the
specific missing-host-library hypothesis as the current blocker for local execution.
It does not by itself authorize merge of PR `#352` while CI structure is disturbed.

The immediately following V41 engine run completed far enough to emit a result but
failed its diagnostic contract:

```text
input_residual_count=7
effective_strict_proven_count=33
remaining_unresolved_count=7
target_response_count=0
job_records_with_target_field=0
records_with_https_resolvable_target=0
field_stats={}
diagnostic_execution_failure_count=1
strict_v41_rescue_count=0
```

The post-run assertion failure is therefore expected and correct: a zero target
response is technical diagnostic failure, not clean zero-yield acquisition evidence.

## Newly evidenced V41 repository defect — request-method mismatch

Repository inspection after the manual failure exposed a deterministic V41 contract
bug:

- authoritative V40 evidence records the Bjak browser-emitted
  `be.bjak.my/career/api-v1/get-all-jobs` request as **`GET`**;
- V41 exact-head code filters that same host/path to **`POST`** before inspecting the
  response;
- therefore the current V41 implementation discards the exact V40-observed target and
  can naturally produce `target_response_count=0` even when the target response is
  present.

This mismatch is narrower and better evidenced than changing timeouts, adding
interaction, reconstructing request bodies or broadening endpoint discovery. The next
V41 correction must bind request method to the already persisted V40 observation
(`GET`) rather than guessing or accepting arbitrary methods.

No Pipeline parser change is authorized by this finding.

## Temporary CI/manual execution policy

Until the current CI-structure disturbance is repaired:

- do not use queued, cancelled, startup-failed or skipped GitHub Actions jobs as
  acquisition evidence;
- avoid generating carrier churn merely to probe scheduler health;
- execute bounded diagnostics manually only from isolated worktrees and exact refs;
- preserve the same static/binding/boundary checks used by CI;
- do not install/mutate host system packages for V41; retain the local overlay;
- do not merge Runtime PR `#352` merely because the local smoke passed; CI repair and
  merge policy are separate from the immediate deterministic campaign;
- persist a durable Runtime checkpoint once a corrected manual V41 result is clean;
- preserve **33/40 strict proven, 7/40 unresolved** until genuine strict proof exists.

## Exact unresolved residual

The current seven unresolved cases remain:

- `33` — `x1f`;
- `45` — `bridgingit`;
- `47` — `commercetools`;
- `48` — `freenet_dls`;
- `52` — `prodyna`;
- `63` — `the_associated_engineers`;
- `72` — `bjak`.

No V41 technical attempt changes this cohort.

## Hard boundaries

The ACQ-RUNTIME boundaries remain unchanged:

- no company-specific success branch merely to increase recall;
- no guessed ATS token, tenant, endpoint, selector, route, board, site or job ID;
- no reconstruction of unknown POST bodies or query values;
- no generic click/scroll broadening after the already-closed interaction class;
- no registrable-domain inference as host authority;
- no URL-less inventory proof;
- no weakening of final genuine-job/content proof;
- provider recognition, structural grouping, field names or historical observation
  alone are never Product/job authority;
- raw HTML/API/XML/JSON bodies, headers, cookies, tokens and request bodies are not
  persisted;
- no DB/Product/source activation/scheduler/application mutation in acquisition shadow
  work;
- ambiguous evidence fails closed;
- technical failed runs are not zero-rescue acquisition evidence.

## Deterministic / booster / ML sequencing

Deterministic acquisition is **not yet evidence-exhausted** because V40 exposed a new
bounded generic diagnostic question and the first V41 manual execution exposed a
narrow implementation mismatch before the diagnostic could observe its target.
Booster admission therefore remains deferred until the corrected V41-derived surface
and any directly evidenced follow-up are closed.

Development-order truth remains:

```text
deterministic hardening -> LLM booster engineering -> ML algorithm engineering
```

Productive decision-order truth remains:

```text
deterministic -> ML algorithm -> booster
```

The ML learning-foundation lane may continue independently where it does not redefine
acquisition authority.

## Required reads for the next chat / operator handoff

Authenticate the Pipeline repository ID and then read, in order:

1. this file completely;
2. Runtime issue `jenshaberle-dotcom/job-pipeline-runtime#203`, especially the V40 and
   V41 checkpoints;
3. Runtime PR `#352` and exact current head/status;
4. V40 run `32977904600` and its persisted result manifest, including the exact Bjak
   request method;
5. Runtime `scripts/run_connector_bjak_url_field_shape_v41.py` at the exact manual-test
   head;
6. `docs/reference/search-intelligence/runtime_network_acquisition.md`;
7. `src/search_intelligence/runtime_network_acquisition.py`;
8. REENTRY-001A only for V37-V39 historical context;
9. `docs/planning/active/ml_learning_foundation_lane.md` for the parallel ML lane.

Do not substitute chat summaries, assistant memory, stale PR descriptions or retired
NEXT artifacts for these sources.

## Sole next safe action

**Correct only the V41 target request-method contract from the stale hard-coded
`POST` assumption to the exact V40-observed `GET`, then rerun the same manual V41
lineage from isolated worktrees with Pipeline
`4ada550e4a0ec0d84b62217528408e6e3d8b2956` and V40 `32977904600`.**

Do not broaden methods, endpoints, hosts, interactions or request reconstruction. If
the corrected run captures exactly one target response and completes with zero
diagnostic failures, inspect only the persisted field-shape counts. Do not patch
`applylink` / `externallink` before that diagnostic evidence proves generic URL
semantics.

Acquisition truth at handoff remains **33/40 strict proven, 7/40 unresolved**.
