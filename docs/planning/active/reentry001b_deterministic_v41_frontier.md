# REENTRY-001B Job Application Pipeline — Deterministic V41 Frontier

Status: current canonical repository re-entry; deterministic acquisition active, V41 diagnostic pending infrastructure-stable execution  
Date: 2026-08-26  
Repository: `jenshaberle-dotcom/job-application-pipeline`  
Repository ID: `1230805345`  
Pipeline main before this refresh: `89a42d515d0e55d5967cbaa0c8b0f484e6bc440c`  
Runtime repository: `jenshaberle-dotcom/job-pipeline-runtime`  
Runtime main: `7696918f17a3126f63f2ebc38486a3630effc7b7`  
Runtime control issue: `#203`  
Boundary: repository plus persisted Runtime evidence are project truth; chat and assistant memory are not project truth

## Purpose and supersession

This file is the canonical continuation point after REENTRY-001A.

REENTRY-001A remains historical evidence for the V37-V39 transition and must not be
rewritten as if those states never existed. Its former sole-next-action statement
(`V40 next`) is now stale because V40 completed successfully and produced a new
repo-supported deterministic diagnostic frontier.

Current continuation authority is therefore:

1. this file for current frontier and stop/continue criteria;
2. Runtime issue `#203` for persisted campaign evidence and execution checkpoints;
3. immutable successful acquisition evidence runs for cohort truth;
4. current Runtime/Pipeline repository state for implementation truth.

## Current truth — two intentionally separate controls

1. **Static default acquisition control remains `23/40` genuine-job proven.**
2. **Accumulated bounded Runtime deterministic acquisition is `33/40` strict proven,
   `7/40` unresolved.**

These values are separate controls and must not be added together.

The latest successful authoritative acquisition evidence is **V40 run
`32977904600`**. V41 has not yet produced acquisition evidence. Technical failures,
startup failures, skipped executions and infrastructure interruptions are not `+0`
acquisition evidence.

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

The current decision is deliberately **not** to add those names to Pipeline
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
  overlay candidate using exact Playwright `1.55.0`, `$RUNNER_TEMP`, `apt-get
  download`, local `dpkg-deb -x`, and `LD_LIBRARY_PATH`; it performs no `sudo`, no
  package installation and no system-package mutation;
- V41 smoke run `32985119975` originally ended in `startup_failure` before any job
  started. A retry was later queued during runner recovery but had not yet delivered
  a trustworthy smoke result at the last repository check.

A current-head Runtime identity retry (`32984862438`) subsequently completed green on
both Linux and Windows after RCC/runner recovery. This proves that dispatch recovered
at least once on PR `#352`, but it does **not** substitute for the missing Chromium
smoke gate.

Therefore PR `#352` remains **OPEN / DO NOT MERGE** until the V41 Chromium smoke gate
executes normally and passes on the exact candidate head. After any host/WSL
maintenance, runner identity/readiness must be revalidated before treating queued
execution as meaningful.

## Current infrastructure pause

At this re-entry refresh the operator is completing host storage maintenance that may
intentionally stop WSL/Ubuntu and self-hosted runners, followed by a clean Windows /
WSL restart.

This is an **execution pause, not a campaign result**.

During the pause:

- do not create acquisition truth from queued, cancelled, startup-failed or interrupted
  jobs;
- do not generate additional campaign carriers merely to test scheduler health;
- do not merge Runtime PR `#352`;
- do not patch Pipeline `URL_KEYS` for `applylink` / `externallink`;
- preserve **33/40 strict proven, 7/40 unresolved**.

After host maintenance:

1. confirm WSL/Ubuntu health;
2. confirm `job-pipeline-runtime-linux` is GitHub `online`, not stale-busy, and carries
   label `job-pipeline-runtime-linux`;
3. confirm Runtime re-entry identity can execute normally;
4. execute/retry the exact-head V41 Chromium smoke on PR `#352`;
5. only if the smoke is green, reconsider merge of `#352`;
6. after merge, create one fresh execution-only V41 diagnostic carrier bound to
   Pipeline `4ada550e4a0ec0d84b62217528408e6e3d8b2956` and V40 `32977904600`;
7. inspect V41 field-shape evidence before any parser patch;
8. if generic URL semantics are proven, implement the smallest reusable parser
   extension and exact replay; otherwise close that class as clean zero-yield and
   continue only from newly evidenced deterministic signal.

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
bounded generic diagnostic question. Booster admission therefore remains deferred
until the V41-derived deterministic surface and any directly evidenced follow-up are
closed.

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
   V41 infrastructure checkpoints;
3. Runtime PR `#352` and exact current head/status;
4. V40 run `32977904600` and its persisted result manifest;
5. `docs/reference/search-intelligence/runtime_network_acquisition.md`;
6. `src/search_intelligence/runtime_network_acquisition.py`;
7. REENTRY-001A only for V37-V39 historical context;
8. `docs/planning/active/ml_learning_foundation_lane.md` for the parallel ML lane.

Do not substitute chat summaries, assistant memory, stale PR descriptions or retired
NEXT artifacts for these sources.

## Sole next safe action

**Finish the intentional host maintenance first.**

Then restore and prove runner health, obtain a green exact-head V41 Chromium smoke for
Runtime PR `#352`, and only then continue the exact V41 diagnostic lineage. Do not
patch `applylink` / `externallink` before diagnostic evidence proves generic URL
semantics.

Acquisition truth at handoff remains **33/40 strict proven, 7/40 unresolved**.
