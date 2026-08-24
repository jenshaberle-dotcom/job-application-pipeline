# ACQ-RUNTIME-001 Runtime / Network Acquisition

Status: active implementation contract  
Date: 2026-08-24  
Authority: Pipeline issue #642  
Baseline: `main@9d463aebdf5c2618fe8a74a7964a863842fcb632`

## Why this layer exists

The current deterministic acquisition baseline is `23/40` genuine-job proven and
`17/40` blocked. All 17 blockers are `no_genuine_job_detail`. The fresh V16
residual matrix is not a collection of unrelated company failures: it contains
ATS/route evidence for 14/17, API/form evidence for 15/17, structured application
state for 11/17, and static-asset evidence for 15/17, while V14 finds zero safe
explicit GET job-API routes and V15 finds zero safe explicit job-link routes.

A bounded LLM-only detail-rescue campaign on the exact 17-case residual then ran
all four normal model stages and rescued `0/17` after 68 model requests. Only three
model-proposed URLs reached deterministic detail validation and none passed. Tavily
was skipped because current credit telemetry was unknown, so this campaign rejects
LLM-only URL guessing for this residual; it does not reject search retrieval.

The evidence supports a narrower diagnosis than "determinism is exhausted":
**static deterministic observability is exhausted for this cohort**. A modern
career application may create its inventory only after client execution, using
XHR/fetch/GraphQL/POST, tenant/session/locale state, pagination, or dynamically
constructed requests. Information that is absent from the observed static input
cannot be recovered by another parser or by more reasoning over the same input.

## Target flow

```text
career/listing page
    -> bounded browser execution
    -> network observation
    -> structured response recognition
    -> job-object hypotheses
    -> deterministic host/source authority
    -> candidate detail fetch
    -> unchanged genuine_job_detail_proof
```

The browser is an observation mechanism, not an authority mechanism.

## Layer boundaries

### Static acquisition

The existing `employer_origin_acquisition` layer remains unchanged. Its current
request budget, host authority and `genuine_job_detail_proof` remain authoritative.
Runtime/network acquisition is an additional shadow evidence source after a
static miss, not permission to weaken static gates.

### Runtime observation

A future browser adapter may observe only bounded public application traffic. The
persistable observation contract must omit headers, cookies, credentials, tokens,
form values and raw response bodies. Secret-like URL query values are redacted.
The initial browser slice is passive: load, wait within an explicit time bound,
observe structured traffic, stop.

Generic interactions such as a ranked `jobs` / `search jobs` / `open positions`
control or one bounded pagination/load-more action are later slices and require
cross-company evidence. No company-specific click rule is authorized.

### Job-payload recognition

`src/search_intelligence/runtime_network_acquisition.py` owns the pure recognizer.
It receives one transient structured payload plus sanitized observation metadata
and emits bounded `JobPayloadCandidate` hypotheses. It does not perform browser,
network, provider, database, Product, lifecycle or source writes.

Recognition is intentionally provider/company agnostic. A candidate requires a
title plus identity or URL and at least one job-specific context signal:

- an explicit job/requisition/position field name; or
- location under a job/position/requisition/vacancy/career container path.

Generic objects that happen to contain `title + id + url + location` are rejected
when they have no job context. This prevents the recognizer from treating product,
news or content cards as job inventory merely because their schema is similar.

Candidate URLs may be emitted as hypotheses when the payload observed them, but
the record separately states whether the URL host is already authorized. An
unbound cross-host URL is never promoted to authority by the recognizer.

### Final detail authority

A recognized job object is not a genuine-job proof. The existing deterministic
source/employer binding must authorize any candidate fetch, and the fetched page
must still pass the unchanged `genuine_job_detail_proof`. Ambiguous evidence fails
closed.

## Slice sequence

### Slice 1 — pure recognition foundation

- immutable observation/candidate/result records;
- secret-like query redaction;
- bounded JSON traversal;
- generic job-context scoring;
- cross-host authority flag;
- positive, negative, adversarial and traversal-bound tests;
- zero external side effects.

### Slice 2 — Runtime browser shadow

After exact-head Slice-1 CI:

1. implement a thin Playwright/CDP-equivalent Runtime adapter;
2. run the exact 17 residuals read-only;
3. keep raw payloads in memory only;
4. persist only sanitized metadata, recognizer candidates and aggregate counts;
5. fetch only candidates that pass the existing host-authority boundary;
6. validate with the unchanged V4 genuine-job proof;
7. report incremental lift against the frozen `23/40` baseline.

### Slice 3 — promote reusable protocols, not company exceptions

Cross-company browser evidence may justify stable ATS-family protocol adapters
(Workday, Personio, d.Vinci, JOIN, or others) or generic interaction rules. A
provider-family adapter is acceptable only when the protocol is supported by
repeatable evidence across tenants; provider detection alone does not authorize
an invented endpoint.

The intended optimization path is:

```text
unknown dynamic site -> browser observation -> protocol evidence
known protocol later -> direct deterministic adapter -> browser fallback only on drift
```

## Relationship to LLM/search and ML

Search remains useful when an external index already knows a concrete public job
URL that the source application does not expose statically. The canonical booster
policy still treats search as retrieval and model outputs as hypotheses only.

LLMs should be used after runtime evidence exists for genuinely unknown semantics,
for example to rank which of several observed structured endpoints is likely to
carry job inventory. They should not be asked to invent current URLs from sparse
static evidence.

The ML learning lane is independent and remains active. Runtime acquisition does
not replace, demote or modify ML work.

## Hard boundaries

- no company-specific success branch;
- no weakening of `genuine_job_detail_proof`;
- no provider/model result as authority;
- no credential/token/cookie/form-value persistence;
- no raw runtime response persistence by default;
- no DB/Product/source activation/application mutation in shadow discovery;
- bounded execution and explicit failure/truncation state;
- any default-path promotion requires tests plus a new 40-case V4 proof and fresh
  residual gate.
