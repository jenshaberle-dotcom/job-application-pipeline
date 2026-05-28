# Source Target Selection Matrix — S1 Controlled Expansion

## Purpose

This document selects candidate source targets for the first controlled source-coverage expansion after the G1 window-function semantics and S1 coverage baseline.

It is intentionally not an implementation plan yet. It is a decision matrix that prevents ad-hoc source growth and keeps the project from repeating the early Greenhouse broad-fetch pattern.

The first expansion should add a small number of relevant targets:

```text
2-3 Greenhouse boards
1-2 Personio/ATS or employer-origin boards
optionally 1 highly relevant employer-specific board
```

The goal is broader market coverage, not raw-volume inflation.

## Selection Principles

A target is only a good S1 candidate when it adds explainable coverage.

Preferred properties:

- employer-origin or ATS-near signal
- Germany, Hannover, remote or strategically relevant market fit
- role relevance for Data Engineering, Analytics Engineering, Data Platform, Requirements Engineering, Product Owner or adjacent software/system roles
- stable, defensive and non-aggressive acquisition path
- local multi-term filtering is possible when server-side search is unavailable
- source target can be measured independently in source-value snapshots
- expected value is not only raw volume

Hard gates:

- unclear or risky acquisition behavior
- login, authentication bypass or non-defensive access requirement
- high duplicate or historical-burden risk without clear value
- no clear source-target identity
- target only adds volume that cannot be explained or evaluated

## Status Values

| Status | Meaning |
|---|---|
| `active` | Already an active source target/search profile. |
| `candidate` | Plausible target, but not selected for implementation yet. |
| `under_evaluation` | Candidate should be validated with a small defensive check before implementation. |
| `manual_review_needed` | Human review is required before connector/profile work. |
| `parser_or_target_gap` | Source appears relevant, but the current parser or URL target is not sufficient. |
| `batch_1_candidate` | Candidate is suitable for the first controlled expansion batch after validation. |
| `batch_1_reserve` | Good backup candidate if a higher-priority target fails validation. |
| `watchlist` | Keep observing, but do not implement in the first batch. |
| `defer` | Not now; may be useful later. |
| `do_not_build` | Do not implement unless the evidence changes materially. |

## Current Active Targets

These targets are already active and are not new S1 expansion candidates.

| Source target | Source family | Status | S1 interpretation |
|---|---|---|---|
| `bundesagentur_fuer_arbeit` | Bundesagentur | `active` | Strong official baseline, but first-source time advantage. |
| `greenhouse:stripe` | Greenhouse | `active` | Existing Greenhouse target; keep retained Silver evidence but do not generalize from legacy raw volume. |
| `greenhouse:contentful` | Greenhouse | `active` | First controlled S1 Greenhouse expansion target. Treat first 24h/7d/30d windows as `coverage_changed` until enough post-activation history exists. |
| `stepstone` | StepStone | `active` | Useful commercial-market signal; intentionally limited to one complete result page. |
| `personio:eraneos` | Personio | `active` | Low-volume employer-near signal. |
| `personio:1komma5grad` | Personio | `active` | Low-volume employer-near signal. |
| `personio:otl-akademie` | Personio | `active` | Low-volume employer-near signal. |
| `personio:schluetersche-mediengruppe` | Personio | `active` | Low-volume employer-near signal. |
| `personio:it-p` | Personio | `watchlist` | Active but no observed loaded jobs so far; do not use as positive value evidence yet. |

## Greenhouse Candidate Board Matrix

Greenhouse expansion must be controlled by board, not by wildcard/full-fetch habit.

| Candidate target | Proposed source target | Status | Rationale | Main caveat | S1 decision |
|---|---|---|---|---|---|
| Contentful | `greenhouse:contentful` | `active` | Technology platform with visible engineering/data-adjacent roles and Germany/Berlin relevance. Useful contrast to Stripe because it is another Greenhouse board but with a different company/domain profile. | First windows after activation are coverage-affected; value must be reviewed after scheduled runs and Silver processing. | Activated in S1D as the first controlled Greenhouse expansion target after defensive validation showed 89 total jobs and 2 matched jobs. |
| commercetools | `greenhouse:commercetools` | `batch_1_candidate` | Technology/product-platform employer with Germany/Berlin relevance. Useful for controlled Greenhouse breadth without adding many boards. | Board API slug and extraction stability must be verified. | Validate first, then add if matched yield and source-value evidence are acceptable. |
| Celonis | `greenhouse:celonis` | `batch_1_reserve` | Strong data/process-intelligence domain fit and German market relevance. | Public careers page and Greenhouse job-board access may not map cleanly to the existing board API contract; validate before relying on it. | Use as reserve if one primary Greenhouse board fails validation. |
| Additional Greenhouse board from ad-hoc search | n/a | `defer` | More boards would increase coverage. | More boards also increase coverage-change noise and historical burden risk. | Do not add until Batch 1 has been measured. |

## Employer-Origin / ATS Candidate Matrix

