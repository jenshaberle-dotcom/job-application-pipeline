# Aggregator Discovery Feasibility Matrix — S2C

## Purpose

S2C turns the S2B aggregator assessment into an explicit decision matrix.

The goal is not to force commercial job platforms into connectors. The goal is to decide which aggregators are useful, responsible and practical enough to support the project as discovery inputs for better employer-origin, ATS or company-board candidates.

A source with high market visibility can still be rejected when access, terms, storage, reproducibility or operational effort do not fit the project.

## Core Principle

Technical feasibility is not sufficient.

A source must also be acceptable from a legal, ethical, operational and documentation perspective.

```text
can_fetch != should_fetch
```

This is especially important for commercial aggregators. The project intentionally avoids fragile or legally ambiguous acquisition paths, even when they would be technically possible.

## Hard Gates

Before any aggregator can be considered for an automated probe or later connector, it must pass these hard gates.

| Gate | Question | Failure consequence |
|---|---|---|
| Legal / terms risk | Is the intended acquisition path allowed or clearly defensible under the platform terms, API terms and documented usage boundaries? | Do not automate. At most use as research-only discovery/reference input. |
| Official or documented access path | Is there a documented API, feed, partner interface or other explicit access path suitable for this use case? | Do not build a connector. |
| No login or account automation | Can the source be used without automating a personal login, browser session, account state or anti-bot workflow? | Do not automate. |
| Storage permission / evidence boundary | Can the project store at least minimal evidence in a way that is allowed, explainable and deletable? | Do not persist raw source content. |
| Reproducibility | Can the same query or access path be repeated and documented well enough to support source evaluation? | Treat as research-only discovery only. |
| Defensive acquisition | Can requests be bounded, rate-limited and kept non-aggressive? | Do not automate. |
| Project value | Does the source add employer, role, vocabulary or false-negative discovery value beyond existing sources? | Do not prioritize implementation. |
| Operational maintainability | Is the maintenance burden acceptable for a portfolio project? | Keep out of production ingestion. |

Legal / terms risk is a hard gate, not a soft score. A technically possible source should still be rejected if it relies on scraping, browser automation, unclear third-party data acquisition or terms that do not fit persistent storage.

A source that requires recurring manual monitoring to create value is not a suitable pipeline source. It may inform one-off or sporadic source research, but it should not become an operational workflow.

## Scoring Dimensions After Hard Gates

Only sources that do not fail a hard gate should receive deeper scoring.

| Dimension | Meaning |
|---|---|
| Discovery value | How well the source helps identify employers, role titles, skill vocabulary or false-negative candidates. |
| Hannover relevance | Whether the source can surface jobs or employers around Hannover / 50km. |
| Remote Germany relevance | Whether the source can identify remote roles relevant for Germany. |
| Data-engineering signal quality | Whether searches for Data Engineer, Analytics Engineer, ETL, Data Platform and related terms are meaningful. |
| Employer-origin handoff quality | Whether results help find direct career pages or ATS boards. |
| API / automation friendliness | Whether a documented, bounded technical path exists. |
| Noise level | Expected false positives and broad-market noise. |
| Evidence quality | Whether captured evidence is minimal, explainable and sufficient for candidate review. |
| Maintenance cost | Expected effort to keep the workflow working. |

## Source Role Categories

| Role | Meaning |
|---|---|
| `research_only_discovery_signal` | One-off or sporadic, time-boxed source-research input for employer, role-title, vocabulary or false-negative candidate review. It may create derived notes such as company name, observed query, platform, rough role/location signal and a link for later verification, but it must not become recurring manual monitoring, automated acquisition, raw job-content persistence or canonical job evidence. |
| `reference_only` | May inform the project context but should not become operational evidence. |
| `bounded_discovery_probe_candidate` | May justify a small, documented API or feed probe with strict limits. |
| `market_signal_sampler_candidate` | May later support aggregate market indicators, not canonical job evidence. |
| `not_recommended` | Value or access path does not justify use. |
| `existing_defensive_source` | Already implemented with documented limits, e.g. StepStone one-page result-card acquisition. |

