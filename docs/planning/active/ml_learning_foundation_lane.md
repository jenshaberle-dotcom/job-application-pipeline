# ML Learning Foundation Lane

Status: active parallel foundation lane
Authority: `docs/reference/search-intelligence/ml_learning_layer.md`  
Booster admission contract: `docs/reference/search-intelligence/booster_admission.md`  
Kaggle execution contract: `docs/reference/search-intelligence/ml_kaggle_execution_contract.md`  
Snapshot materialization contract: `docs/reference/search-intelligence/ml_snapshot_materialization_contract.md`  
First pilot design: `docs/reference/search-intelligence/ml_pilot_job_fit.md`  
Operator label evidence: `docs/reference/search-intelligence/operator_review_label_contract.md`  
Branch: `feature/ml-learning-foundation`

## Purpose

Build the ML path in small, independently mergeable slices while deterministic Search Intelligence and the LLM booster continue to mature.

ML is treated as an optional task-specific booster capability, parallel in governance to the LLM booster. It is not a mandatory stage to insert across the complete pipeline. New ML surfaces are admitted only where a measured deterministic residual and expected incremental value justify further evaluation.

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
- MLF-005 implementation merged via PR #626 / merge `12407fbf95e6e3cb3e5c4b497dfd440e1beb0395`: real read-only Silver materialization into an immutable local package with on-disk CPU validation.
- MLF-005 live local DB package proof is still pending; implementation/CI success must not be reported as live-data evidence.
- `BOOSTER-ADMISSION-001` merged via PR #630: ML and LLM are task-local optional boosters admitted by measured residual value, not mandatory serial pipeline layers.
- `ML-PILOT-001A` merged via PR #631 / merge `26e074ee5d7449567d9f0af8c063de4f8d9b07ff`: append-only `operator_review_relevance` label evidence with historical job-evidence fingerprints, sampling reason and signal-exposure provenance. Label collection may begin before MLF-005 proof; supervised dataset/split construction and model training may not.
- `ML-PILOT-001B` merged via PR #634 / merge `0241426929af5202a52da0436cad6e87981efeea`: one-click Product V1 Control Center capture for `interesting`, `not_relevant`, and `unsure`, with exact server-owned Silver evidence fingerprinting, DB readback, idempotence on unchanged evidence, and append-only superseding corrections. Repository implementation/CI are complete; one-shot read-only runtime DB migration status proof is pending before claiming the local capture path operational.
- No provider/GPU execution slice is activated; GPU use remains an explicit operator boundary.

## Booster strategy

`BOOSTER-ADMISSION-001` governs where additional ML or LLM capability is worth evaluating.

The development rule is:

```text
bounded decision surface
-> strongest deterministic baseline
-> measured residual
-> task-specific ML/LLM admission evidence
-> rank viable opportunities by expected incremental net value
-> evaluate the strongest surface first
```

A booster that wins on one surface does not become a mandatory stage on adjacent surfaces. Admission is shadow-only and never authorizes training/provider execution or product authority.

The first planned ML value surface remains `job_review_relevance`, with ranking as a later adjacent surface only if evidence supports it. Existing LLM booster surfaces remain independently governed by `LLM-BOOST-001`.

## MLF-005 live-proof gate

The sole remaining proof for MLF-005 is one operator-local execution against the real PostgreSQL Silver state from a clean checkout of current `main`:

```bash
python -m scripts.materialize_ml_training_snapshot \
  --evidence-cutoff <EXPLICIT_TIMEZONE_AWARE_CUTOFF>
```

Acceptance requires the command to complete without DB writes and to produce a local immutable package below ignored `.runtime/ml-training-packages/` whose receipt proves:

- non-zero Silver row count;
- `compute_class=cpu_validation`;
- `external_execution=false`;
- `product_authority=false`;
- source-snapshot, dataset-manifest, snapshot-plan and package fingerprints;
- explicit evidence cutoff;
- successful on-disk package validation.

