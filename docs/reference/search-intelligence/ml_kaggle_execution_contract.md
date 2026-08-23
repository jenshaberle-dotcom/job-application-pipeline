# ML-KAGGLE-001 — Experiment Transport, Validation and Re-Entry Contract

Status: **MLF-004 foundation contract — no external execution authorized**  
Authority relationship: refines `ML-LEARN-001` for Kaggle-facing experiment preparation  
PED reference: operational lessons are reused as patterns, not copied as model- or dataset-specific authority

## 1. Purpose

This contract defines how the Job Application Pipeline prepares, validates, observes and later re-enters ML experiments without turning Kaggle, a notebook, a model artifact or an export file into project truth.

MLF-004 is deliberately an **execution-foundation slice**. It prepares contracts and CPU validation only. It does not submit a Kaggle dataset/kernel, start a notebook, request an accelerator, train a model or spend provider compute.

The repository and DB-backed pipeline remain the system of record. Generated transport packages and returned experiment artifacts are derived, checksummed evidence.

## 2. Compute authority boundary

The compute boundary is intentionally asymmetric.

### CPU validation

Local or CI CPU validation is allowed without a separate operator action when it is limited to deterministic contract checks such as:

- package manifest validation;
- schema/version checks;
- content SHA-256 verification;
- declared-file inventory checks;
- safe transport-name/path checks;
- dataset/plan/provenance binding checks;
- serialization and round-trip checks;
- telemetry/checkpoint contract validation;
- lightweight model-independent fixtures or future CPU baseline tests that do not invoke an external provider.

CPU validation must not silently upload a package, invoke Kaggle or switch to external execution.

### Kaggle upload and GPU execution

In MLF-004 all external provider execution remains disabled:

```text
external_upload_authorized = false
gpu_training_authorized = false
provider_credentials_in_repository = false
```

A GPU request is a hard operator boundary. It must fail closed until a future execution slice has both:

1. an **explicit operator authorization**; and
2. repository code that deliberately admits the exact authorized execution.

An authorization reference alone cannot make MLF-004 execute GPU work. CI success, a merged PR, an available Kaggle credential, an accelerator detected by a provider, or a previous PED authorization cannot grant Job-Pipeline GPU authority.

A future GPU authorization should bind at least the exact training-package fingerprint, experiment/run identity, intended compute class/provider, code revision and bounded purpose. It must not be interpreted as blanket permission for unrelated or later runs.

## 3. Training-package contract

A transport package is generated evidence, never source truth.

The package manifest binds:

- package identity;
- dataset-manifest fingerprint from MLF-002;
- snapshot-plan fingerprint from MLF-003;
- source-snapshot identity;
- feature-contract version;
- product-contract version;
- exact code revision;
- declared package files with role, size and SHA-256;
- transport platform and schema version.

Required logical roles are:

```text
dataset_payload
dataset_manifest
```

Optional snapshot metadata may accompany them. Package entries use safe flat transport filenames; path traversal or undeclared files fail closed.

The package fingerprint is distinct from both the MLF-002 dataset-manifest fingerprint and the MLF-003 snapshot-plan fingerprint. A later materializer must still establish the actual source/data snapshot identity rather than inferring it from the plan.

## 4. PED lessons deliberately carried forward

PED proved several operational patterns that are useful beyond pedestrian detection. Job Pipeline adopts the pattern while keeping its own datasets, features, model choices and authority.

### 4.1 Freeze identity before provider execution

Before a provider run can ever be admitted, the exact dataset/package, code revision and experiment contract must already be immutable and checksummed. A provider result is meaningful only when it can be traced back to those inputs.

### 4.2 Separate execution ownership from observation

A future provider observer should inspect a run without pretending to own the provider run lifetime.

Observer responsibilities include:

- timestamped provider status observations;
- bounded inaccessible-status handling;
- quota snapshots before and after an authorized provider run;
- terminal-state recording;
- provider artifact inventory;
- secret-safe diagnostics.

An observer timeout must not automatically cancel an otherwise valid provider run. Provider cancellation or mutation requires its own authority.

### 4.3 Fail closed on blind monitoring

Repeated inability to read provider status is not success. The default foundation contract uses the PED-proven bounded rule of three consecutive inaccessible-status observations before monitoring fails closed. This is an observation failure, not permission to restart compute.

### 4.4 Reuse unchanged provider capability evidence

A previously proven provider capability should not be re-smoked merely because a new experiment is prepared. A new capability smoke is justified only by material provider/tool/compute-contract drift or a separately approved diagnostic need.

