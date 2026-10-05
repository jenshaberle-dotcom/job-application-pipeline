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
SOCIAL is confined to REGION_HANNOVER, the Hannover city-and-region contrast scope; it is
not a city-only scope and is not expanded to the other TECH geographies. This declared scope
does not prove actual municipality or source coverage. Company identities are shared across
dimensions; `scope_memberships` preserves observed geography/cohort pairs without a false
cross product. Directory profile URLs are lineage/navigation evidence, not employer domains.
They live in `directory_urls`, never in `websites`, until actual employer-domain evidence is acquired.

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

## Current execution gates (2026-10-05)

PR #1167 is integrated as `5d85a6f09d47824f7012e92e23f600a61d3ca77b`. The Census workflow,
consumer test policy, trusted test launcher and optional `test_plan` input are now on main.
The earlier observation that the Census workflow returned 404 was a pre-merge observation,
not a current blocker. Likewise, looking for Actions only by candidate `head_sha` misses
trusted-main `workflow_dispatch` runs; the candidate is bound by the `source_sha` input and
must be verified in the execution evidence.

Operator-reported host receipt `20261005T064216Z-645995` confirms adoption of RCC source
`4a04c21e8feec202e64a2aaabf1d578fdb49022e` using the existing controller and state roots.
It reports quiescence, unchanged request receipts and successful controller/broker self-tests.
Cloud delivery remains disabled. This is host adoption evidence, not a completed Workchat
validation, real Census execution, status-write acceptance or automatic merge permission.

The remaining transitions are distinct:

1. **Workchat validation:** publish a source-bound request in a PR description using the
   existing `rcc-test-request` contract. Observe a real dynamic plan, RCC assignment, Actions
   execution, bound test receipt and terminal status. Full pytest remains the PR/merge
   baseline. Diagnostics may adjust optional suites but cannot replace merge qualification.
2. **Public Census execution:** separately admit the existing Census workflow through RCC.
   The automatic JAP PR catalog entry remains `pr-validation.yml`, not the Census. A mapped
   demand or green validation run does not itself authorize live network discovery. RCC must
   construct exact authority, resolve profile identity/hash, allocate a General Pool member
   and dispatch. Do not handcraft consumer runner assignments or relabel discovery as CI.
3. **Coverage and Factory evaluation:** inspect real source failures, TECH/SOCIAL and regional
   counts, then acquire Career/Origin evidence and evaluate the immutable population. A
   completed discovery process alone does not prove full company coverage or extraction.

The executor uses the installed host broker. GitHub request/Actions access from Workchat does
not grant direct host administration. Preserve terminal/uncertain requests and reservations;
do not reset them to obtain another run. No live Census receipt is recorded by this document
update, and no provider, Azure, production source activation or application action is granted.

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