These targets are not active ingestion targets yet. They should not be treated as already connected.

| Candidate target | Proposed source target | Status | Rationale | Main caveat | S1 decision |
|---|---|---|---|---|---|
| HDI Group | `employer_origin:hdi` | `manual_review_needed` | Strategically relevant insurance employer; Tech & Data role families have been observed in source evaluation. Strong portfolio relevance for the user's target market. | Exact target/result-page handling still needs manual or target-specific validation. | Keep in Batch 1 consideration as optional employer-specific target, but do not implement blindly. |
| ROSSMANN | `employer_origin:rossmann` | `parser_or_target_gap` | Hannover-region relevance and prior origin evidence for Data Engineer-style roles. | Earlier landing-page smoke was too coarse; needs better result-page targeting. | Good first employer-origin validation target before connector work. |
| Finanz Informatik | `employer_origin:finanz_informatik` | `under_evaluation` | Strong IT/data domain fit with Hannover/Muenster/Frankfurt relevance; prior evidence suggests vocabulary gaps around Data Integration, Governance, Analytics and Reporting. | Search terms may need vocabulary broadening before value is visible. | Good ATS/employer-origin candidate after validating target URL and vocabulary. |
| WERTGARANTIE Group | `employer_origin:wertgarantie` | `watchlist` | Hannover/insurance-adjacent relevance and useful aggregator-vs-origin validation case. | Current role fit may be more Product/Analytics/Business than Data Engineering. | Keep as watchlist; not first implementation unless stronger evidence appears. |
| New Personio target not yet identified | `personio:<target>` | `defer` | Personio can produce clean employer-near signals. | Adding arbitrary Personio boards without candidate rationale would be source growth by habit. | Only add after a concrete employer target is selected and validated. |

## Recommended First Expansion Batch

The first implementation batch should remain small and reversible.

Recommended shape:

```text
Greenhouse:
  2 primary board candidates
  1 reserve candidate

Employer-origin / ATS:
  1-2 validation candidates
  optional employer-specific board only after manual review
```

Proposed Batch 1 shortlist:

| Slot | Candidate | Reason | Required pre-check |
|---|---|---|---|
| Greenhouse primary 1 | Contentful | Greenhouse board, tech/data-adjacent, Germany/Berlin relevance. | Activated in S1D after validation; review post-activation source value before adding more Greenhouse boards. |
| Greenhouse primary 2 | commercetools | Greenhouse board, Germany/Berlin relevance, different company/domain from Stripe. | Validate board API slug, matched terms and row shape. |
| Greenhouse reserve | Celonis | Strong data-domain fit. | Validate whether existing Greenhouse connector can access the board reliably. |
| Employer/ATS candidate 1 | Finanz Informatik | Strong IT/data domain fit and regional relevance. | Validate target URL and vocabulary gap before connector work. |
| Employer/ATS candidate 2 | ROSSMANN | Regional relevance and prior known-job evidence. | Validate result-page targeting; avoid weak landing-page parsing. |
| Optional strategic employer | HDI | Insurance-domain relevance and Tech/Data role family signal. | Manual review first; implement only if the target URL and parser boundary are defensible. |

This is a selection shortlist, not authorization to add all candidates at once.

## Expansion Guardrails

Batch 1 should follow these rules:

- add at most 3 new active targets in the first implementation PR
- prefer 2 Greenhouse boards plus 1 employer-origin/ATS validation target
- keep each target separately named and observable
- keep local multi-term filtering active for sources without server-side search
- create source-value snapshots after the first scheduled runs
- treat the first 24h/7d/30d windows after activation as `coverage_changed`
- compare matched rows and Silver rows, not raw volume alone
- pause or defer a target if it produces high load, high duplicates or unclear value

## Metrics to Review After Batch 1

After 2-3 scheduled runs, review:

- fetched jobs before filtering
- matched jobs after local filtering
- matched rate
- inserted rows
- duplicate rate
- Silver rows
- distinct companies
- distinct canonical candidates
- overlap with BA, StepStone and existing ATS targets
- failures or parsing instability
- whether the target adds new value or only repeats known jobs

A target should not remain active only because it produces many raw rows.

## S1C Greenhouse Board Validation Preview

S1C introduces a defensive validation script before new Greenhouse boards are activated:

```bash
python -m scripts.validate_greenhouse_board_candidates \
  --export-dir exports/greenhouse_board_candidate_validation
```

Default validation covers only the two primary Batch 1 Greenhouse candidates:

```text
contentful
commercetools
```

The reserve candidate can be included explicitly:

```bash
python -m scripts.validate_greenhouse_board_candidates \
  --include-reserve \
  --export-dir exports/greenhouse_board_candidate_validation_with_reserve
```

The script is intentionally read-only:

- one Greenhouse boards API request per selected board token
- no database writes
- no `raw_jobs` inserts
- no source profile activation
- no detail-page fetching
- local matching against the current Data Engineering search-term set