This avoids wasting accelerator quota and prevents diagnostic work from becoming accidental training spend.

### 4.5 Keep authority, runpack/status and artifacts separate

Dataset/package authority, provider-run state and returned artifacts are different truths. A status projection cannot mutate the frozen package, and a model artifact cannot rewrite dataset authority.

## 5. CPU validation gate

Before any future provider admission, the generated package must pass the CPU validation layer.

The gate verifies at minimum:

```text
manifest schema
+ exact declared entry set
+ byte sizes
+ SHA-256 fingerprints
+ package fingerprint
+ safe transport filenames
+ non-authoritative contract flags
```

The resulting `CpuValidationReport` is local/CI evidence. It carries `external_execution=false` and `product_authority=false`.

Passing CPU validation means only that the package is internally consistent and reproducible enough to consider for a later experiment. It does **not** authorize upload, training, GPU use or product promotion.

## 6. Telemetry contract

Future authorized provider execution should emit structured telemetry instead of relying on notebook logs as the only evidence.

The initial event vocabulary is:

```text
quota_before
provider_status
epoch_checkpoint
artifact_inventory
quota_after
terminal_state
diagnostic
```

Each event binds the experiment identity and training-package fingerprint and records a UTC observation time. Epoch events also record the completed epoch where applicable. Detailed logs may remain outside repository truth, while a checksum can bind the retained detail artifact.

Telemetry is observational and always `product_authority=false`.

## 7. Epoch/checkpoint re-entry

A long-running training process must be resumable from explicit checkpoint evidence rather than from chat memory or an opaque provider page.

After each checkpoint epoch declared by a future experiment/run contract, the system should materialize an `EpochReentryCheckpoint` containing at least:

- experiment identity;
- training-package fingerprint;
- completed epoch;
- checkpoint/model-state artifact fingerprint;
- metrics artifact fingerprint;
- code revision;
- provider-run reference;
- exact operator-authorization reference for GPU-derived checkpoints;
- state;
- parent checkpoint fingerprint when resuming a chain.

The next training segment must prove continuity with the previous checkpoint:

```text
same experiment
+ same training package
+ same operator authorization
+ strictly advancing epoch
+ exact previous-checkpoint fingerprint
```

A changed dataset/package, authorization or non-advancing epoch is not a resume. It requires a newly classified run/authority decision.

The checkpoint receipt is a re-entry surface, not product authority. A later session or runner must still revalidate live repository/run truth before continuing.

Checkpoint cadence is intentionally model-agnostic in MLF-004. The future experiment contract will declare appropriate epochs/checkpoints rather than copying PED's detection-specific epoch numbers.

## 8. Diagnostics and failure taxonomy

ML experiments should retain evidence from failures instead of looping until a run turns green.

The initial diagnostic classes mirror the useful PED distinction:

- `hypothesis_failure` — the experiment ran correctly but the ML hypothesis did not produce the expected value;
- `convergence_failure` — implementation/model behavior has not converged and needs a materially different causal repair;
- `operational_failure` — credible transient provider/runner/network/tooling failure;
- `governance_failure` — missing authority, credential expansion, GPU/paid-compute boundary, unsafe transfer or other operator-controlled decision.

A diagnostic receipt binds experiment, stage, failure class, evidence key and a fingerprint of detailed evidence. Run IDs or cosmetic message changes must not erase the causal identity of a recurring failure.

`governance_failure` is an immediate operator stop. Autonomous retries cannot create missing authority.

## 9. Artifact return contract

Any later returned experiment artifact must bind:

- artifact identity and kind;
- experiment identity;
- exact training-package fingerprint;
- artifact SHA-256;
- producing code revision;
- compute class;
- operator-authorization reference when GPU-derived;
- `product_authority=false`.

Examples may later include checkpoints, model candidates, metrics, predictions or diagnostic bundles. A returned model is a candidate artifact, not a product decision.

## 10. MLF-004 hard stop

MLF-004 may merge when its contracts and CPU tests pass normal repository CI.

MLF-004 must stop before all of the following:

- database snapshot materialization against live production data;
- external dataset/package upload;
- Kaggle API/CLI submission;
- notebook/kernel execution;
- CPU execution on Kaggle or another external provider;
- GPU allocation, CUDA smoke or accelerator probing;
- model-family selection;
- real model training;
- productive inference/ranking changes.

The next execution-oriented slice must be separately defined. GPU execution remains blocked until the operator explicitly authorizes the exact intended run boundary.
