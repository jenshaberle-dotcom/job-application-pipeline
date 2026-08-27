# REENTRY-001B Job Application Pipeline — Deterministic V41 Frontier

Status: current canonical repository re-entry; clean V41 diagnostic complete, URL-key parser follow-up next  
Date: 2026-08-27  
Repository: `jenshaberle-dotcom/job-application-pipeline`  
Repository ID: `1230805345`  
Pipeline main before this refresh: `cc4ba91c50bbc2111eecd720d22c47e0b5ec43ea`  
Runtime repository: `jenshaberle-dotcom/job-pipeline-runtime`  
Runtime control issue: `#203`  
Boundary: repository plus persisted Runtime evidence are project truth; chat and assistant memory are not project truth

## Purpose and supersession

This file remains the canonical continuation point after REENTRY-001A. REENTRY-001A
is historical evidence for the V37-V39 transition and must not be rewritten as if
those states never existed.

The previous state in this file is now stale in two places:

1. V41 is no longer blocked by the missing Chromium host libraries for manual
   execution; the runner-local dependency overlay was proven locally.
2. The V41 request-method defect (`POST` vs authoritative V40 `GET`) was isolated,
   corrected as a one-line local diagnostic patch, and the same exact V41 lineage
   then completed cleanly.

CI structure remains disturbed. Until that separate infrastructure problem is fixed,
bounded campaign tests may run manually from isolated worktrees with exact immutable
refs and the same fail-closed contracts. CI/startup failures and failed manual
technical attempts remain non-evidence.

## Current acquisition truth — unchanged

Two controls remain intentionally separate:

1. **Static default acquisition control: `23/40` genuine-job proven.**
2. **Accumulated bounded Runtime deterministic acquisition: `33/40` strict proven,
   `7/40` unresolved.**

Do not add these values together.

The latest successful authoritative acquisition evidence is still **V40 run
`32977904600`**. V41 is diagnostic-only and credits zero rescues by construction, so
its clean result does **not** change `33/40`.

## Authoritative V40 binding

V41 remains bound to:

- Pipeline acquisition snapshot: `4ada550e4a0ec0d84b62217528408e6e3d8b2956`;
- Runtime V40 run: `32977904600`;
- V40 result branch: `carrier/203-runtime-network-residual-v40-32977904600`;
- V37 / V38 / V39 lineage: `32971101384 / 32973049347 / 32974128089`;
- residual IDs: `[33, 45, 47, 48, 52, 63, 72]`;
- V40 effective strict proof: `33/40`;
- V40 strict rescues: `0`;
- V40 diagnostic failures: `0`.

V40 exposed candidate `72 / bjak`: the browser emitted an XHR `GET` request to
`be.bjak.my/career/api-v1/get-all-jobs`; the current generic recognizer saw structured
job records but had no recognized candidate URL because normalized fields
`applylink` and `externallink` were outside `URL_KEYS`.

## V41 execution history and method-contract repair

Earlier V41 attempts were technical non-evidence:

- run `32982443750`: skipped;
- run `32983583479`: Chromium could not launch because the Linux host lacked
  `libnspr4`, `libnss3`, and `libasound2t64`;
- Runtime PR `#352`, head
  `1c19f434a1e8c64e9c941df6b7e19ed92118452f`, introduced a runner-local dependency
  overlay candidate without `sudo`, package installation, or system mutation;
- run `32985119975`: GitHub Actions `startup_failure` before job execution.

Manual exact-ref execution on 2026-08-27 proved the dependency overlay itself works:
Playwright `1.55.0` installed, Chromium downloaded, the three libraries were extracted
locally, and a blank Chromium smoke passed.

The first manual V41 engine execution then returned
`diagnostic_execution_failure_count=1` and `target_response_count=0`. Repository/V40
comparison proved a deterministic implementation defect: V40 persisted the exact
Bjak target as `GET`, while V41 hard-filtered the same host/path to `POST`.

The local diagnostic worktree was restored to exact Runtime head and then changed by
exactly one line, `POST -> GET`. A byte-for-byte comparison proved that this was the
only V41-script delta before rerunning the same bound lineage.

## Clean manual V41 diagnostic result

The corrected manual V41 diagnostic completed cleanly:

```text
target_response_count=1
navigation_failure_count=0
diagnostic_execution_failure_count=0
job_records_with_target_field=228
records_with_https_resolvable_target=228
strict_v41_rescue_count=0
effective_strict_proven_count=33
remaining_unresolved_count=7
```

For **both** normalized fields, `applylink` and `externallink`, all `228/228` inspected
job records had the same bounded shape:

```text
present=228
absolute_https=228
query_present=0
null=0
empty_string=0
relative/root-relative/path-like=0
resolved_response_host=0
resolved_existing_authorized_host=0
resolved_other_host=228
```

No raw field values were persisted. This is strong evidence that both names have
reusable URL semantics. It is **not** host authority and it is not acquisition proof.

## Host/proof boundary after V41

Current `runtime_network_acquisition.py` remains deliberately exact-host/fail-closed:

