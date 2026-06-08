# StepStone Company Discovery Cycle

## Purpose

EO-002A3 introduces a controlled company-discovery cycle for StepStone. The goal is not to permanently blacklist known companies and not to mutate search terms with negative keywords. The goal is to temporarily cool down already-learned company blocks so the same search space can reveal other employers.

## Design clarification

Companies are the interesting discovery unit. Search terms provide the search raster.

A search term such as `Data Engineer` should remain clean. The query may temporarily append company exclusions such as `NOT "HDI"`, but this is a visibility control for companies, not search-term learning.

Known companies must not be suppressed forever. They may later produce new titles, technologies, role names, and search terms. Therefore company suppression is a cooldown, not a blacklist.

## Logical pool vs. request budget

The logical company-cooldown pool is not capped. It may grow over time as the system learns that more companies have already produced enough evidence for a given search space.

The single StepStone request is still bounded. A request may only include a budgeted NOT wave, because StepStone is a search engine, not a clean exclusion API. Very long or legally precise company names can collapse or distort result pages.

This creates two separate concepts:

- `company_discovery_cooldowns`: DB-backed logical pool of temporarily cooled-down companies.
- NOT request wave: a bounded, prioritized window from that pool for one StepStone request.

Later waves can rotate through the same logical pool using an `exclusion_wave_index`. This avoids turning a technical request limit into a permanent discovery limit.

## Company NOT aliases

Validated probes showed that short aliases are more stable than full legal names.

Use examples:

- `HDI`
- `Finanz Informatik`
- `enercity`
- `Ratiodata`
- `Deutsche Bahn`
- `adesso`

Avoid examples:

- `Finanz Informatik GmbH & Co. KG`
- `Deutsche Bahn AG`
- `adesso SE`

Aliases only affect the StepStone NOT token. They do not change canonical company identity.

## Cycle model

1. Pick the next due search term from the adaptive search raster.
2. Load active temporary company cooldowns for that term.
3. Select one bounded NOT request wave from the logical cooldown pool.
4. Build a planned StepStone query, for example `Data Engineer NOT "HDI" NOT "Ratiodata"`.
5. Fetch at most one StepStone result page.
6. Learn companies, titles, and relevance signals.
7. Propose temporary cooldowns for dominant company blocks.
8. Adapt the next interval for the search term.

High-yield and high-quality search spaces get shorter intervals. Lower-yield or noisy spaces get longer intervals. Every search space keeps a maximum interval so it is eventually triggered and does not starve.

A zero-result response is not automatically an error. It is a valid cycle signal and may mean either that the search space is exhausted for the current NOT wave or that the query was over-constrained. It must be visible in review output.

## Boundaries

This feature remains a market-sensor and review layer:

- no detail pages
- no pagination
- no automatic candidate creation
- no connector activation
- no Bronze/Silver writes from the planner
- no scheduler mutation without explicit later approval
- review-state first; cooldown application remains explicit

## Current policy

The NOT syntax is only approved as a controlled probe for whitelisted terms. Initial stable terms are `Data Engineer` and `Analytics Engineer`. Other terms require separate validation because the stability probe showed known-hit leakage, zero-result behavior, or search-intent drift for several terms.

The current implementation should be evaluated as a redundancy breaker and employer-block learning mechanism, not as a guarantee of complete StepStone market recall.


## Request-wave validation note

The logical company-cooldown pool is separate from the bounded NOT terms sent in one StepStone request.

For validation and diagnostics the agent supports two seed modes:

- `--seed-known-candidates`: temporary cooldown pool from known employer-origin candidates with matching StepStone market evidence.
- `--seed-market-evidence-companies`: larger temporary cooldown pool from observed market-evidence companies for the selected search term. This is intended for read-only wave validation and does not create candidates or apply cooldowns.

If a selected wave is beyond the available logical pool, the agent must report `skip_empty_exclusion_wave` instead of silently falling back to another baseline fetch. This prevents duplicate baseline runs from being mistaken for deeper discovery waves.
