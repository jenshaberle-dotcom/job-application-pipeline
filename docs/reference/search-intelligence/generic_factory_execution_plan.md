# Generic factory implementation and dependency decision

Status: 2026-10-20. Identity handoff implemented and live recheck started.
Generic bounded GET retries, metered redirects, static asset exclusion and
same-host sitemap fallback implemented; deployment qualification pending.
Embedding inference and automatic recipe materialization remain pending.

## Baseline and acceptance

The latest retained campaign assessed 2,240 candidates. First failures:
948 origin, 443 inventory, 307 proof, 224 reachability, 126 detail,
111 delegation, 20 process failures, 7 ambiguous identities, 1 timeout.
53 recipes are ready for construction, not installed connectors.
Counts are first failures, not independent defects or predicted repair yields.

Measure separately: identity resolved, inventory found, real detail proven,
recipe constructed, isolated execution passed, repeat execution passed,
source admitted, and jobs imported. Personal relevance stays in Gold.

## 1. Identity and reproducible evaluation

The V4 discovery adapter accepts the caller's bounded candidate identity.
It validates the exact company key and a nonempty company name before
using that record. Legacy DB loading remains available for existing callers.
No synthetic Census identities are inserted into the old candidate table.
Existing domain/proof rules remain in force.

Regression cases cover Census keys absent from the legacy database,
mismatched identities, missing names, and existing URLs. These synthetic
offline fixtures contain no copied third-party pages.

Next evaluation corpus: stratified samples from all four main failure groups,
plus positive cases and ambiguous company identities. Retain source URL,
timestamp, acquisition result, content digest and expected decision.
Keep raw third-party snapshots private until retention/reuse rights are
recorded. Do not commit website bodies to the public repository by default.
Separate unseen employers/templates from development examples. Current
pipeline failures are not ground-truth labels for ML.

## 2. Shared acquisition and staged navigation

Reuse requests, existing structured-data extraction, host authorization,
provider recognition and sitemap helpers. Do not add Scrapy or a second
crawler framework.

Introduce a single explicit request budget, deadline and evidence record
across stages. Retries for transient GET failures consume that budget;
never retry arbitrary POST operations. TLS verification remains enabled.
Respect server retry timing, avoid repeated requests to failing domains,
and distinguish denial, timeout, DNS/TLS and parsing failures.

Strategy order: structured data; recognized public ATS paths; explicit
career navigation; bounded same-host sitemap inventory; ranked observed
links. Browser execution is optional, isolated, and subject to demonstrated
coverage gain. Do not install browser binaries merely as a precaution.

Existing acquisition policies intentionally restrict requests and delegated
hosts. Broader navigation requires explicit regression coverage of these
boundaries, not removal of the genuine-job proof.

## 3. Local embeddings, no external inference service

Use a replaceable local encoder with immutable model revision and artifact
hashes. No model downloads during worker execution and no remote model code.
Evaluate a small multilingual encoder against the deterministic baseline
before adopting its runtime dependencies.

Candidate: intfloat/multilingual-e5-small, repository declares MIT.
This is not a completed clearance of a particular artifact or its runtime.
Record model revision, license file, notice, files, dependency closure and
training-data disclosures before packaging.

Rank observed authorized links and classify page types. Embedding scores
do not authorize new domains, prove company identity or establish genuine
jobs. Confidence thresholds must be calibrated on held-out examples.
Unavailable model: deterministic fallback with explicit telemetry.
Do not describe lexical hashing as learned embeddings.

No vector database or RAG framework is required for the initial scale.
Use existing storage and a bounded local index. LLM generation remains
optional and outside the first implementation.

## 4. Reusable recipe construction and selection

Persist declarative recipes, not executable code produced by a model:
strategy family/version, observed host binding, navigation parameters,
field mapping, pagination policy, evidence hashes and qualification state.
Similarity can suggest a family; it cannot copy another employer's URL or
authorize it. Execute in isolation, validate actual job fields, then repeat
against a separate observation before admission.

Recipe lifecycle: proposed -> validated -> qualified -> admitted;
failure -> diagnostic/quarantined. Record the binding from every imported
job back to recipe revision and source evidence. A successful assessment
alone must never be displayed as a built or active connector.

## Dependency/governance register

No new dependency added for the identity repair.

* Local embedding model candidate:
  https://huggingface.co/intfloat/multilingual-e5-small/tree/main
  MIT declaration; pinned artifact and runtime review pending.
* Optional Playwright:
  https://github.com/microsoft/playwright/blob/main/LICENSE
  Apache-2.0 for Playwright; browser distribution/third-party notices are
  separate packaging concerns. Not selected or installed for this change.
* Existing PyMuPDF requirement:
  https://pymupdf.io/licensing
  AGPL/commercial choice. Review actual import paths, distribution mode,
  existing license and obligations before expanding its use or shipping a
  new bundle. Not needed by this factory feature. Do not remove it blindly
  because other document functions may depend on it.

Library/model licenses do not grant rights to scrape, redistribute or train
on every website. Evaluate source conditions and intended data use separately.
This register records engineering findings, not a blanket legal clearance.

## Live recheck findings

The first identity-only recheck exposed a second generic issue: opaque Census
keys were treated as domain/name evidence. The planner now excludes hash and
UUID identifiers from identity tokens and domain bases while preserving the
original storage key. Domain labels longer than 63 characters are rejected.
No individual employer exceptions are added.
