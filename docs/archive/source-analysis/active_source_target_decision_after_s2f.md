# Active Source Target Decision after S2F — S2G

## Purpose

S2G turns the S2E employer-candidate review and the S2F employer-origin validation into a documented next-source decision.

The goal is not to implement a connector yet. The goal is to decide which single employer-origin or ATS-near path deserves the next controlled manual validation step before any active source-target implementation.

This keeps the project between two unsafe extremes:

- treating every reachable career page as connector-ready
- refusing source expansion even when repeated evidence shows a strong candidate

## Input Evidence

S2G uses two prior review layers.

### S2E — Employer Candidate and False-Negative Review

S2E quantified current visibility and false-negative risk across strategic and discovered employers.

Relevant S2E interpretation for S2G:

- some employers are already visible in Silver
- some employers are visible only in Raw or through bounded discovery signals
- some expected candidates remain missing or weakly visible
- raw-only or missing status does not automatically mean a new connector is required
- the next source decision should consider source coverage, search terms, fetch limits and Silver filtering together

### S2F — Employer-Origin Source Candidate Validation

S2F checked one configured public career/search URL for each selected employer candidate.

Relevant S2F interpretation for S2G:

- all four first-pass candidates were reachable with HTTP 200
- no candidate produced a conservative static ATS hint
- HDI and Finanz Informatik exposed profile-term signals in static HTML
- Finanz Informatik exposed both `Data Engineer` and `Business Intelligence`
- Finanz Informatik produced the strongest rough job-signal count by a wide margin
- ROSSMANN and WERTGARANTIE remained reachable but did not expose current profile terms in static HTML

## Candidate Comparison

| Candidate | S2F reachability | Static profile-term signal | Rough job signal | Strategic fit | S2G interpretation |
|---|---:|---|---:|---|---|
| Finanz Informatik | 200 | `Data Engineer`, `Business Intelligence` | Very high | Strong IT/Data-domain fit and regional relevance | Best next manual validation candidate. |
| HDI Group | 200 | `Analytics Engineer` | Low / focused | Strong insurance-domain and Hannover relevance | Keep as strategic candidate, but do not pick first. |
| Dirk Rossmann GmbH | 200 | none in static HTML | Medium | Regional relevance | Keep for later; likely needs dynamic/API/manual inspection. |
| WERTGARANTIE Group | 200 | none in static HTML | Low | Useful control case | Defer; not strong enough as next active target. |

## Decision

S2G selects:

```text
Finanz Informatik GmbH & Co. KG
```

as the next candidate for controlled manual source-target validation.

Candidate source family:

```text
employer_origin:finanz_informatik
```

Candidate source type:

```text
employer_origin_career_site
```

Configured S2F URL:

```text
https://www.f-i.de/stellen-finden
```

## What This Decision Allows

This decision allows the next implementation block to investigate Finanz Informatik manually and defensively.

Allowed next steps:

- inspect whether the public career/search page exposes stable job result data
- identify whether a clean ATS-near endpoint or structured data source exists
- check whether relevant query parameters, filters or static result payloads are available
- evaluate whether one bounded source target can be activated without crawling
- document legal, operational and maintenance risks before implementation

## What This Decision Does Not Allow

This decision does not implement a connector.

It does not allow:

- broad crawling of the Finanz Informatik career site
- detail-page crawling by default
- browser automation as a default acquisition strategy
- treating rough job-signal counts as parser evidence
- adding a production ingestion profile before manual review
- promoting employer-origin data into Silver without a clear Bronze contract

## Non-Selected Candidates

### HDI Group

HDI remains highly relevant because of the insurance-domain fit and the visible `Analytics Engineer` signal. It is not selected first because the S2F signal is narrower than Finanz Informatik and the immediate Data/BI alignment is weaker.

HDI should remain in the watchlist for a later employer-origin or ATS-near validation block.

### Dirk Rossmann GmbH

ROSSMANN remains regionally interesting and reachable. However, S2F did not find current profile-term matches in static HTML. This may mean the page is dynamic, uses an internal API or requires more careful manual inspection.

ROSSMANN should not be the first active source-target candidate after S2F.

### WERTGARANTIE Group

WERTGARANTIE remains useful as a control case for aggregator-versus-origin validation. The current S2F signal is too weak for the next active candidate decision.

## Risk Notes

The Finanz Informatik signal is promising, but not sufficient for immediate connector work.

Main risks:

- the page may be dynamic and not expose stable result data in static HTML
- a high rough job-signal count may come from repeated or non-result page text
- the visible profile terms may not correspond to extractable current jobs
- the employer-origin path may still require an ATS-specific approach
- legal and operational boundaries must be checked before any automated acquisition

## Decision Outcome

S2G outcome:

```text
Selected for next manual validation: Finanz Informatik
Implementation status: no connector yet
Activation status: blocked until manual source-path review
Other candidates: retained for later review, not selected now
```

## Next Block

The next block should be:

```text
S2H — Finanz Informatik Origin Path Manual Validation
```

S2H should remain read-only and defensive. It should determine whether Finanz Informatik exposes a clean, bounded and maintainable acquisition path worth implementing as a controlled source target.
