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

Coverage reports candidates per geography/cohort, source contribution and exclusive source
contribution. TECH minimums are Hannover 250, Wolfsburg 50, Ingolstadt 50, Stuttgart 100,
Berlin 250 and Munich 250. SOCIAL cannot satisfy a TECH threshold. A partial population with
valid identities may support Factory learning; gaps generate `SOURCE_COVERAGE_GAP`.
Known invalid names or reused discovery IDs instead produce `SOURCE_IDENTITY_INVALID`, with
`factory_run_recommended=false`, `ml_scale_ready=false` and counts explicitly unvalidated.
Structural identity sanity and scale thresholds do not prove complete market coverage or
training readiness. Source configurations remain provisional until measured.

## Accepted infrastructure and first real flight (2026-10-05)

PR #1167 integrated the Lab. PR #1168 integrated test-fixture isolation at
`8fcddf12e2200521df566ddefeec923fea092c2c`. Its Workchat diagnostic run `37274755893`
and independent full run `37274757623` passed, including artifacts and terminal RCC statuses.
The operator supplied matching successful requests and a subsequent merge plan with the same
execution digest, proving reuse rather than a new full test execution.

The existing RCC controller was adopted at `4a04c21e8feec202e64a2aaabf1d578fdb49022e`.
Cloud delivery remained disabled. Upload probe `37279430073` then passed before the single
public Census run `37279612056`, bound to Classic source `8fcddf12e2200521df566ddefeec923fea092c2c`.
The Census job, artifact upload and workspace cleanup passed. The operator's RCC receipt
reports final `OFFLINE_DISABLED_EXACT_ONLY` after runtime-context cleanup and reservation release.
This is real execution evidence, not acceptance of the returned company identities.

Artifact `11331628069` was downloaded and verified against SHA-256
`1d0dd4ea1cb4d6dafc8694d4bb919de055ffded3d40bd04b151ffbc51df46c75`.
Its immutable population digest is
`e362ed032a54faeac866d64af288cc86de22c1b144fdebffb0eb030132336b3d`.

### Data result: rejected for Factory and ML use

The artifact reports 423 input seeds, 421 candidate rows and 54 Hannover directory pages.
Its raw coverage projection reports Hannover TECH 411 / SOCIAL 19, Ingolstadt TECH 1,
and zero for Wolfsburg, Berlin, Munich and Stuttgart. TECH and SOCIAL can overlap.
These are defective parser observations, not accepted unique-employer counts:

- 208 candidate names are `Homepage` and 212 are URLs. Across the population 47 discovery
  evidence IDs refer to multiple candidate rows. The HSH parser split every occurrence of
  `Berufsfeld(er)` and used its preceding text as a name; the directory repeats labels in
  navigation, desktop and mobile views. That creates false rows and inflated counts.
- The one Ingolstadt row is `Startup Opportunities: Dual-Use Innovation`, an opportunity/event
  link, not an established company identity. Its inclusion pattern needs source-specific review.
- Berlin and Wolfsburg reported `SOURCE_DISCOVERY_FAILURE`; retained evidence only contains
  `CalledProcessError`, not its HTTP cause. Munich and Stuttgart returned no parsed records;
  neither result establishes that the markets contain no companies.

Preserve this original artifact as failure/evaluation evidence; do not repair names by guessing
from domains, relabel it as training data, or overwrite the consumed Census authority.

### Implemented repair and remaining operator gate

HSH parsing now binds each company to its actual local `/companies/<id>/` profile link,
collects labelled fields within that record, coalesces repeated views, and uses that profile
URL as stable discovery evidence. Conflicting records fail explicitly. The old global
preceding-text identity heuristic is removed. A positive directory total with no parsed
identities is a parser failure, not a successful zero-company observation.

Regression fixtures reproduce the observed tab/desktop/mobile structure with synthetic names;
they are not claimed to be captured live HTML. Coverage sanity checks flag invalid names and
cross-company evidence collisions without modifying the original population.

The next gate is exact-source CI, then a separately admitted corrected-source discovery flight.
No corrected live company counts, successful origin acquisition, complete extraction or ML
readiness are claimed by the repair. Fix or replace the other sources only from real source
structure/failure evidence; the first flight now establishes where additional work is needed.
The existing automatic PR carrier remains validation-only and does not launch live discovery.

## Corpus truth

`evaluate_connector_factory_corpus.py` preserves every Census company and groups engineering
gaps. `materialize_connector_ml_corpus.py` requires complete one-to-one evaluation coverage and
rejects a conflicting population digest. Definition-only `qualified_inactive`/`recipe_ready`
examples are `RUNTIME_GAP`. Positive labels require verified origin, runtime admission, passing
qualification and complete passing extraction with an explicit measured job count. Zero is
`ZERO_JOB_VALID_SOURCE` only with that proof; failures/gaps stay negative examples.

Origin acquisition, real disposition distribution, extraction replay and ML readiness remain
pending a corrected, accepted population. Do not train a model before corpus quality, volume
and diversity are demonstrated. No provider, Azure, database or production activation effects
are granted by source qualification or this inspection record.