The package bytes and job rows must remain local. Do not upload them to GitHub, Actions artifacts, chat, Kaggle or another provider as part of this proof. Repository truth may later record only the bounded aggregate receipt/fingerprints needed for re-entry.

A one-shot workflow, `.github/workflows/mlf005-live-db-proof.yml`, may satisfy this gate only when it runs on the registered `job-pipeline-runtime-linux` self-hosted runner, resolves the PASS RCC runtime context, authenticates and fast-forwards the persistent checkout to the exact triggering `main` SHA, executes the existing local-only materializer, and publishes only the allowlisted aggregate proof. The workflow is path-triggered only by its own addition/change so it does not become recurring ML execution.

The operator has explicitly allowed `ML-PILOT-001A/B` label evidence capture to start before this proof so useful ground truth can accumulate. This is not a waiver of MLF-005 for training: until the live proof exists, do not materialize supervised job/label datasets, create train/validation/test splits, or train a model from the collected labels. Do not activate provider/GPU execution.

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

5. **MLF-005 — read-only Silver materialization and local package proof**
   - execute the exact MLF-003 `silver_jobs` snapshot SELECT inside verified `REPEATABLE READ / READ ONLY`;
   - fail closed if PostgreSQL does not report read-only mode and the expected isolation level;
   - canonicalize exact selected rows to deterministic UTF-8 JSONL;
   - bind payload, cutoff, query, plan, product contract and exact clean Git revision through SHA-256 lineage;
   - generate MLF-002 dataset manifest plus MLF-004 package manifest;
   - keep the evidence snapshot explicitly unsplit and unlabeled;
   - write only below ignored local `.runtime/` by default;
   - validate staged bytes from disk before immutable atomic publication;
   - expose only aggregate source/null/grouping diagnostics in snapshot metadata;
   - no Kaggle upload, external execution, model family, model training or product inference.

6. **ML-PILOT-001A — operator review label evidence**
   - explicit `interesting`, `not_relevant`, `unsure` vocabulary;
   - only the first two map to binary supervised targets; unreviewed jobs never become negatives;
   - append-only corrections through superseding events;
   - bind reviewer, time, evidence cutoff and historical job-evidence SHA-256;
   - record normal/uncertainty/disagreement/exploration/tail/blind sampling reason;
   - record whether deterministic/ML/LLM signals were visible and any active ML artifact/score;
   - no training, ranking authority, Top-5 effect or application behavior.

7. **ML-PILOT-001B — Control Center label capture**
   - add one-click `interesting`, `not_relevant`, and `unsure` actions to the ordinary job-detail workflow;
   - browser submits only exact Silver job identity and label; server owns all provenance;
   - reload and fingerprint the exact canonical MLF Silver evidence projection at review time;
   - fail closed on missing migration, missing job, timestamp drift or evidence-schema drift;
   - project latest persisted label back into Product V1 read truth;
   - keep repeated identical label/evidence submissions idempotent;
   - append a superseding event for a changed decision/evidence state;
   - no model training, provider/GPU execution, ranking/Top-5/lifecycle/source/application mutation or product authority.

## First pilot training path after MLF-005

After the live proof, `ML-PILOT-001` may progress to supervised dataset/split implementation:

```text
explicit operator_review_relevance labels
-> deterministic feature projection
-> time/duplicate-safe split
-> deterministic baseline
-> logistic regression control
-> LightGBM binary classifier candidate
-> same-holdout comparison
-> shadow predictions only
```

The label collection contract does not authorize training before the live-proof gate and does not create ranking authority after it.

## Merge rule

A slice may merge to `main` when it is generic, side-effect-bounded, covered by focused tests, and passes the repository CI. The feature branch must then rejoin the resulting `main` before further work.

No slice in this lane may silently introduce ranking authority, Top-5 semantics, model-family selection, source activation, connector mutation or automatic application behavior.

GPU/provider execution is an explicit operator boundary. MLF-004/005 and ML-PILOT-001A/B cannot self-authorize it through configuration, CI, a PR merge, a credential being present, a generated local package, collected labels, or a previous project/provider proof.
