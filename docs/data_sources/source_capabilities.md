# Source Capabilities

## Purpose

This document compares job source capabilities.

The goal is not to force all sources into the same technical behavior.

The goal is to make source differences explicit, comparable and visible in the connector architecture.

## Terminology Alignment

This document uses the shared terminology from `docs/glossary.md`, ADR-022 and ADR-023.

Source-specific differences should be captured as source capabilities or mappings to canonical concepts. They should not introduce separate terminology for each source.

For example, a StepStone `article[data-testid="job-item"]` is documented as an observed source signal for a **result card**. It is not a new canonical project entity.

Source capabilities describe what a source can support technically and operationally.

They are not only used for connector implementation, but also for:

- source evaluation
- ingestion strategy decisions
- local filtering decisions
- heartbeat strategy planning
- dashboard interpretation
- future source prioritization

For search-result-oriented sources, connector output should follow the documented search result connector contract.

See also:

- `docs/data_sources/search_result_connector_contract.md`
- `docs/adr/023_define_search_result_connector_contract.md`

---

## Capability Matrix

| Source | Type | Keyword | Location | Radius | Employment Type | Remote | Pagination | Full Fetch | Current Status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Bundesagentur für Arbeit | Public job API | yes | yes | yes | yes | no | yes | no | implemented |
| Greenhouse | ATS job board | no | no | no | no | no | no | yes | implemented |
| StepStone | Commercial job portal | observed | observed | unknown | unknown | unknown | not evaluated | no | limited result-card connector |
| Workday | Enterprise ATS | limited | limited | no | limited | unclear | yes | no/limited | candidate |
| Personio | ATS / company career system | limited | limited | no | limited | unclear | limited | yes/limited | candidate |
| Lever | ATS job board | no/limited | limited | no | no | no | no/limited | yes | candidate |
| Company career pages | Direct employer source | variable | variable | variable | variable | variable | variable | variable | candidate |

---

## Extended Evaluation Dimensions

The basic capability matrix is intentionally compact.

For more complex sources, especially commercial job portals and HTML-based sources, additional evaluation dimensions are required.

These dimensions help decide whether a source should be implemented as:

- a production connector
- an experimental spike
- a documentation-only candidate
- a deferred source

### Source Role

Describes the intended architectural role of a source.

Allowed values:

| Value | Meaning |
|---|---|
| `official_api_source` | Official or explicitly intended machine-readable API source. |
| `canonical_source` | Employer or ATS-near source preferred for canonical job identity. |
| `discovery_source` | Source used to discover that an opportunity may exist. |
| `aggregator_source` | Source aggregating postings from multiple employers or recruiters. |
| `fallback_source` | Source used when no stronger canonical source can be resolved. |
| `observation_source` | Source providing evidence that a job was seen at a specific time. |

### Acquisition Mode

Describes how broadly the source should be queried.

Allowed values:

| Value | Meaning |
|---|---|
| `official_api_ingestion` | Systematic ingestion through an official API. |
| `company_board_ingestion` | Fetching jobs from a company or ATS board. |
| `limited_probe` | Bounded sample used for source and connector validation. |
| `controlled_sampling` | Bounded recurring sampling with explicit caps and stop conditions. |
| `unsupported_full_crawl` | Broad collection mode that should not be implemented. |

### Recall Claim Level

Describes what kind of coverage claim the project may make for the source.

Allowed values:

| Value | Meaning |
|---|---|
| `full_or_high_confidence` | Broad coverage can be claimed for the configured source scope. |
| `bounded_sample` | Results represent a documented bounded sample. |
| `sample_only` | Results are useful for probing and exploration only. |
| `none` | No recall claim should be made. |
| `unknown` | Not evaluated yet. |

### Source Value Evaluation

Describes whether the source must prove continued value through later metrics.

Relevant value dimensions:

| Dimension | Meaning |
|---|---|
| `coverage_gain` | Additional jobs or companies discovered compared with existing sources. |
| `unique_job_rate` | Share of jobs not already observed through other sources. |
| `unique_company_rate` | Share of companies not already observed through other sources. |
| `canonical_match_rate` | Share of discovered jobs that can be resolved to a canonical company or ATS source. |
| `early_discovery_value` | Whether the source discovers opportunities earlier than other sources. |
| `risk_penalty` | Legal, terms-of-service, blocking or responsible-use sensitivity. |
| `maintenance_penalty` | Expected parser, connector and operational maintenance cost. |

### Access Model

Describes how the source can be accessed.

Allowed values:

| Value | Meaning |
|---|---|
| `public_api` | Structured public API |
| `public_json` | Public JSON endpoint without formal API contract |
| `ats_board` | ATS-hosted company job board |
| `html_pages` | HTML pages requiring parsing |
| `browser_like` | Requires browser-like requests or dynamic page handling |
| `unknown` | Not evaluated yet |

### Filtering Capability

Describes how much of the canonical search intent can be applied server-side.

Allowed values:

| Value | Meaning |
|---|---|
| `strong` | Keyword, location and other relevant filters are supported server-side |
| `partial` | Some important filters are supported server-side |
| `weak` | Only coarse filtering is supported server-side |
| `none` | Source requires full fetch and local filtering |
| `unknown` | Not evaluated yet |

### Identifier Quality

Describes whether the source provides stable job identifiers.

Allowed values:

| Value | Meaning |
|---|---|
| `stable` | Source provides stable external job IDs |
| `derived` | Identifier can be derived from URL or structured fields |
| `unstable` | Identifier may change between requests |
| `missing` | No reliable identifier available |
| `unknown` | Not evaluated yet |

### Publication Date Quality

Describes whether publication metadata is available and reliable.

Allowed values:

| Value | Meaning |
|---|---|
| `exact` | Source provides explicit publication timestamp or date |
| `approximate` | Source provides approximate age or freshness information |
| `missing` | No publication metadata available |
| `unknown` | Not evaluated yet |

### Pagination Model

Describes how result traversal works.

Allowed values:

| Value | Meaning |
|---|---|
| `page` | Page-number based pagination |
| `offset` | Offset/limit based pagination |
| `cursor` | Cursor-based pagination |
| `infinite_scroll` | Dynamic loading pattern |
| `none` | No pagination required or available |
| `unknown` | Not evaluated yet |

### Operational Risk

Describes practical implementation and maintenance risk.

Relevant risk dimensions:

| Dimension | Meaning |
|---|---|
| `rate_limit_risk` | Risk of being throttled |
| `blocking_risk` | Risk of anti-bot blocking |
| `layout_change_risk` | Risk of source structure changes breaking the connector |
| `maintenance_effort` | Expected long-term maintenance effort |
| `legal_ethical_risk` | Terms-of-service, scraping and responsible-use concerns |

Allowed risk values:

| Value | Meaning |
|---|---|
| `low` | Low expected risk |
| `medium` | Manageable but relevant risk |
| `high` | Significant risk requiring caution |
| `unknown` | Not evaluated yet |

### Heartbeat Strategy

Describes how source availability should be checked.

Allowed values:

| Value | Meaning |
|---|---|
| `endpoint_check` | Lightweight check against a stable endpoint |
| `lightweight_search` | Minimal search request without broad ingestion |
| `board_metadata_check` | Check ATS board metadata or company board availability |
| `not_defined` | No heartbeat strategy defined yet |
| `not_applicable` | Heartbeat does not apply to this source type |

### Ingestion Strategy

Describes the intended productive ingestion mode.

Allowed values:

| Value | Meaning |
|---|---|
| `search_fetch` | Fetch based on canonical search intent |
| `full_fetch` | Fetch all jobs from a source or board |
| `company_board_fetch` | Fetch one company-specific ATS board |
| `experimental_spike` | Limited exploration before production use |
| `limited_result_card_fetch` | Fetch search-result cards only without detail-page crawling or broad pagination |
| `deferred` | Not planned for implementation yet |

---

## Source Capability Profiles

### Bundesagentur für Arbeit

Current profile:

| Dimension | Value |
|---|---|
| Access model | `public_api` |
| Filtering capability | `strong` |
| Identifier quality | `stable` |
| Publication date quality | `exact` |
| Pagination model | `page` |
| Rate limit risk | `low` |
| Blocking risk | `low` |
| Layout change risk | `low` |
| Maintenance effort | `low` |
| Legal / ethical risk | `low` |
| Heartbeat strategy | `lightweight_search` |
| Ingestion strategy | `search_fetch` |

Summary:

The Bundesagentur für Arbeit source is the cleanest currently implemented source.

It is suitable for validating ingestion mechanics, search profile behavior, pagination, duplicate handling and Bronze-to-Silver processing.

It should not be the only architectural reference point because it is more structured than many real-world recruiting sources.

### Greenhouse

Current profile:

| Dimension | Value |
|---|---|
| Access model | `ats_board` |
| Filtering capability | `none` |
| Identifier quality | `stable` |
| Publication date quality | `missing` |
| Pagination model | `none` |
| Rate limit risk | `low` |
| Blocking risk | `low` |
| Layout change risk | `medium` |
| Maintenance effort | `medium` |
| Legal / ethical risk | `low` |
| Heartbeat strategy | `board_metadata_check` |
| Ingestion strategy | `company_board_fetch` |