## Initial Aggregator Feasibility Matrix

This matrix is an initial S2C classification. It does not implement access, create credentials, authorize scraping or create a connector.

| Aggregator | Discovery value | Access / legal feasibility | Automation friendliness | Initial role | Next action |
|---|---|---|---|---|---|
| LinkedIn | Very high | Low for this project unless a suitable approved API path with storage rights exists. | Low | `research_only_discovery_signal` | Use only during bounded source-research reviews for employer/vocabulary discovery; do not automate or monitor routinely. |
| XING | High for DACH | Limited for this use case; official job integration is posting/vendor oriented. | Low to medium only for approved vendor scenarios | `research_only_discovery_signal` | Use only during bounded source-research reviews for German employer and role-title discovery; do not build search ingestion. |
| Indeed | High | Unclear to low for independent broad ingestion; partner/API access is controlled. | Medium only with approved partner/API path | `research_only_discovery_signal` / `reference_only` | Assess only if an approved API path clearly fits; otherwise research-only discovery. |
| Glassdoor | Medium for employer context, lower for direct job-feed value | Low for automation without written permission. | Low | `reference_only` | Use only during bounded source-research reviews for employer context only; no harvesting and no operational job evidence. |
| StepStone | Medium to high for Germany | Already handled defensively with explicit limitation. | Medium under current one-page boundary | `existing_defensive_source` | Keep current bounded connector; no broad expansion without separate review. |
| Arbeitnow | Medium to high for Germany / remote discovery | Potentially better fit because it exposes an API-oriented job board surface. | Potentially medium to high | `bounded_discovery_probe_candidate` | Candidate for a small API/documentation review before any probe. |
| Adzuna | Medium to high for broad market and API experiment value | Potentially acceptable through official API/key model, subject to terms and storage review. | Medium to high | `bounded_discovery_probe_candidate` | Candidate for API terms review and tiny bounded market-signal probe. |
| Jooble | Medium; broad aggregator with likely noise risk | Potentially acceptable through documented REST API, subject to API terms and storage review. | Medium | `bounded_discovery_probe_candidate` | Candidate for API terms review; watch noise and duplicate risk. |
| Remotive | Medium for remote roles, lower for Hannover specificity | Potentially acceptable with public API and attribution/linkback constraints. | Medium | `market_signal_sampler_candidate` | Consider only for remote-market signal, not regional Hannover coverage. |

## Consequences for S2D

The next step should not be a connector implementation.

S2D is implemented as a bounded source-family evaluation workflow:

```text
S2D — Aggregator discovery candidate evaluation
```

See `docs/source_analysis/aggregator_discovery_candidate_evaluation.md`.

S2D evaluates hard-gated commercial aggregators and API-friendlier discovery candidates in one run. LinkedIn, XING, Indeed and Glassdoor remain research-only/reference-only unless a suitable approved access path exists. Arbeitnow, Adzuna, Jooble and Remotive are evaluated as bounded discovery-probe candidates, with no database writes and minimal evidence export only.

The expected output is not raw aggregator ingestion. The expected output is evidence for deciding whether to:

1. validate one employer-origin candidate,
2. create or reject a tiny bounded API probe for an API-friendlier aggregator,
3. expand an existing ATS source family,
4. pause source expansion and improve search-intent quality first.

Minimum useful S2D evidence:

- source-family hard-gate status
- platform-level recommendation
- candidate employer names, if probe matches exist
- search query used
- Hannover / remote Germany signal
- role / skill signal
- direct career page or ATS board candidate for follow-up, if derivable later

## Non-Goals

S2C does not implement a connector.

S2C does not authorize scraping, browser automation, login automation, account automation, CAPTCHA handling, proxy usage or third-party scraped-data APIs.

S2C does not treat high discovery value as permission to persist raw aggregator content.

S2C does not classify aggregator content as canonical job evidence.