The validation output should be interpreted as activation evidence only. It is not long-term source value evidence yet. Long-term value still requires scheduled runs, source-value snapshots, Silver processing and post-activation review.

## S1D Activation Decision

S1D activates only one new Greenhouse board: `greenhouse:contentful`.

Validation evidence from S1C:

| Board | Status | Total jobs | Matching jobs | Decision |
|---|---|---:|---:|---|
| `contentful` | reachable | 89 | 2 | Activate as first controlled Greenhouse expansion target. |
| `commercetools` | reachable | 11 | 0 | Do not activate now; keep as validation evidence only. |
| `celonis` | reachable | 189 | 1 | Keep as reserve; do not activate in the same step as Contentful. |

This keeps the coverage change measurable. It avoids repeating the earlier broad Greenhouse expansion pattern and creates a clean before/after boundary for source-value snapshots.

## Search-Term Duplication Boundary

The repeated data-engineering search terms across `greenhouse:stripe` and `greenhouse:contentful` are intentional at the current profile level.

Each Greenhouse board is modeled as a separate source target. This is necessary because each board has its own requested URL, ingestion history, duplicate profile, source-value snapshots and operational behavior. Applying the same search intent to multiple boards is therefore semantically correct.

S1D also confirmed that this is not currently a fetch-volume issue: `greenhouse:contentful` produced exactly one ingestion run for the board and did not fan out into one request per search term.

However, the current implementation stores repeated terms separately per search profile. This creates maintainability debt. Changing the default data-engineering search intent currently requires updating multiple profile-specific `search_terms` rows across BA, StepStone, Greenhouse and selected Personio targets.

A later cleanup should evaluate a shared search-intent or term-set model, for example:

- `search_intents`
- `search_intent_terms`
- profile-to-intent assignment
- explicit per-source overrides where needed

Until then, profile-specific search terms remain acceptable as long as each source target remains separately observable and is fetched once per profile run.

## Next Step

After the first Contentful ingestion and source-value snapshot, the next S1 step is not another automatic Greenhouse expansion.

Preferred next implementation block:

```text
S2 — Source Strategy Review before additional source expansion
```

The review should reassess whether Greenhouse and Personio targets are the best next value sources for Hannover or remote-in-Germany relevance. It should also evaluate commercial aggregators such as LinkedIn, XING, Indeed and Glassdoor as a separate source family, primarily as employer and role discovery signals before any ingestion commitment.

See `docs/source_analysis/source_strategy_review.md`.

## S2B Aggregator / Discovery Assessment Outcome

S2B reassessed LinkedIn, XING, Indeed and Glassdoor as a separate aggregator source family.

Current decision:

```text
aggregators = discovery_source first
```

They should not become broad automated Bronze ingestion sources now. Their best near-term value is discovery of employers, role-title vocabulary, missing search terms and possible false negatives. Persistent ingestion should still prefer employer-origin or ATS-near evidence when a defensible source target exists.

See `docs/source_analysis/aggregator_discovery_assessment.md`.

### Impact on Next Source Selection

The S1 shortlist remains useful, but S2B changes the preferred next move:

| Next move | Current preference | Reason |
|---|---|---|
| Another Greenhouse board | Lower preference | The connector exists, but Contentful should be observed first and another board may add only limited Germany/remote value. |
| Another Personio/ATS board | Medium preference | Valuable if the employer target is relevant and the acquisition path is clean. |
| Employer-origin validation | High preference | Best match for explainable Hannover/remote-in-Germany source value. |
| Aggregator connector | Not preferred | Too much acquisition/policy risk for direct ingestion at this stage. |
| Aggregator source-research log | High preference | Useful for discovering employers and vocabulary without uncontrolled crawling. |

S2C should therefore select either one employer-origin validation candidate or a manual aggregator discovery-log workflow before more active ingestion targets are added.

## S2C Aggregator Discovery Feasibility Matrix

S2C adds explicit hard gates before any aggregator can move from discovery into automated probing or ingestion.

See `docs/source_analysis/aggregator_discovery_feasibility_matrix.md`.

The most important gate is legal / terms risk. Technical possibility is not enough. If a source cannot be read, stored, reproduced and documented through a defensible access path, it must remain research-only discovery, reference-only or out of scope.

Initial consequence:

| Source group | S2C interpretation | Preferred next action |
|---|---|---|
| LinkedIn, XING, Indeed, Glassdoor | High discovery value, but poor or restricted fit for automated acquisition in this project. | Research-only discovery unless a clearly approved API path exists. |
| StepStone | Existing defensive aggregator source with deliberate one-page boundary. | Keep bounded; do not broaden without separate review. |
| Arbeitnow, Adzuna, Jooble, Remotive | More plausible API/discovery candidates, still subject to terms and storage review. | Consider only after research-only discovery proves value or a tiny API documentation review is justified. |

The preferred next move is a aggregator source-research log that tests whether aggregators actually reveal better employer-origin or ATS candidates for Hannover / remote-in-Germany relevance.
