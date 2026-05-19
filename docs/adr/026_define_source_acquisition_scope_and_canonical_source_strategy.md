# ADR-026: Define source acquisition scope, canonical source strategy and source value evaluation

## Status

Accepted

## Context

The project ingests job-related data from different types of sources.

These sources differ significantly in technical reliability, legal and terms-of-service sensitivity, data quality, canonicality and long-term maintenance cost.

Examples:

- official APIs such as Bundesagentur für Arbeit
- public company board APIs such as Greenhouse
- company or applicant tracking system sources such as Workday, SAP SuccessFactors, SmartRecruiters, Lever, Personio or Ashby
- commercial aggregation platforms such as StepStone

Earlier project phases treated additional sources mainly as a way to increase coverage. StepStone exploration showed that this is not enough. A source can produce many observations while still being noisy, duplicative, fragile, legally sensitive or difficult to interpret.

The project therefore needs a clearer distinction between:

- discovering that an opportunity may exist
- identifying the canonical source of that opportunity
- preserving source observations for traceability
- deciding whether a source is worth continued ingestion

This decision is especially important for commercial aggregation platforms. They can provide valuable discovery signals, but they should not silently become full-crawl primary databases or replicated job boards.

## Decision

The project will distinguish source acquisition strategy from canonical job identity.

Commercial aggregation platforms may be used as controlled discovery sources, but the project will prefer official, company or ATS sources as canonical sources whenever feasible.

If no better canonical source can be resolved, a discovery source record may remain as a fallback source. Such fallback usage must be explicit and should not be confused with a verified canonical company source.

The project will introduce Source Value evaluation as a future decision criterion for keeping, expanding, reducing or removing sources.

A source is not valuable only because it provides data. A source must justify its continued use through incremental value compared with operational, technical and legal or terms-of-service related risk.

## Source Roles

The project uses the following source roles.

### Official API Source

A source with an official or explicitly intended machine-readable interface.

Examples:

- Bundesagentur für Arbeit API

Expected use:

- preferred for systematic ingestion
- suitable for recurring collection
- lower operational and legal or terms-of-service sensitivity compared with HTML aggregation sources

### Canonical Source

A source that is closest to the employer or applicant tracking system that owns the job posting.

Examples:

- Greenhouse board API
- company career site
- Workday posting
- SAP SuccessFactors posting
- SmartRecruiters posting
- Lever posting
- Personio posting
- Ashby posting

Expected use:

- preferred source for stable job identity
- preferred source for canonical fields in Silver
- preferred target for deduplication and job-cluster resolution

### Discovery Source

A source that helps discover that a job opportunity may exist, but is not necessarily the preferred canonical representation of the job.

Examples:

- StepStone result cards
- other commercial job aggregation platforms
- search-result pages
- recruiter or aggregator listings

Expected use:

- identify companies, titles, locations and source URLs
- support search-term quality analysis
- provide observations and discovery evidence
- trigger later canonical source discovery where feasible

### Aggregator Source

A source that aggregates or republishes opportunities from multiple employers or recruiters.

Examples:

- StepStone
- comparable commercial job platforms

Expected use:

- controlled discovery
- not treated as a full-crawl market database by default
- requires explicit acquisition caps and risk review

### Fallback Source

A source that remains the best available representation of a job when no stronger canonical company or ATS source can be resolved.

Expected use:

- allowed when canonical source discovery fails
- must remain marked as fallback
- should not be treated as equivalent to a verified canonical company source

### Observation Source

A source that provides evidence that a job was seen at a specific time, under a specific search profile, search term or acquisition scope.

Expected use:

- preserve lineage
- support lifecycle analysis
- support search-term quality and source-value evaluation
- support later cross-source deduplication

## Acquisition Modes

The project distinguishes acquisition modes.

### Limited Probe

Used to validate source structure, connector behavior, result-card extraction, identifiers and lineage.

Characteristics:

- small bounded sample
- no broad pagination
- no detail-page collection unless explicitly justified
- no full recall claim
- suitable for connector and data-model validation

### Controlled Sampling

Used for recurring, bounded source monitoring when the source is useful but requires caution.

Characteristics:

- explicit caps
- explicit sample scope
- documented URL policy
- no full-crawl claim
- stop conditions
- delays where appropriate
- suitable for commercial HTML aggregation sources if justified

### Full or Broad Acquisition

Used only when the source is suitable for systematic collection.

