# StepStone Source Analysis

## Status

Initial source analysis in progress.

No production connector has been implemented yet.

## Purpose

This document evaluates StepStone as a potential job data source for the job application pipeline.

The goal is to understand whether StepStone can be integrated responsibly and technically cleanly before implementing a connector.

This is intentionally not a connector implementation document.

It documents source behavior, risks, open questions and a possible connector path.

---

## Current Repository State

A StepStone connector skeleton exists in `src/connectors/stepstone.py`.

The connector is intentionally not implemented yet.

Current behavior:

- the connector can be imported
- `fetch_jobs()` is not implemented
- calling the connector raises `NotImplementedError`
- no production StepStone ingestion exists yet

This matches the intended architecture path:

1. source analysis
2. limited technical spike
3. connector decision
4. production connector only if justified

---

## Source Type

| Dimension | Assessment |
|---|---|
| Source category | Commercial job portal |
| Market relevance | High |
| Geographic relevance | High for German job market |
| Current implementation status | Prepared connector skeleton only |
| Recommended next step | Limited technical spike after evaluation |
| Production connector readiness | Not ready |

---

## Evaluation Scope

This analysis should clarify whether StepStone is suitable for:

- production ingestion
- limited ingestion
- discovery-only usage
- deferral
- rejection

The evaluation should focus on technical feasibility, data quality, operational risk and responsible usage.

---

## Candidate URL and Access Questions

The source analysis should answer:

- how search URLs are structured
- whether keyword and location filters are encoded in stable paths or query parameters
- whether pagination has stable URLs
- whether job detail pages contain stable identifiers
- whether the same job can appear under multiple URLs
- whether relevant metadata is visible in HTML or embedded structured data
- whether a non-browser HTTP request is sufficient
- whether consent, blocking or anti-bot behavior appears during limited access

No broad crawling should be performed during this phase.

---

## Expected Search Result Fields

Potentially relevant search result fields:

| Field | Assessment |
|---|---|
| Job title | to evaluate |
| Company | to evaluate |
| Location | to evaluate |
| Remote / home-office hint | to evaluate |
| Salary teaser | to evaluate |
| Snippet / summary text | to evaluate |
| Relative publication age | to evaluate |
| Result count | to evaluate |
| Detail link | to evaluate |
| External job identifier | to evaluate |

Potential mapping:

| Source Field | Candidate Pipeline Field |
|---|---|
| Job title | `title` |
| Company | `company_name` |
| Location | `location` |
| Remote / home-office hint | raw metadata, later `remote_type` if normalized |
| Snippet | raw metadata or description snippet |
| Relative publication age | raw metadata |
| Detail link | `source_url` |
| Stable ID from URL or page data | `external_job_id` |

---

## Expected Detail Page Fields

Potentially relevant detail page fields:

| Field | Assessment |
|---|---|
| Job title | to evaluate |
| Company | to evaluate |
| Location | to evaluate |
| Employment type | to evaluate |
| Remote / home-office information | to evaluate |
| Publication age or publication date | to evaluate |
| Job description | to evaluate |
| Responsibilities / tasks | to evaluate |
| Requirements / candidate profile | to evaluate |
| Benefits | to evaluate |
| Company metadata | to evaluate |

Detail pages may be necessary for reliable Silver-layer mapping, but fetching detail pages increases request volume and operational risk.

A technical spike should therefore limit detail-page access to a very small number of examples.

---

## Identifier Assessment

A future StepStone connector needs a stable external job identifier.

Candidate strategies:

| Strategy | Assessment |
|---|---|
| Numeric ID from detail URL | to evaluate |
| Canonical URL | to evaluate |
| Embedded structured job ID | to evaluate |
| Content hash fallback | possible but weaker |

Open validation questions:

- Does the same job keep the same identifier across search queries?
- Is the identifier stable over time?
- Are there duplicate URLs for the same job?
- Are inline URLs canonical or presentation-specific?
- Is there a better canonical ID embedded in the page?

Current assessment:

`identifier_quality = unknown`

---

## Filtering Assessment

StepStone should not be assumed to support the full canonical search intent until evaluated.

| Filter | Assessment |
|---|---|
| Keyword | to evaluate |
| Location | to evaluate |
| Radius | to evaluate |
| Employment type | to evaluate |
| Remote | to evaluate |
| Publication date | to evaluate |
| Sorting | to evaluate |
| Pagination | to evaluate |

Open validation questions:

- How are multi-word keywords represented?
- How are German umlauts handled?
- Does radius filtering exist and remain stable?
- Does remote filtering exist and remain stable?
- Does sorting change result URLs?
- Are filters represented in paths, query parameters or client-side state?

Current assessment:

`filtering_capability = unknown`

---

## Pagination Assessment

Pagination must be evaluated before any connector implementation.

Candidate models:

- page-number based pagination
- query-parameter based pagination
- dynamic loading
- server-rendered first page with client-side continuation
- unknown or unstable pagination

Open validation questions:

- Does page 2 have a stable URL?
- Is result ordering stable?
- Can pagination be traversed without browser automation?
- Is there a responsible page limit for a spike?
- Is total result count available and reliable?

Current assessment:

`pagination_model = unknown`

---

## Data Completeness Assessment

Potential strengths:

- broad German job market coverage
- likely useful title, company and location data
- possible remote or home-office hints
- possible detail-page text for future role classification
- possible richer metadata than some ATS boards

Potential limitations:

- publication information may be relative instead of exact
- metadata consistency may vary by posting
- some fields may be UI-oriented rather than canonical
- detail pages may be required for full extraction
- parsed HTML may contain duplicated or promotional text
- salary information may be incomplete or teaser-based

---

## Operational Risk Assessment

| Risk Dimension | Initial Assessment |
|---|---|
| Rate limit risk | unknown |
| Blocking risk | medium to high |
| Layout change risk | medium to high |
| Maintenance effort | high |
| Legal / ethical risk | high until clarified |
| Detail page request volume risk | high |
| Browser automation risk | high |

Rationale:

StepStone is a commercial job portal, not an official public API or simple ATS board endpoint.

Automated ingestion is therefore more sensitive than ingestion from sources such as the Bundesagentur für Arbeit API or public ATS board endpoints.

A production connector should not be implemented until legal, ethical and operational constraints have been reviewed.

---

## Responsible Use Constraints

A future technical spike should be limited and cautious.

Recommended constraints:

- no broad crawling
- no high-frequency requests
- no parallel fetching
- no login-protected areas
- no circumvention of access controls
- no bypassing of anti-bot systems
- no production persistence during the spike
- no mass detail-page fetching
- document every inspected URL pattern
- prefer employer-origin sources where feasible

If StepStone links to employer career pages, the long-term architecture may prefer using StepStone as a discovery source while employer pages or ATS boards become canonical sources where feasible.

---

## Heartbeat Strategy

A productive heartbeat strategy is not defined yet.

Candidate strategies:

| Strategy | Assessment |
|---|---|
| Search page status check | possible but operationally sensitive |
| Lightweight keyword/location check | possible for spike only |
| Detail page check | not preferred |
| No automated heartbeat | possible if risk remains high |

Recommended current value:

`heartbeat_strategy = not_defined`

A StepStone heartbeat should not be implemented before source evaluation and responsible-use constraints are clear.

---

## Candidate Connector Path

### Stage 1: Source Analysis

Document:

- URL path patterns
- visible fields
- identifier candidates
- pagination behavior
- metadata availability
- responsible-use constraints
- heartbeat feasibility

Status:

`in progress`

### Stage 2: Limited Technical Spike

Possible branch:

`spike/stepstone-source-probe`

Possible script:

`scripts/analyze_stepstone_source.py`

Scope constraints:

- one keyword
- one location
- one search result page
- no broad pagination
- no mass detail-page fetching
- no persistence into production tables
- output only local analysis artifacts or console summary

The spike should answer:

- Can search result cards be extracted reliably?
- Can detail links be extracted reliably?
- Can stable identifiers be extracted?
- Is one detail page enough to map core fields?
- Does the HTML contain stable enough markers?
- Is a non-browser HTTP request sufficient?
- Are there blocking or consent issues?

### Stage 3: Connector Decision

Only after Stage 2 should the project decide between:

| Option | Meaning |
|---|---|
| `production_connector` | Implement StepStone as normal connector |
| `limited_connector` | Implement with strict limits and warnings |
| `discovery_only` | Use only to identify employer-side sources manually |
| `defer` | Do not implement for now |
| `reject` | Do not implement due to risk or instability |

### Stage 4: Production Connector

A production connector would require:

- explicit capability profile
- stable external ID strategy
- cautious request strategy
- error handling
- source-specific tests
- documentation updates
- dashboard interpretation notes
- heartbeat decision

---

## Initial Capability Profile

| Dimension | Current Assessment |
|---|---|
| Access model | `html_pages` / to evaluate |
| Filtering capability | `unknown` |
| Identifier quality | `unknown` |
| Publication date quality | `unknown` |
| Pagination model | `unknown` |
| Rate limit risk | `unknown` |
| Blocking risk | `medium` to `high` |
| Layout change risk | `medium` to `high` |
| Maintenance effort | `high` |
| Legal / ethical risk | `high` until clarified |
| Heartbeat strategy | `not_defined` |
| Ingestion strategy | `experimental_spike` |

---

## Limited Probe Results

A limited technical probe was executed with `scripts/analyze_stepstone_source.py`.

Scope:

- two single search-page requests
- no crawling
- no pagination
- no database writes
- no mass detail-page fetching

Tested URLs:

- `https://www.stepstone.de/jobs/data-engineer/in-hannover`
- `https://www.stepstone.de/jobs/data-scientist/in-hannover`

Observed results:

| Signal | Observation |
|---|---|
| HTTP status | `200` for both tested URLs |
| Consent or bot block | Not observed during the limited probe |
| Content type | `text/html; charset=utf-8` |
| HTML size | Approximately 1.18 MB to 1.23 MB |
| Page title | Contains search term, result count, location and date |
| Meta robots | `index,follow` observed |
| StepStone links | More than 150 links per tested page |
| Candidate job detail links | 25 candidate detail links per tested page |
| Candidate numeric IDs | 25 candidate IDs per tested page |

Important interpretation:

The probe confirms that candidate StepStone detail links and numeric ID candidates can be extracted from public search result HTML.

However, the number of extracted candidate detail links does not necessarily match the result count shown in the page title.

For example, the `data-scientist` search title showed 10 jobs, while the probe extracted 25 candidate detail links.

This means the current extraction logic identifies candidate job links, but does not yet distinguish primary search results from related, recommended or otherwise embedded job links.

Connector implication:

A production connector must not simply ingest every detected detail link from the page.

A future spike must identify stable result-card boundaries or structured page data before deciding whether a reliable connector is feasible.

---

## Result Card Boundary Probe

A follow-up probe inspected whether extracted candidate job links can be mapped to stable search-result card boundaries.

Tested URL:

- `https://www.stepstone.de/jobs/data-engineer/in-hannover`

Observed boundary signals:

| Signal | Count |
|---|---:|
| Candidate job detail links | 25 |
| Candidate numeric IDs | 25 |
| `article` elements with `id="job-item-..."` and `data-testid="job-item"` | 25 |
| Title links with `data-testid="job-item-title"` | 25 |

No mismatches were found between extracted candidate IDs, article IDs and title-link IDs.

Current interpretation:

The tested page exposes a stable result-card boundary candidate:

~~~text
article[data-testid="job-item"]
└── a[data-testid="job-item-title"]
~~~

The numeric StepStone job ID appears consistently in both:

- the article element ID: `job-item-{id}`
- the job detail URL: `--{id}-inline.html`

Connector implication:

A future StepStone connector should prefer extracting primary results from explicit `article[data-testid="job-item"]` containers instead of collecting all matching detail links globally from the page.

This reduces the risk of ingesting unrelated embedded, recommended or duplicate job links.

Remaining limitation:

This finding is based on a limited single-page probe.

Before implementing production ingestion, the boundary should be tested across additional search terms, result counts and pagination states.

---

---

## Structured Card Extraction Probe

A follow-up probe tested whether the stable result-card boundary can be used to extract structured card-level fields without opening detail pages.

Script:

- `scripts/analyze_stepstone_structured_cards.py`

Tested URL:

- `https://www.stepstone.de/jobs/data-engineer/in-hannover`

Observed structured card signals:

| Signal | Count |
|---|---:|
| Structured cards | 25 |
| Cards with title | 25 |
| Cards with company | 25 |
| Cards with location | 25 |
| Cards with detail URL | 25 |
| Cards where title URL ID matches article ID | 25 |

Observed quality rates:

| Metric | Rate |
|---|---:|
| Title coverage | 1.0000 |
| Company coverage | 1.0000 |
| Location coverage | 1.0000 |
| Detail URL coverage | 1.0000 |
| ID match rate | 1.0000 |

Extracted card-level fields:

- external job ID
- title
- company
- location
- detail URL
- raw href
- card HTML size
- title/article ID consistency
- selected `data-at` field values

Current interpretation:

The tested StepStone search page exposes enough structured card-level signals to extract a useful first search-result snapshot from `article[data-testid="job-item"]` containers.

The most reliable fields in the limited probe are:

- external job ID
- title
- company
- location
- detail URL

The card text and snippet-like fields are available, but should be treated as noisy raw evidence. Several fields contain duplicated text, promotional labels or mixed metadata such as badges, salary prompts, home-office labels and time-ago values.

Connector implication:

A future StepStone connector spike can use the structured card extraction approach as a safer next step than global link extraction.

The connector should:

- iterate only over `article[data-testid="job-item"]`
- extract title from `data-at="job-item-title"`
- extract company from `data-at="job-item-company-name"`
- extract location from `data-at="job-item-location"`
- extract the detail URL from the title link
- validate that the article ID matches the URL ID
- store noisy card text only as raw source evidence, not as trusted canonical fields

Remaining limitation:

This finding is still based on a limited single-page probe.

Before implementing production ingestion, the approach should be tested across additional search terms, result counts, empty-result pages and pagination states.


## Terminology Alignment

This source analysis uses the shared project terminology from `docs/glossary.md` and ADR-022.

StepStone-specific HTML markers such as `article[data-testid="job-item"]` and `a[data-testid="job-item-title"]` are treated as observed source signals for **result cards** and title links. They are not canonical entities outside the StepStone source analysis.

The StepStone numeric ID extracted from URLs or article IDs is treated as an **external job ID** candidate. A later Silver-layer model must still map source-specific observations into the canonical job model.

## Current Decision

StepStone should not be implemented as a production connector yet.

The next appropriate step is a limited technical spike after this source analysis is reviewed.

The spike should be used to decide whether StepStone is suitable for:

- production ingestion
- limited ingestion
- discovery-only usage
- deferral
- rejection
