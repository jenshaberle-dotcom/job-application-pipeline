# ML-SNAPSHOT-001 — Read-only Silver Materialization Contract

Status: **MLF-005 candidate — local materialization and CPU validation only**  
Upstream authority: `ML-LEARN-001`, MLF-002 dataset manifest, MLF-003 snapshot plan  
Downstream boundary: `ML-KAGGLE-001` transport contract  
External provider execution: **not authorized**

## 1. Purpose

MLF-005 closes the gap between the DB-backed Silver source of truth and the already-defined Kaggle transport contract without making an export file, notebook or model artifact authoritative.

The intended chain is:

```text
PostgreSQL silver_jobs
-> MLF-003 read-only snapshot plan
-> canonical local JSONL materialization
-> MLF-002 dataset manifest
-> MLF-004 transport-package manifest
-> local/on-disk CPU validation
-> immutable derived package below ignored .runtime/
```

The database and repository contracts remain project truth. The generated package is reproducible derived evidence only.

## 2. Hard execution boundary

MLF-005 does not upload anything and does not invoke Kaggle.

It must not:

- submit a Kaggle dataset, notebook or kernel;
- request or probe an accelerator;
- allocate GPU compute;
- train or evaluate a model;
- call an external LLM/provider as part of materialization;
- mutate `silver_jobs`, labels, lifecycle state, Gold read models or product ranking;
- write generated job rows into the Git repository or a GitHub Actions artifact.

The package is local derived state. The default output root is:

```text
.runtime/ml-training-packages/
```

`.runtime/` is ignored by Git.

## 3. Database read boundary

The live materializer reuses the exact MLF-003 plan rather than constructing a second SQL path.

It therefore uses:

```text
source relation: silver_jobs
isolation: REPEATABLE READ
transaction mode: READ ONLY
evidence cutoff: explicit timezone-aware timestamp
```

Defense in depth is required. After opening the transaction, the runtime checks the database-reported settings:

```text
transaction_read_only = on
transaction_isolation = repeatable read
```

If either check fails, no snapshot SELECT is accepted. The connection is rolled back after the read path even though the transaction is read-only.

The SQL itself remains the MLF-003 generated SELECT and excludes any row whose `normalized_at`, `created_at` or `updated_at` exceeds the explicit evidence cutoff.

MLF-005 rechecks those three timestamp boundaries in Python after retrieval. This second check is intentional: a query/configuration regression must not silently become a valid package.

## 4. Fail-closed row contract

A materialization fails if:

- the snapshot is empty;
- returned columns differ from the MLF-003 selected-column contract;
- the primary key is missing, invalid or duplicated;
- a time-boundary field is missing, naive or later than the evidence cutoff;
- a selected value has an unsupported serialization type.

MLF-005 does not silently drop unexpected columns or coerce unsupported values.

## 5. Canonical dataset payload

Rows are sorted by the snapshot primary key and serialized as canonical UTF-8 JSON Lines.

Stable representation rules include:

- timezone-aware timestamps normalized to UTC `Z` form;
- dates serialized as ISO dates;
- JSON object keys sorted canonically;
- one row per line with a trailing newline;
- no locale-dependent formatting.

The payload file is:

```text
silver-jobs.jsonl
```

Its SHA-256 is part of the snapshot identity.

## 6. Snapshot identity

The `source_snapshot` identity is derived from a canonical identity core containing at least:

- materialization schema version;
- source relation;
- explicit evidence cutoff;
- exact row count;
- MLF-003 snapshot-plan fingerprint;
- generated SELECT fingerprint;
- read-only transaction-preamble fingerprint;
- canonical dataset-payload fingerprint;
- read-only and isolation declarations.

This produces a stable identity of the form:

```text
silver_jobs:sha256:<digest>
```

Changing the payload, cutoff or snapshot-plan/query contract changes the source-snapshot identity.

The source-snapshot identity intentionally describes the DB evidence snapshot, while the later dataset/package manifests also bind the exact feature contract, product contract and code revision.

## 7. Repository and product provenance

The local CLI refuses a live materialization when tracked Git changes are present. The producing code must therefore be representable by one exact Git commit.

The CLI binds:

- current Git commit;
- fingerprinted MLF-003 snapshot/feature contract;
- SHA-256 of `docs/reference/product-contract/PRD.md`;
- generated DB source-snapshot identity.

This prevents a package from claiming a commit while actually being produced by uncommitted code.

## 8. Labels and splits are deliberately absent

MLF-005 is an **evidence materialization**, not a trainable task definition.

Its MLF-002 dataset contract records:

```text
split_strategy = unsplit_evidence_snapshot_v1
label_provenance = none:unlabeled_evidence_snapshot_v1
```

No operator-interest label, application decision, interview outcome or LLM weak label is joined here.

This is important for leakage control: MLF-005 proves the DB-to-package path before a future task/label/split contract introduces supervised-learning semantics.

A later slice must define approved labels and group-safe train/validation/test splitting explicitly. MLF-005 may not infer those decisions.

## 9. Aggregate diagnostics

Snapshot metadata contains only bounded aggregate diagnostics in addition to lineage fields, including:

- source-name row counts;
- null counts for feature-candidate fields;
- count of rows with a canonical duplicate-group key;
- count requiring the documented fallback grouping key.

These diagnostics help identify source or feature-quality problems before compute is considered. They do not create labels or ranking authority.

## 10. Package layout

One immutable local package directory contains:

```text
silver-jobs.jsonl
dataset-manifest.json
snapshot-metadata.json
package-manifest.json
cpu-validation-report.json
```

The first three files are declared MLF-004 package entries and are individually checksummed.

`package-manifest.json` binds the MLF-002 dataset-manifest fingerprint, MLF-003 plan fingerprint, source snapshot, feature/product contract versions, code revision and entry fingerprints.

`cpu-validation-report.json` records local CPU validation only and retains:

```text
compute_class = cpu_validation
external_execution = false
product_authority = false
```

## 11. On-disk validation and immutable publish

MLF-005 validates the in-memory package first, writes declared bytes to a staging directory, reads those bytes back from disk, validates them again against MLF-004 hashes, and only then atomically publishes the package directory.

An existing package ID is never overwritten. Re-running the exact materialization therefore fails rather than silently mutating previously derived evidence.

A partial or checksum-invalid staging package cannot be published as a successful local package.

## 12. Local command

A live package can be created with an explicit evidence cutoff:

```bash
python -m scripts.materialize_ml_training_snapshot \
  --evidence-cutoff 2026-08-23T16:00:00Z
```

The command prints only a bounded receipt containing package/snapshot fingerprints, row count, cutoff, compute class and local output directory. It does not print database credentials or job rows.

## 13. Promotion boundary

Successful MLF-005 materialization proves only:

> the current Silver evidence can be reproducibly read under a verified read-only boundary, converted into a checksummed local package and validated without external compute.

It does not prove model value and does not authorize provider execution.

The next ML work should remain ordered:

```text
MLF-005 live local package proof
-> explicit task/label contract
-> group-safe split/leakage contract
-> deterministic and LLM baseline evidence
-> only then a separately authorized provider/GPU execution slice
```

No MLF-005 merge, CI result, local package or available Kaggle credential may self-activate GPU/provider execution.