- `_allowed_host()` accepts only exact normalized host membership;
- recognition may emit a sanitized HTTPS `candidate_url` while independently marking
  `host_authorized=False`;
- `runtime_job_record_proof()` requires an authorized employer page plus a strong
  candidate;
- a cross-host candidate can be proven when the response host is already authorized;
- otherwise the candidate host must exactly equal the response host;
- unrelated third-party response -> third-host delegation fails closed;
- one-hop candidate-host delegation occurs only after Runtime proof succeeds.

For the V40 Bjak case, existing authorized hosts are `bjak.my` and
`my.jobstreet.com`, while the target response host is `be.bjak.my`. Exact-host matching
therefore does not automatically authorize that response. V41 also classified all
observed target URLs as `other_host`, not response-host or already-authorized-host.

Consequently, adding the two URL aliases alone must **not** grant host/proof authority
and is not expected to manufacture a rescue. The next replay must measure that rather
than assume it.

## Next parser change authorized by V41

V41 now supplies the missing semantic evidence. The smallest reusable Pipeline change
is authorized:

- add normalized `applylink` to `URL_KEYS`;
- add normalized `externallink` to `URL_KEYS`;
- do **not** add either key to `EXPLICIT_JOB_KEYS`;
- do not change scoring except the existing generic URL-key scoring naturally taking
  effect;
- do not change `_allowed_host`, page/response authority, Runtime proof, delegation,
  Product/source/application authority, request budgets, interaction rules, or
  persistence rules.

This follows the existing `absoluteurl` precedent: evidence-backed URL vocabulary may
be extended without allowing the field name alone to make an object a job.

After the parser delta, run an exact replay on the V41/V40 Bjak surface. The replay
must report candidate/proof/delegation behavior under unchanged authority. A clean
zero-rescue result is valid evidence if the execution itself is complete; a technical
failure is not.

## Temporary CI/manual execution policy

Until CI structure is repaired:

- manual tests only from isolated worktrees and exact refs;
- retain all static, binding, boundary and output assertions;
- no queued/cancelled/startup-failed/skipped CI run becomes acquisition evidence;
- no carrier churn merely to test scheduler health;
- no host system package mutation for browser support;
- PR `#352` merge policy remains separate from the deterministic campaign;
- persist technical checkpoints in Runtime issue `#203`;
- preserve `33/40` until a genuine strict proof is produced.

## Exact unresolved residual

- `33` — `x1f`;
- `45` — `bridgingit`;
- `47` — `commercetools`;
- `48` — `freenet_dls`;
- `52` — `prodyna`;
- `63` — `the_associated_engineers`;
- `72` — `bjak`.

## Hard boundaries

- no company-specific success branch merely to increase recall;
- no guessed ATS token, tenant, endpoint, selector, route, board, site or job ID;
- no reconstruction of unknown POST bodies or query values;
- no generic click/scroll broadening after the already-closed interaction class;
- no registrable-domain inference as host authority;
- no URL-less inventory proof;
- no weakening of final genuine-job/content proof;
- field names, provider recognition and structural grouping alone are never Product/job
  authority;
- raw HTML/API/XML/JSON bodies, headers, cookies, tokens and request bodies are not
  persisted;
- no DB/Product/source activation/scheduler/application mutation in acquisition shadow
  work;
- ambiguous evidence fails closed;
- technical failed runs are not zero-rescue acquisition evidence.

## Deterministic / booster / ML sequencing

Deterministic acquisition is still not evidence-exhausted because V41 proved a new
bounded generic URL-vocabulary repair and an exact replay is still outstanding.
Booster admission remains deferred until that parser surface and any *directly
evidenced* follow-up are closed.

Development order:

```text
deterministic hardening -> LLM booster engineering -> ML algorithm engineering
```

Productive decision order:

```text
deterministic -> ML algorithm -> booster
```

The ML learning-foundation lane may continue independently where it does not redefine
acquisition authority.

## Required reads for next handoff

1. this file;
2. Runtime issue `jenshaberle-dotcom/job-pipeline-runtime#203`;
3. Runtime PR `#352` and the V41 method-contract repair state;
4. V40 result `32977904600`;
5. Runtime `scripts/run_connector_bjak_url_field_shape_v41.py`;
6. `src/search_intelligence/runtime_network_acquisition.py`;
7. `tests/test_runtime_network_acquisition.py`;
8. `docs/reference/search-intelligence/runtime_network_acquisition.md`;
9. REENTRY-001A only for V37-V39 history;
10. `docs/planning/active/ml_learning_foundation_lane.md` for the parallel ML lane.

## Sole next safe action

**Implement only the evidence-backed `applylink` / `externallink` additions to
Pipeline `URL_KEYS` (not `EXPLICIT_JOB_KEYS`), protect the unchanged host/proof boundary
with regression tests, and execute the exact bounded Bjak replay manually while CI is
disturbed.**

Do not change host authority merely because V41 says the fields contain URLs.
Acquisition truth remains **33/40 strict proven, 7/40 unresolved** until the replay
produces genuine strict proof.
