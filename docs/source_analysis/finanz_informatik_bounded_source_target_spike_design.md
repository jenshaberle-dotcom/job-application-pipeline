# Finanz Informatik Bounded Source-Target Spike Design — S2I

## Purpose

S2I defines the design boundaries for a later Finanz Informatik source-target spike.

This is still not a production connector. The purpose is to define how a small, read-only, export-first spike could be implemented without repeating the Greenhouse mistake of broad, weakly differentiated ingestion.

S2I follows:

- S2E — Employer candidate and false-negative review
- S2F — Employer-origin source candidate validation
- S2G — Active source-target decision after S2F
- S2H — Manual Finanz Informatik origin-path review

## Decision Context

S2H showed that Finanz Informatik exposes a technically rich origin path.

The main finding was not duplicate noise. The main risk is relevance and scope control.

The path contains many potentially useful open-position links, but also roles that are outside the project scope:

- dual-study roles
- Ausbildung roles
- working-student roles
- trainee roles
- non-target locations
- broad IT or management roles without clear profile fit

Therefore, the spike must be designed as a bounded relevance-first source-target spike.

## Design Decision

A future Finanz Informatik spike may be implemented only as a read-only, export-first source-target spike with explicit gates.

The spike may inspect only configured source URLs and allowed URL patterns.

The spike must not ingest all Finanz Informatik jobs into Bronze by default.

The spike must first produce reviewable export artifacts.

Only after review should any Bronze persistence be considered.

## Allowed Acquisition Scope

The initial spike may use only explicitly configured URLs under the Finanz Informatik career domain.

Allowed candidate URL pattern:

    /de/karriere/offene-stellen/

Allowed employer domain:

    f-i.de

Allowed ATS-near candidate domain for manual review only:

    finanz-informatik.onapply.de

The OnApply domain must not be treated as automatically approved. If used, it needs a separately documented boundary.

## Excluded Acquisition Scope

The spike must exclude:

- arbitrary crawling
- unbounded pagination
- detail-page fetching without a documented request cap
- browser automation
- login- or session-dependent access
- broad OnApply crawling
- storing raw HTML in the database
- automatic Bronze persistence
- non-career pages
- social-media links
- external marketing pages

## Required URL Gates

The spike must distinguish at minimum:

| Path Type | Handling |
|---|---|
| `/de/karriere/offene-stellen/...` | candidate job path |
| `/de/karriere/duales-studium-ausbildung/...` | exclude |
| `/de/karriere/das-teamfi/...` | exclude as career content |
| `/de/karriere/karriereevents` | exclude |
| `finanz-informatik.onapply.de/details/...` | manual review candidate only |
| external social/contact links | exclude |

## Required Relevance Gates

A later spike must classify each candidate before any persistence decision.

### Positive Signals

A candidate should be considered stronger when it matches one or more of:

- Hannover
- remote / Germany-wide relevance
- Data
- Daten
- Analytics
- Business Intelligence
- BI
- SQL
- Python
- AI / KI
- Data Integration
- Data Governance
- Data Platform
- Product Owner / product-adjacent IT role
- Business Analyst with clear IT/Data/AI context

### Exclusion Signals

A candidate should be excluded or downgraded when it matches one or more of:

- duales Studium
- Ausbildung
- Werkstudierende / Werkstudent
- Praktikum
- Trainee
- Active Sourcing student role
- HR-only role
- payroll-only role
- pure management role without profile fit
- location outside target scope without remote indication

## Recommended Spike Output

The first implementation should not write to the database.

It should export:

    exports/s2i_finanz_informatik_source_target_spike/

Recommended files:

- `finanz_informatik_spike_candidates.csv`
- `finanz_informatik_spike_relevance_summary.csv`
- `finanz_informatik_spike_manifest.json`
- `finanz_informatik_spike_review.md`

The export should include at least:

- source page URL
- candidate URL
- candidate title or slug
- path classification
- location signal
- profile-term signals
- exclusion signals
- recommendation
- reason
- whether detail fetching would be needed later
- source evidence fields available without detail fetch

## Request Boundaries

The initial spike should use defensive request limits:

- one configured listing/source URL at first
- no detail pages in the first pass unless separately approved
- short timeout
- explicit user agent
- no retry storm
- no parallel request burst
- no scheduled execution
- no database writes
- no raw HTML persistence

If a later detail-page pass is considered, it must be separately bounded with:

- maximum detail-page count
- only candidates that passed listing-level gates
- export-first behavior
- explicit stop conditions

## Stop Conditions

The spike should stop or defer implementation when:

- relevant jobs require broad crawling
- relevant jobs require browser automation
- relevant jobs require login/session access
- OnApply usage boundaries are unclear
- candidate URLs cannot be filtered reliably
- relevance gates produce too many false positives
- no Hannover/remote/Germany-relevant profile matches are found
- the source creates more operational burden than source value

## Bronze Persistence Decision

Bronze persistence is not part of the first spike.

A later Bronze ingestion decision requires:

- stable external job IDs or deterministic source-specific IDs
- clear source-name convention
- source-target naming aligned with existing connector terminology
- relevance decision fields preserved as evidence
- no broad all-jobs load
- explicit run metadata
- tests covering exclusion gates
- documentation update

## Expected Source Value

Finanz Informatik is valuable because it tests an important source family:

- employer-origin career pages
- Germany/Hannover relevance
- IT/Data-adjacent employer
- rich but noisy job universe
- relevance-first source acquisition

This makes it a strong portfolio example if handled defensively.

It should demonstrate that the project can identify a promising source and still refuse broad ingestion when relevance risk is high.

## Non-Goals

S2I does not implement the spike.

S2I does not add a connector.

S2I does not activate a source target.

S2I does not write to the database.

S2I does not approve OnApply crawling.

S2I does not approve all-job ingestion.

S2I does not replace Silver-gate analysis.

## Next Step

The next implementation block may be:

    S2J — Finanz Informatik export-first spike

S2J should implement a small script or spike that reads one configured source page, extracts candidate links, applies the S2I gates and writes review artifacts under `exports/`.

Only after S2J review should a connector or Bronze persistence decision be discussed.
