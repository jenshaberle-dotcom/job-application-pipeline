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

## Manual slice 3 — query-value persistence review

`src/search_intelligence/runtime_network_acquisition.py::sanitize_url` currently
redacts only values whose query keys look secret-like. Other query values remain in
the returned in-memory URL and the existing unit test explicitly preserves
`tenant=acme`.

At first inspection that looked inconsistent with the current campaign boundary
`query_values_persisted=false`. Runtime call-site review shows that the active
campaign persistence layer applies an additional, stricter projection:

- `run_connector_runtime_authority_shadow_v18.py::public_candidate_url` persists
  candidate identity as HTTPS scheme/host/path only, removing query and fragment;
- Runtime request/response/page evidence is persisted through `url_shape` / `url_meta`
  structures that retain query *keys* only, never values;
- V31 and V40 inherit those persistence projections while using the Pipeline candidate
  URL transiently for recognition/proof.

Therefore **no current V18/V31/V40 query-value evidence leak is proven** and no
sanitizer patch is justified from this review alone.

The naming/API contract is still worth future cleanup because `sanitize_url` means
"secret-value redaction", not "safe-for-all-persistence". A future refactor may split
transient executable URL normalization from persistable URL-shape projection, but it
must preserve exact observed query-bearing URLs transiently when deterministic replay
requires them.

No code change is authorized by this finding during the current V41 frontier.

## Manual test gate

Because the branch changes only tests/documentation, the first manual gate is:

```bash
python -m pytest -q tests/test_runtime_network_v41_frontier.py tests/test_runtime_network_acquisition.py tests/test_runtime_network_absolute_url.py
```

Then run the repository's normal fast/full deterministic gates before any merge.

Until those gates pass, this branch is preparation only. No campaign truth changes.
