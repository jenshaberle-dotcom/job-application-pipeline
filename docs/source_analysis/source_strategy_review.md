# Source Strategy Review — S2

## Purpose

S2 starts after the first controlled source-coverage expansion target was activated: `greenhouse:contentful`.

The purpose of this review is to avoid continuing source expansion by habit. The project has already learned that more source targets and more raw rows do not automatically create more value.

S2 therefore asks which source family or source target should be expanded next for the user's actual search context:

```text
Hannover region or remote in Germany
```

The review must compare source value, acquisition risk, operational effort and explainability before adding more Greenhouse, Personio, employer-origin or aggregator targets.

## Why S2 Exists Now

S1 deliberately stopped after one controlled Greenhouse addition.

The active system now includes:

- a stable German public API baseline through Bundesagentur
- Greenhouse ATS boards with Stripe and Contentful
- selected Personio / employer-near ATS targets
- a defensively limited StepStone aggregator signal

This is enough to start evaluating source strategy without immediately adding another board.

Known interpretation caveats still apply:

- `greenhouse:stripe` contains historical burden and must not be treated as clean market volume
- Bundesagentur has a first-source time advantage and strong regional Silver evidence
- StepStone intentionally fetches only one full result page and is not a full-market crawl
- Personio targets are employer-near but currently low volume
- `greenhouse:contentful` is a new coverage change and needs scheduled observation before long-term value claims

## Primary Question

The primary S2 question is:

```text
Which next source move creates unique, explainable value for Hannover or remote-in-Germany job search intelligence?
```

A source move can be valuable even when it does not immediately become a production ingestion connector. For example, an aggregator may be useful as a discovery source for employers, titles or vocabulary gaps, while still being unsuitable as a broad automated ingestion source.

## Source Families Under Review

| Source family | Current role | S2 review question |
|---|---|---|
| Bundesagentur | Official API and regional baseline. | Keep as benchmark; use to compare whether other sources add unique value. |
| Greenhouse | Employer-near ATS boards. | Does another board add German/remote relevance, or mostly duplicate low-value coverage? |
| Personio | Employer-near European ATS targets. | Which targets add unique employer-origin evidence rather than low-volume noise? |
| StepStone | Limited commercial aggregator signal. | Can it support discovery without broader crawling or higher operational risk? |
| Employer-origin sites | Potential canonical employer evidence. | Which known employers are worth targeted validation before connector work? |
| Aggregators | Potential discovery family. | Can LinkedIn, XING, Indeed or Glassdoor help discover relevant employers, titles and vocabulary without becoming uncontrolled scraping targets? |

## Aggregator Boundary

S2 treats commercial aggregators as a separate source family.

They should not automatically be modeled as canonical job sources. Their first possible role is discovery:

- discover relevant employers in Hannover or remote Germany
- discover alternative titles and vocabulary not covered by current search terms
- identify employer-origin boards worth validating
- compare whether BA, StepStone, Greenhouse and Personio miss important signals
- support false-negative analysis without committing to broad ingestion

Possible aggregator roles:

| Role | Meaning | Default stance |
|---|---|---|
| `discovery_source` | Used manually or semi-automatically to discover employers, titles or source targets. | Preferred first role. |
| `market_signal_sampler` | Used in a bounded way to understand market vocabulary or coverage gaps. | Possible after analysis. |
| `direct_ingestion_source` | Used as an automated Bronze ingestion source. | High bar; not assumed. |
| `canonical_source` | Treated as authoritative employer evidence. | Not preferred when employer-origin or ATS source exists. |

Aggregators must not be expanded into uncontrolled crawling. If they are evaluated technically, the evaluation should be defensive, bounded and documented before implementation.

## Candidate Groups To Reassess

S2 should reassess, not rediscover, the known candidate groups.

### Greenhouse / ATS boards

Carry forward:

- `greenhouse:commercetools` as validation evidence only
- `greenhouse:celonis` as reserve evidence only
- selected Personio targets only when employer relevance is clear

Do not add another Greenhouse board only because the connector already exists.

### Employer-origin candidates

Carry forward known employer-origin candidates from the selection matrix:

- HDI
- ROSSMANN
- Finanz Informatik
- WERTGARANTIE

These candidates should be reviewed for target quality, vocabulary fit and Hannover/remote relevance before implementation.

### Aggregator candidates

Evaluate aggregators as a family first:

- LinkedIn
- XING
- Indeed
- Glassdoor

The first question is not whether they can be scraped. The first question is whether they can responsibly and usefully improve discovery, source-target selection or false-negative analysis.

## Decision Gates

Before adding another active source target, S2 should answer:

1. Does the source improve Hannover or remote-in-Germany relevance?
2. Does it add unique companies, roles or vocabulary compared with BA, StepStone, Greenhouse and Personio?
3. Can the source be acquired defensively with bounded requests and transparent lineage?
4. Is the source better used as direct ingestion, discovery-only or manual review input?
5. Can the result be explained in source-value snapshots and future Gold views?
6. Does the expected value justify maintenance effort and operational risk?

## Allowed Outcomes

S2 may conclude any of the following:

- activate one additional validated company or ATS target
- keep Greenhouse expansion paused
- keep Personio expansion paused until a better target is identified
- treat aggregators as discovery-only for now
- build a small aggregator analysis spike before any ingestion decision
- prioritize employer-origin validation over more ATS boards
- update search terms before adding new sources

A decision to not build a connector can be a valid engineering outcome.

## Non-Goals

S2 does not implement broad ingestion from LinkedIn, XING, Indeed or Glassdoor.

S2 does not authorize large-scale Greenhouse or Personio expansion.

S2 does not redefine Bronze as strict pre-filtered storage. Bronze remains tolerant and raw-first.

S2 does not promote aggregator results into canonical source evidence without employer-origin or ATS validation.

## Next Implementation Shape

Recommended next small implementation block after this boundary document:

```text
S2B — Aggregator / discovery source family assessment
```

S2B should compare aggregators and employer-origin candidates as source-strategy options before selecting the next active ingestion target.
