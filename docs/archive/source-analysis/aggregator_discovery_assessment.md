# Aggregator / Discovery Source Family Assessment — S2B

## Purpose

S2B evaluates commercial aggregators as a source family before the project adds another active source target.

The goal is not to prove that aggregators can be scraped. The goal is to decide whether they can responsibly improve the project as discovery inputs for:

- relevant employers in the Hannover region or remote in Germany
- role-title vocabulary not covered by current search terms
- false-negative analysis
- employer-origin or ATS target selection
- market-signal comparison against Bundesagentur, StepStone, Greenhouse and Personio

This assessment follows the S2 boundary in `docs/archive/source-analysis/source_strategy_review.md`.

## Current Decision

Aggregators should not become broad automated Bronze ingestion sources at this stage.

Their best near-term role is:

```text
discovery_source
```

A bounded `market_signal_sampler` may be considered later. A direct ingestion connector requires a much higher bar and must not be created only because public job-search pages exist.

## Assessment Summary

| Aggregator | Likely value | Acquisition / policy risk | Recommended project role | Current decision |
|---|---|---|---|---|
| LinkedIn | Very high employer and recruiter discovery value; strong signal for current market language. | High for automation. LinkedIn Jobs terms restrict automated scraping/data extraction unless expressly authorized. | Manual or human-in-the-loop discovery; candidate employer and vocabulary discovery. | Do not build automated ingestion now. |
| XING | High DACH relevance; useful for German employer discovery and alternative role titles. | Medium to high. Available official XING job integration API is employer/vendor posting-oriented, not a general job-search ingestion API. | Research-only discovery and employer shortlist support. | Do not build automated ingestion now. |
| Indeed | Broad job-market visibility and useful duplicate/coverage comparison potential. | High for uncontrolled ingestion. Official APIs are partner/integration oriented and require approved use; developer terms constrain database building and scraping-style use. | Discovery-only unless an approved/defensible integration path exists. | Do not build automated ingestion now. |
| Glassdoor | Employer context, salary/review context and company discovery. Lower primary job-feed value. | High for automation. Terms restrict automated agents and scraping/mining without written permission. | Manual employer/context enrichment only. | Do not build automated ingestion now. |

## Interpretation

Aggregators are valuable because they show where the market is visible to humans. That does not automatically make them good automated data sources.

For this portfolio project, the strongest engineering story is:

1. use aggregators to discover employers, missing vocabulary and possible false negatives
2. validate the discovered companies against employer-origin pages or ATS boards
3. ingest only the defensible source target when the acquisition path is clear
4. keep aggregator evidence as discovery lineage, not canonical source evidence

This avoids repeating the early broad Greenhouse lesson in a more fragile commercial-platform context.

## Per-Source Notes

### LinkedIn

LinkedIn is likely the strongest discovery surface for professional roles and company visibility.

Useful signals:

- relevant companies appearing repeatedly in Hannover / Germany / remote searches
- role-title variants around data engineering, analytics engineering, platform, product and requirements roles
- recruiter phrasing and skill vocabulary
- possible source-target candidates that point to employer-origin boards

Boundary:

- no logged-in automation
- no account automation
- no headless browser workflow
- no automated scraping/data extraction as a project connector

Recommended use:

```text
manual_discovery_source
```

### XING

XING remains relevant because of its DACH focus, especially for German employers that may be underrepresented on international ATS boards.

Useful signals:

- German role-title vocabulary
- regional employer names
- SMEs and mid-market employers
- Product Owner, Requirements, Data and IT roles with German naming patterns

Boundary:

- treat official API access as posting/vendor integration unless proven otherwise
- do not assume a public job-search API exists
- no broad scraping connector without a separate risk review

Recommended use:

```text
manual_discovery_source
```

### Indeed

Indeed can be useful for broad market visibility and for finding employer names that the current source set misses.

Useful signals:

- employer frequency in regional or remote-in-Germany searches
- job-title variants not found through current search terms
- duplicate/overlap comparison against BA and StepStone
- company-origin URLs worth validating later

