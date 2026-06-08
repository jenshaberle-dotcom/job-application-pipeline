# ADR-028: Separate Source Family, Source Target and Source Type

## Status

Accepted

## Context

The project currently uses `source_name` as the primary source identifier throughout ingestion, storage and analysis.

Examples include:

- `bundesagentur_fuer_arbeit`
- `stepstone`
- `greenhouse:stripe`
- `personio:eraneos`

This was sufficient during the early stages of the project because only a small number of sources existed.

As source coverage grows, the current model starts to mix fundamentally different analytical levels under the same attribute.

Examples:

| Current source_name | Actual concept |
|---|---|
| `bundesagentur_fuer_arbeit` | Public job API |
| `stepstone` | Aggregator and discovery platform |
| `greenhouse:stripe` | ATS family plus employer board |
| `personio:eraneos` | ATS family plus employer board |

These values do not represent the same analytical level.

As a consequence, future analysis may incorrectly compare:

- aggregators
- public APIs
- ATS platforms
- individual employers
- direct employer career sites

as if they were equivalent source entities.

This becomes increasingly problematic for:

- Source Value analysis
- Source Health monitoring
- employer-specific tracking
- source overlap analysis
- canonical source resolution
- ATS expansion
- direct employer career site integration

The project therefore requires a more explicit source model.

## Decision

The project will conceptually separate source information into three dimensions:

- `source_family`
- `source_target`
- `source_type`

This ADR defines the intended analytical model.

It does not require an immediate database migration.

## Source Family

The source family describes the technical platform, provider family or acquisition mechanism that provides the data.

Examples:

- `bundesagentur_fuer_arbeit`
- `stepstone`
- `greenhouse`
- `personio`
- `workday`
- `lever`
- `smartrecruiters`
- `softgarden`
- `employer_site`

The source family answers:

> Which technical platform, provider family or acquisition mechanism produced the data?

## Source Target

The source target describes the concrete target within a source family.

Examples:

- `stripe`
- `eraneos`
- `schluetersche-mediengruppe`
- `hdi`
- `vhv`
- `enercity`
- `data_engineer_hannover`

The source target answers:

> Which employer, tenant, board, search scope or acquisition target produced the result?

## Source Type

The source type describes the architectural role of the source.

Examples:

- `official_api`
- `aggregator`
- `discovery`
- `ats`
- `employer`
- `fallback`
- `observation`

The source type answers:

> What role does this source play within the job intelligence architecture?

## Examples

### Bundesagentur für Arbeit

source_family:

    bundesagentur_fuer_arbeit

source_target:

    NULL

source_type:

    official_api

### StepStone

source_family:

    stepstone

source_target:

    data_engineer_hannover

source_type:

    aggregator

### Greenhouse Stripe

source_family:

    greenhouse

source_target:

    stripe

source_type:

    ats

### Personio Eraneos

source_family:

    personio

source_target:

    eraneos

source_type:

    ats

### Future HDI Career Site

source_family:

    employer_site

source_target:

    hdi

source_type:

    employer

If HDI later exposes a known ATS platform, the source family may become more specific.

Example:

source_family:

    workday

source_target:

    hdi

source_type:

    ats

## Relationship to ADR-026 and ADR-027

ADR-026 defines the source acquisition scope, canonical source strategy and Source Value evaluation direction.

ADR-027 defines the source target acquisition model.

ADR-028 refines the analytical source model by explicitly separating:

- source family
- source target
- source type

ADR-026 answers:

> Which kinds of sources should be treated as discovery, aggregator or canonical-source candidates?

ADR-027 answers:

> How are concrete acquisition targets represented?

ADR-028 answers:

> How can different source categories be analysed without mixing analytical levels?

## Current Implementation Position

The current implementation may continue to use compound source identifiers such as:

- `greenhouse:stripe`
- `personio:eraneos`

This remains acceptable for:

- Bronze evidence preservation
- connector implementation
- operational monitoring
- small-scale source expansion

However, future analytical capabilities should avoid treating compound `source_name` values as the final source model.

In particular, Source Value analysis should not permanently compare `bundesagentur_fuer_arbeit`, `stepstone`, `greenhouse:stripe` and `personio:eraneos` as if they were all the same kind of source entity.

## Consequences

### Positive

- avoids comparing employers, ATS platforms and aggregators as the same entity
- improves future Source Value analysis
- improves future Source Health monitoring
- supports employer-centric monitoring
- supports ATS-centric analysis
- prepares future canonical source resolution
- supports direct employer source integration
- documents the intended analytical model before implementation becomes necessary

### Negative

- introduces additional terminology
- requires discipline while the schema still uses `source_name`
- requires later schema evolution
- requires migration planning when implementation begins
- may temporarily coexist with compound source identifiers

## Deferred Implementation

Implementation is intentionally postponed.

The project will revisit this decision when one or more of the following conditions become true:

- multiple Personio targets are active
- multiple Greenhouse targets are active
- direct employer career sites are integrated
- Source Value analysis requires separation between platform and employer
- Source Health reporting requires target-level visibility
- canonical source resolution requires employer metadata

Potential implementation options include:

- a dedicated `source_targets` table
- explicit `source_family` column
- explicit `source_target` column
- explicit `source_type` column
- transitional derivation from compound `source_name` values
- source target configuration before broader ATS or employer-site expansion

## Follow-Up Work

1. Continue using the current `source_name` representation for operational simplicity.
2. Avoid treating `source_name` as the final analytical source model.
3. Revisit this ADR before large-scale ATS expansion.
4. Revisit this ADR before integrating direct employer career sites.
5. Extend Source Value analysis to distinguish family-level and target-level observations.
6. Consider the source family and source target model before implementing advanced Source Health diagnostics.
