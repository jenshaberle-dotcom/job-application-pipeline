# ADR-027: Define source target acquisition model

## Status

Accepted

## Context

The project already distinguishes canonical search intent from source-specific connector capabilities.

Existing decisions establish that:

- `SearchProfile` and `SearchTerm` represent the current canonical search intent.
- Every connector receives the same search intent.
- Connectors declare which filters they can apply server-side.
- Unsupported filters may be applied locally after fetching.
- Search-term lineage is preserved on `ingestion_runs`.
- Source acquisition strategy and canonical source strategy are handled separately.

This is sufficient for search-capable sources such as the Bundesagentur für Arbeit API.

However, not all sources behave like search APIs.

Some sources are accessed through concrete source-specific targets, for example:

- Greenhouse company boards such as `greenhouse:stripe`
- future Greenhouse boards such as `greenhouse:metronome`
- StepStone discovery queries
- future Personio, SmartRecruiters, Workday, SAP SuccessFactors or company career targets

These targets are not the same as a search profile.

A search profile describes what the project wants to find.

A source target describes where and how one source is accessed to acquire possible matching records.

Without this distinction, the project risks modelling technical targets as separate search profiles.

That would make later search-quality, source-value and cross-source overlap analysis harder because the same intent would be duplicated across many source-specific profile names.

Example of the problem:

    greenhouse_stripe_data_engineer
    greenhouse_metronome_data_engineer
    greenhouse_teachable_data_engineer

These names mix at least two concepts:

- the search intent: data engineering oriented jobs
- the technical source target: a specific Greenhouse board

The project needs a clearer acquisition model before expanding ATS and company-board sources.

## Decision

The project will distinguish the following concepts.

### Search Profile

A source-independent search intent.

Example:

    data_engineering_hannover

A search profile describes the kind of opportunities the project wants to find.

It may include:

- role focus
- location focus
- radius or regional scope
- remote or hybrid expectations
- active search terms

### Search Term

A source-independent term or phrase that belongs to a search profile.

Examples:

    Data Engineer
    Analytics Engineer
    ETL
    Data Platform
    Python SQL

Search terms describe what should be searched or matched.

They do not describe where to fetch data.

### Source

An external system or website family that can provide job data.

Examples:

    bundesagentur_fuer_arbeit
    greenhouse
    stepstone
    personio
    softgarden
    smartrecruiters
    workday
    sap_successfactors

A source describes the technical system family, not one concrete company board or query.

### Source Target

A source-specific acquisition target.

Examples:

    greenhouse:stripe
    greenhouse:metronome
    stepstone:data_engineer_hannover
    personio:example_company
    softgarden:example_company

A source target describes the concrete access point used by a connector.

Depending on the source, this may be:

- a company board token
- an API endpoint scope
- a search result URL pattern
- a controlled discovery query
- a company career site
- an ATS tenant or board identifier

Source targets are not search profiles.

A source target may be used by one or more search profiles over time.

A search profile may use many source targets.

### Acquisition Mode

The acquisition mode describes how a source target is queried.

| Acquisition Mode | Meaning |
|---|---|
| `api_search` | Search-capable API request using the canonical search intent. |
| `company_board_fetch` | Fetch jobs from one company or ATS board. |
| `full_board_with_local_keyword_filter` | Fetch a complete board and apply search terms locally. |
| `discovery_search` | Controlled search-result acquisition from a discovery source. |
| `limited_probe` | Small bounded sample for validation. |
| `controlled_sampling` | Recurring bounded acquisition with explicit caps and stop conditions. |

### Acquisition Policy

The acquisition policy describes the operational and responsible-use boundaries for a source target.

Examples:

    max_jobs_per_board
    max_pages
    timeout_seconds
    no_detail_pages
    pagination_enabled
    pagination_cap
    fail_closed_url_policy
    active

Policies are especially important for commercial aggregation platforms and HTML-based discovery sources.

## Conceptual Example

The following conceptual configuration should be supported by the architecture over time.

Search profile:

    data_engineering_hannover

Search terms:

    Data Engineer
    Analytics Engineer
    ETL
    Data Platform
    Python SQL

Source targets:

    greenhouse:stripe
    greenhouse:metronome
    greenhouse:pilot
    greenhouse:teachable

Acquisition mode:

    full_board_with_local_keyword_filter

Policy:

    max_jobs_per_board optional
    timeout_seconds 30
    no_detail_pages true
    active true

This means:

- the search profile stays stable
- the same search terms can be evaluated across sources
- Greenhouse boards are treated as source targets
- local filtering is explicit
- later source-value analysis can compare source targets without confusing them with search intent

## Boundary to Bronze

Bronze remains source-preserving.

This ADR does not change the Bronze rule that raw source evidence should be stored with minimal interpretation.

The acquisition model belongs before and around Bronze as lineage and run context.

Bronze records may continue to store source-specific payloads.

However, ingestion lineage should make it possible to answer:

- which search profile caused this acquisition
- which search term was executed or applied
- which source was accessed
- which source target was used
- which acquisition mode was used
- which acquisition policy limited the run

## Boundary to Silver and Gold

Silver remains responsible for canonical job normalization.

The source target acquisition model does not perform cross-source deduplication.

It prepares later Silver and Gold analysis by preserving better acquisition context.

Future analysis should be able to evaluate:

- source value per source
- source value per source target
- company overlap across source targets
- duplicate candidate groups across source targets
- search-term quality by source and source target
- false-positive and false-negative behavior by acquisition strategy

## Current Implementation Position

The current implementation already has partial support:

- `search_profiles` represent search profiles.
- `search_terms` represent search terms.
- `ingestion_runs.search_term_id` and `ingestion_runs.search_term` preserve term lineage.
- `ingestion_runs.requested_url` preserves the executed URL.
- connector `source_name` currently often includes the concrete source target, for example `greenhouse:stripe`.

This ADR does not require an immediate schema migration.

The next implementation step should decide whether to introduce source targets explicitly, for example through:

- a `source_targets` table
- source target fields on ingestion runs
- a source target configuration file
- or a small incremental migration before expanding ATS ingestion

## Consequences

### Positive

- avoids mixing search intent with technical board targets
- improves future search-term quality evaluation
- improves future source-value evaluation
- supports controlled ATS and company-board expansion
- keeps commercial aggregator acquisition defensive and explicit
- prepares the project for Personio, Softgarden, SmartRecruiters, Workday and similar sources
- makes Greenhouse expansion more professional than adding isolated board-specific profiles

### Negative

- introduces another architectural concept
- requires careful naming to avoid over-engineering
- may require a future schema migration
- delays broader Greenhouse expansion slightly

## Follow-up Work

1. Update source capability documentation to reference source targets explicitly.
2. Decide the smallest implementation mechanism for source targets.
3. Avoid creating one search profile per ATS board.
4. Add a controlled Greenhouse source-target set for the existing data engineering search profile.
5. Preserve source-target lineage on ingestion runs.
6. Extend Source Value exploration to group by source target once lineage exists.
7. Later evaluate source-target quality, not only source-level quality.
