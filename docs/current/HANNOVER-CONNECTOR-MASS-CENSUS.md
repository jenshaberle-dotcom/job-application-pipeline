# Multi-Region Connector Factory Lab

JAP Classic is the development, benchmark and experiment environment for the JAP Cloud
Connector Factory. It is no longer a product to preserve. Tracking: #1166, PR #1167.
Quality > cost > time.

## One execution path

Public Company Discovery → Multi-Region Census → Career/Origin Evidence → Fingerprinting
→ aggressive Connector Factory → Generic Extraction → Qualification → Evaluation → labelled ML corpus.

`connector_factory.py` and `connector_extraction.py` are the sole Factory core and recipe
runtime. `aggressive_factory.py` owns advancement; the older policy API projects its results
for existing callers. Independent copies of the core/runtime have been removed.
No per-employer parser generation, production activation or legacy registry authority is
introduced. A definition qualification proves definition integrity, not successful extraction.

TECH covers REGION_HANNOVER, WOLFSBURG, INGOLSTADT, STUTTGART_REGION, BERLIN and MUNICH.
SOCIAL is confined to REGION_HANNOVER. Company identities are shared across dimensions;
`scope_memberships` preserves observed geography/cohort pairs without a false cross product.
Directory profile URLs are lineage/navigation evidence, not employer domains. They live in
`directory_urls`, never in `websites`, until actual employer-domain evidence is acquired.

## RCC execution

`.rcc/workload-demands.json` maps `connector-factory-hannover-census.yml` to `linux-base`.
The workflow checks exact source, RCC facade and ephemeral assignment, resolves the RCC
qualified interpreter and deletes its isolated checkout after uploading evidence. It owns no
runner, physical member selection, profile installation or hosted fallback.

The discovery runner executes each configured source once with a bounded timeout and continues
after source failure. Failed attempts cannot reuse an earlier snapshot. It writes
`discovery-coverage.json` even if no usable source remains. Each successful snapshot carries a
SHA-256 digest. The Census population digest identifies replay inputs; raw HTML is not archived.

Coverage reports unique companies per geography/cohort, source contribution and exclusive
source contribution. TECH minimums are Hannover 250, Wolfsburg 50, Ingolstadt 50, Stuttgart 100,
Berlin 250 and Munich 250. SOCIAL cannot satisfy a TECH threshold. A nonempty partial population
is Factory-usable; gaps generate `SOURCE_COVERAGE_GAP` and `additional_sources_required=true`.
Source configuration is provisional until a real RCC run proves it. No source additions are
justified by fixtures or hypothetical counts.

## Verified external execution gate (2026-10-04)

Read from current RCC `main`:

- `tools/linux/Run-DemandV2CiController-Wsl.py` automatically admits only the exact configured
  validation-only PR workflow. JAP's catalog entry is `pr-validation.yml`; it is not the Census.
- `tools/linux/Run-SharedPoolProductionWorkload-Wsl.py` supports `EXACT_SOURCE_V1` with
  `OPEN_PR_EXACT_HEAD`, but checks the workflow on trusted consumer `main` before effects.
- The Corpus workflow is absent from JAP `main`; GitHub returned 404 for that path.
- The executor performs facade lifecycle operations through the installed host broker
  `/usr/local/lib/rcc/Rcc-FacadeLifecycleBroker.py`. No authenticated remotely reachable RCC
  execution endpoint or broker access is exposed to this Work session.
- No Actions runs were observed for the experiment branch at the audited head
  `a75e5cdc8cc1fee0dcd0e7bad231bf9c429d0fd9`.

These are execution/trusted-workflow gates, not a need for more hypothetical sources.
The next admissible flight requires trusted workflow admission on consumer main and an
RCC-owned execution service with broker/credential access. RCC must construct exact authority,
resolve profile identity/hash, allocate a General Pool member and dispatch; this repository must
not fabricate these values. This PR does not merge itself or relabel a live discovery as
validation-only to evade admission.

## Corpus truth

`evaluate_connector_factory_corpus.py` preserves every Census company and groups engineering
gaps. `materialize_connector_ml_corpus.py` requires complete one-to-one evaluation coverage and
rejects a conflicting population digest. Definition-only `qualified_inactive`/`recipe_ready`
examples are `RUNTIME_GAP`. Positive labels require verified origin, runtime admission, passing
qualification and complete passing extraction with an explicit measured job count. Zero is
`ZERO_JOB_VALID_SOURCE` only with that proof; failures/gaps stay negative examples.

A real Census, real disposition distribution, origin acquisition, extraction replay and
ML readiness are still pending the RCC flight. Fixture tests are not population evidence.
After the flight: identify weak regions, add sources there only, acquire origin evidence,
cluster capability gaps by population impact, extend generic capabilities, replay and measure
ML readiness. Do not train a model before corpus quality/volume/diversity is demonstrated.
