# ML Learning Foundation Lane

Status: active parallel foundation lane
Authority: `docs/reference/search-intelligence/ml_learning_layer.md`
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
   - read-only query/snapshot plan;
   - explicit selected columns and provenance;
   - leakage and duplicate-grouping metadata;
   - dry-run only before any Kaggle transport integration.

4. **MLF-004 — Kaggle experiment transport contract**
   - generated training package + manifest;
   - artifact metadata contract;
   - no model-family choice;
   - no productive inference.

## Merge rule

A slice may merge to `main` when it is generic, side-effect-bounded, covered by focused tests, and passes the repository CI. The feature branch must then rejoin the resulting `main` before further work.

No slice in this lane may silently introduce ranking authority, Top-5 semantics, model-family selection, source activation, connector mutation or automatic application behavior.