Summary:

Greenhouse is a full-fetch ATS board source.

It does not support the canonical search intent server-side in the current implementation.

The connector therefore fetches a company board and applies local filtering where needed.

This source is useful because it introduces realistic ATS behavior, incomplete metadata and source-specific normalization needs.

### StepStone

Current status: `limited_result_card_connector`

Current profile:

| Dimension | Value |
|---|---|
| Access model | `html_pages` |
| Filtering capability | `partial` |
| Identifier quality | `derived` |
| Publication date quality | `unknown` |
| Pagination model | `unknown` |
| Rate limit risk | `unknown` |
| Blocking risk | `medium` |
| Layout change risk | `high` |
| Maintenance effort | `high` |
| Legal / ethical risk | `high` |
| Heartbeat strategy | `not_defined` |
| Ingestion strategy | `limited_result_card_fetch` |

Observed StepStone-specific capabilities:

| Capability | Current Assessment |
|---|---|
| Source role | `discovery_source`, `aggregator_source`, `observation_source` |
| Canonical source preference | Prefer company or ATS source when resolvable |
| Fallback source usage | Allowed, but fallback records must remain distinguishable from verified canonical sources |
| Current acquisition mode | `limited_probe` |
| Target acquisition mode candidate | `controlled_sampling` |
| Recall claim level | `sample_only` |
| Full crawl support | Explicitly out of scope |
| Detail-page strategy | Disabled unless explicitly justified later |
| Source value evaluation | Required before expanding long-term strategic usage |
| Search URL filtering | Keyword and location observed |
| Result boundary | `article[data-testid="job-item"]` observed |
| Result-card fields | Title, company, location and detail URL observed |
| Result-card parser | Reusable parser module implemented and fixture-tested |
| External ID | Derived candidate from article ID and detail URL |
| ID confidence | Promising in sample, not long-term validated |
| Detail pages | Not evaluated |
| Pagination | Not evaluated |
| Database ingestion | Controlled profile validated |
| Connector status | Limited result-card connector implemented and validated through controlled profile |
| Operational risk | Medium to high |
| Maintenance risk | High |
| Recommended strategy | Controlled multi-term result-card ingestion, no detail pages, no pagination, no aggressive crawling |

Summary:

StepStone is no longer an unknown source.

Source analysis and limited result-card probes showed that StepStone can provide useful search-result-level records from public HTML result pages.

A reusable result-card parser now exists and is covered by fixture-based tests.

The limited result-card connector is implemented in `src/connectors/stepstone.py`.

This does not mean broad crawling, detail-page fetching, pagination traversal or full production-scale ingestion.

StepStone should remain marked as operationally sensitive and higher maintenance than API-based or ATS-board sources. The implemented connector remains intentionally limited to result-card extraction.

A controlled multi-term ingestion run validated that StepStone can be executed through the normal ingestion runner.

The run produced 175 observations, 109 new raw jobs and 66 duplicate observations across seven search terms.

The result also showed broad source-side matching behavior, so downstream relevance scoring and search-term quality evaluation are required before using StepStone results for candidate-facing recommendations.


---

## Source Categories

### Search-capable APIs

These sources can apply a large part of the canonical search intent server-side.

Example:

- Bundesagentur für Arbeit

### Full-fetch ATS boards

These sources expose all jobs for one company or board.

Example:

- Greenhouse

These require local filtering if the project wants only jobs matching a role term such as `Data Engineer`.

### Commercial job portals

These sources are realistic and valuable, but may involve higher technical, operational and legal complexity.

Examples:

- StepStone
- Indeed-like platforms
- LinkedIn-like platforms

They should be isolated behind connector boundaries and implemented cautiously.

Commercial job portals should be evaluated before implementation.

### Direct employer career pages

These sources can provide high-value original job postings but often have highly variable structures.

Examples:

- company career pages
- custom recruiting pages
- embedded ATS widgets

They should be evaluated source by source.

---

## Architectural Rules

All connectors receive the same canonical search intent.

Each connector declares which filters it can apply server-side.

Unsupported filters are applied locally where feasible.

Sources with unknown or high operational risk should first be evaluated through source analysis and limited probes before production ingestion.

Commercial job portals require explicit source evaluation before production ingestion.

Heartbeat strategy should be considered part of source capability evaluation.

Source capabilities should be documented before adding complex connectors.