Characteristics:

- expected mainly for official APIs or public board APIs
- not the default for commercial HTML platforms
- requires explicit justification
- requires clear operational boundaries

### Unsupported Full Crawl

Used for source behaviors that should not be implemented.

Examples:

- broad crawling of commercial job platforms without an official API
- bypassing blocking or anti-bot mechanisms
- account or application-flow automation
- mass detail-page extraction without a specific decision

## Commercial Aggregator Policy

Commercial aggregation platforms must be handled defensively.

The project will not build an alternative public job platform or mirror third-party job advertisements.

For commercial aggregation platforms:

- use them primarily as discovery sources
- prefer original employer or ATS sources when available
- do not treat them as primary canonical databases by default
- avoid full crawl behavior
- avoid storing complete HTML pages
- avoid republishing full third-party job advertisements
- keep source references transparent
- do not bypass login, captcha, blocking or anti-bot mechanisms
- use fail-closed URL handling for pagination
- document acquisition caps before expanding collection depth

StepStone is currently classified as a discovery source and aggregator source.

Its current implementation status is a limited probe:

- first result page only
- bounded result-card extraction
- no detail pages
- no broad pagination
- no full recall claim

A possible future StepStone target mode is controlled sampling, not full crawl.

A conservative controlled-sampling candidate is:

- maximum 2 result pages per search term
- maximum 50 result cards per search term
- no detail pages initially
- explicit delay between page requests
- fail-closed URL policy
- stop on unexpected HTML, blocking, redirect, empty page or repeated page signature
- source content minimization
- continued use only if Source Value justifies the risk and effort

## Fail-Closed URL Policy

For HTML sources, pagination must not generate arbitrary URLs.

A connector may only request pagination URLs that match documented and reviewed allowed URL patterns.

If a generated URL does not match an explicitly allowed pattern, the connector must not request it.

## Canonical Source Strategy

The project prefers canonical company or ATS sources over commercial aggregation sources whenever feasible.

The intended flow is:

1. discover a potential job through one or more sources
2. preserve the discovery observation in Bronze
3. attempt to identify a stronger canonical employer or ATS source
4. normalize canonical fields in Silver
5. preserve discovery and canonical lineage
6. resolve duplicates and source clusters in later Silver or Gold layers

## Fallback Strategy

If no canonical company or ATS source can be identified, the discovery source may remain as fallback.

Fallback records must remain distinguishable from verified canonical records.

## Source Value Evaluation

The project will introduce a Source Value Score as a future metric and decision criterion.

Candidate positive factors:

- coverage gain
- unique company rate
- unique job rate
- canonical match rate
- early discovery value
- field completeness
- field reliability

Candidate negative factors:

- legal or terms-of-service sensitivity
- maintenance complexity
- parser fragility
- request volume
- data noise rate
- duplicate rate
- operational failures

Example scoring direction:

    source_value_score =
        value_score
        - risk_penalty
        - maintenance_penalty

Commercial aggregation sources with low incremental value and elevated risk may later be reduced, downgraded to limited probes or removed entirely.

## Dashboard and Portfolio Positioning

The dashboard should focus on:

- personal job discovery
- source transparency
- canonical source identification
- search-term quality
- source value evaluation
- duplicate and overlap analysis
- application workflow support
- market intelligence

The dashboard should avoid:

- republishing full third-party job advertisements
- storing or rendering complete HTML pages
- acting as an alternative public job board
- hiding original source attribution

## Consequences

### Positive

- clearer distinction between discovery and canonical data
- more defensive treatment of commercial aggregation platforms
- better alignment with Bronze, Silver and Gold architecture
- stronger foundation for cross-source deduplication
- explicit source risk and value evaluation
- reduced risk of accidentally building a full crawler

### Negative

- more design work before adding pagination
- StepStone and similar sources remain sensitive and require careful handling
- canonical source discovery will add complexity
- Source Value scoring needs future metrics and validation

## Follow-up Work

1. document source strategy guidelines as a visible project design guide
2. update source capability documentation with source roles and acquisition modes
3. update StepStone documentation with its controlled discovery role
4. add a StepStone URL policy and pagination boundary probe
5. design controlled sampling with hard caps
6. prototype canonical company or ATS source discovery
7. define Source Value Score metrics
8. build search-term quality analysis with acquisition-scope context
9. later design cross-source duplicate candidates and canonical job clusters in Silver or Gold