Boundary:

- no uncontrolled crawling
- no permanent aggregator-derived job database unless an approved integration path exists
- no attempt to replicate Indeed search experience locally

Recommended use:

```text
discovery_source
```

A later `market_signal_sampler` spike is possible only if it is bounded, documented and does not become raw-volume collection.

### Glassdoor

Glassdoor is weaker as a primary job-feed source for the current project, but useful as company/context signal.

Useful signals:

- employer context
- salary and company review context for later application prioritization
- employer discovery when combined with manual review

Boundary:

- no automated scraping/mining connector
- no review/salary harvesting
- no use as canonical job source

Recommended use:

```text
reference_only
```

## Discovery Workflow Candidate

The next implementation should not be an aggregator connector.

A better next building block is a small, reviewable discovery workflow:

```text
time-boxed aggregator source research -> candidate employer/source target -> validation -> optional ingestion target
```

Possible lightweight artifacts:

- an optional future discovery log document, if this historical workflow is reopened
- `docs/archive/source-analysis/employer_origin_source_candidate_review.md`
- a review-only evidence template, if manual discovery evidence becomes frequent enough
- later, a table such as `source_discovery_observations` if manual evidence becomes frequent enough

Minimum useful fields for research-only discovery evidence:

| Field | Meaning |
|---|---|
| `observed_at` | When the source was reviewed. |
| `aggregator_name` | LinkedIn, XING, Indeed, Glassdoor or another aggregator. |
| `search_query` | Human search query used. |
| `market_scope` | Hannover, 50km, Germany remote, etc. |
| `observed_company` | Candidate employer name. |
| `observed_role_title` | Role title seen in the aggregator. |
| `origin_candidate_url` | Employer-origin or ATS URL to validate, if found. |
| `discovery_reason` | Why this candidate may add value. |
| `next_action` | Manual review, validate origin target, ignore, watchlist. |

This keeps the project explainable: aggregators help discover, but the platform still prefers employer-origin or ATS-near evidence for persistent ingestion.

## Decision Gate for S2C

S2C has been documented in `docs/archive/source-analysis/aggregator_discovery_feasibility_matrix.md`.

The key refinement is that legal / terms risk is a hard gate. A source can have high discovery value and still be unsuitable for automated acquisition when reading, storing, reproducing or documenting the access path is not defensible enough for the project.

S2C should select the next source move from these options:

1. create a aggregator source-research log before adding any more ingestion sources
2. validate one employer-origin candidate, preferably HDI, Finanz Informatik or ROSSMANN
3. run a tiny API/documentation review for an automation-friendlier aggregator such as Arbeitnow, Adzuna, Jooble or Remotive
4. add one more already validated ATS/Greenhouse candidate only if it clearly improves German/remote relevance
5. pause source expansion and improve search-intent / term-set normalization first

The preferred direction is option 1 first. It can discover or challenge the next employer-origin candidate without forcing any aggregator into a connector.

## References Checked

This assessment is based on the current official documentation / terms checked during S2B:

| Platform | Reference type | Interpretation for this project |
|---|---|---|
| LinkedIn | LinkedIn Jobs Terms and Conditions | Automated scraping/data extraction needs explicit authorization; no connector now. |
| Indeed | Indeed Partner Docs and Developer Agreement | APIs are partner/integration-oriented and approved-use constrained; no broad independent ingestion now. |
| XING | XING E-Recruiting API Documentation | API is oriented toward posting and monitoring job ads for customers/contracts; not treated as a search ingestion API. |
| Glassdoor | Glassdoor Terms | Automated agents and scraping/mining require written permission; no connector now. |

## Non-Goals

S2B does not implement new connectors.

S2B does not authorize browser automation, login automation, account automation, detail-page harvesting, review scraping or salary scraping.

S2B does not classify aggregator results as canonical job evidence.

S2B does not prevent later aggregator use. It requires that later use be bounded, defensive and explicitly justified.
