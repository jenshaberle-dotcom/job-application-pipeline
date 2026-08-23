# ML Learning Foundation Lane

Status: active parallel foundation lane
Authority: `docs/reference/search-intelligence/ml_learning_layer.md`  
Kaggle execution contract: `docs/reference/search-intelligence/ml_kaggle_execution_contract.md`  
Branch: `feature/ml-learning-foundation`

## Purpose

Build the ML path in small, independently mergeable slices while deterministic Search Intelligence and the LLM booster continue to mature.

The branch is intentionally long-lived but must be fast-forwarded to current `main` after each accepted slice so it does not become a parallel source of truth.

## Delivery rhythm

Each slice should be small enough to merge independently after normal CI:

```text
feature/ml-learning-foundation
-> small foundation slice
-> focused unit tests
-> full repository CI
-> merge to main
-> fast-forward feature branch to new main
-> next slice
```

## Progress

- MLF-001 merged: pure foundation contracts and tests.
- MLF-002 merged: deterministic dataset manifest serialization and fingerprinting.
- MLF-003 merged: read-only DB-backed snapshot planning boundary.
- MLF-004 merged: Kaggle transport, CPU validation, telemetry and checkpoint re-entry contracts; no external execution.
- No provider/GPU execution slice is activated; GPU use remains an explicit operator boundary.

## Initial slices

1. **MLF-001 — pure foundation contracts and tests**
   - protect development vs runtime ordering;
   - define reproducible training-dataset provenance minimums;
   - enforce non-authoritative Shadow ML signals;
   - define conditional LLM residual-routing reasons;
   - no DB, provider, Kaggle or product execution.

2. **MLF-002 — dataset manifest serialization**
   - deterministic JSON manifest;
   - schema/version validation;
   - content fingerprinting;
   - fixtures and round-trip tests;
   - still no live DB export.

3. **MLF-003 — DB-backed snapshot planning boundary**
   - read-only `silver_jobs` query/snapshot plan;
   - explicit selected columns and feature/provenance roles;
   - evidence-cutoff semantics over `normalized_at`, `created_at`, and `updated_at`;
   - duplicate grouping by canonical key with normalized fallback metadata;
   - leakage controls that exclude labels and future outcomes;
   - deterministic plan fingerprint for later transport traceability;
   - dry-run only before any Kaggle transport integration.

4. **MLF-004 — Kaggle experiment transport and observability contract**
   - generated training-package manifest with per-entry checksums and safe transport names;
   - local/CI CPU validation gate for package integrity and contract checks;
   - hard fail-closed GPU/operator boundary: no Kaggle upload, kernel execution or accelerator use;
   - returned-artifact metadata remains non-authoritative and binds producing package/code/compute;
   - PED-derived operational patterns: observer/lifetime separation, quota/status telemetry, bounded inaccessible-status failure, immutable run evidence and reuse of unchanged provider-capability proof;
   - epoch/checkpoint re-entry receipts with a verified resume-parent chain;
   - diagnostic failure classes and stable evidence fingerprints;
   - no model-family choice and no productive inference.

## Merge rule

A slice may merge to `main` when it is generic, side-effect-bounded, covered by focused tests, and passes the repository CI. The feature branch must then rejoin the resulting `main` before further work.

No slice in this lane may silently introduce ranking authority, Top-5 semantics, model-family selection, source activation, connector mutation or automatic application behavior.

GPU/provider execution is an explicit operator boundary. MLF-004 cannot self-authorize it through configuration, CI, a PR merge, a credential being present, or a previous project/provider proof.
