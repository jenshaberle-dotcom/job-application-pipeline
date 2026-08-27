# V41 Manual Hardening While Runtime CI Is Unavailable

Status: active manual hardening note; no acquisition authority change  
Date: 2026-08-27  
Canonical re-entry: `reentry001b_deterministic_v41_frontier.md`

## Purpose

Runtime self-hosted CI is temporarily unavailable. This note records only work that
can be prepared without creating new acquisition evidence or weakening the existing
proof boundary.

Authoritative acquisition truth remains:

- static default control: `23/40`;
- accumulated bounded Runtime deterministic truth: `33/40` strict proven;
- unresolved: `7/40`;
- latest successful acquisition evidence: V40 run `32977904600`;
- V41: diagnostic-only and not yet acquisition evidence.

## Manual slice 1 — pin the pre-V41 parser boundary

`tests/test_runtime_network_v41_frontier.py` records the exact safe precondition for
V41-derived parser work:

- normalized Bjak-observed field names `applylink` and `externallink` do not currently
  grant candidate-URL authority;
- a strongly job-shaped record may still be recognized as a hypothesis, but without a
  supported URL key it must have an empty `candidate_url`;
- consequently `runtime_job_record_proof` must fail closed;
- the already-supported `applyurl` contract remains distinct and continues to produce
  the existing runtime proof when all other authority checks pass.

This test intentionally does **not** add `applylink` or `externallink` to `URL_KEYS`.
That change remains blocked until V41 produces value-shape evidence proving reusable
generic URL semantics.

## Manual slice 2 — stale reference-document finding

`docs/reference/search-intelligence/runtime_network_acquisition.md` still describes
V34 as deterministic exhaustion at `31/40` with nine residual cases. That statement
is historical and stale after V37/V38/V40.

Current continuation authority is REENTRY-001B, which records V40 at `33/40` with
seven residuals and V41 as the next bounded diagnostic frontier.

Do not use the stale V34 exhaustion paragraph to admit the current seven-case residual
to the booster layer.

A later documentation reconciliation should preserve the V34 section as historical
evidence while moving its status/continuation text to the current V40/V41 frontier.

## Manual slice 3 — query-value sanitization finding

`src/search_intelligence/runtime_network_acquisition.py::sanitize_url` currently
redacts only values whose query keys look secret-like. Other query values remain in
the returned sanitized URL; the existing unit test explicitly preserves
`tenant=acme`.

REENTRY-001B and current Runtime campaign boundaries are stricter: persisted campaign
evidence must not contain query values.

This is a real boundary-drift candidate, but it must **not** be patched by simply
redacting every value without call-site analysis. `JobPayloadCandidate.candidate_url`
uses the same sanitizer and may be consumed transiently for exact observed candidate
navigation. Destroying required query values could therefore break deterministic
replay while appearing to improve persistence safety.

Required follow-up before code change:

1. separate transient executable URL from persistable URL shape if necessary;
2. identify every persistence boundary that serializes `NetworkObservation` or
   `JobPayloadCandidate`;
3. ensure persisted forms retain query keys only, never values;
4. keep exact observed query-bearing URLs available only transiently when execution
   genuinely requires them;
5. add positive persistence tests and negative replay-regression tests before changing
   the sanitizer contract.

## Manual test gate

Because the branch changes only tests/documentation, the first manual gate is:

```bash
python -m pytest -q tests/test_runtime_network_v41_frontier.py tests/test_runtime_network_acquisition.py tests/test_runtime_network_absolute_url.py
```

Then run the repository's normal fast/full deterministic gates before any merge.

Until those gates pass, this branch is preparation only. No campaign truth changes.
