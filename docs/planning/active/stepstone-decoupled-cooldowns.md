# StepStone Decoupled Cooldown Controls

## Status

Implementation and persistence foundation only. No production StepStone planner
is switched by this change. Activation remains blocked until query transport,
maximum filter capacity and policy thresholds are validated and explicitly
approved.

## Why the original cooldown was insufficient

The historical company cooldown combined several unrelated concerns:

- rotating already-seen companies out of the next filter request;
- deciding when an unfiltered StepStone page should be observed again;
- preventing repeated employer-origin connector refreshes;
- preserving company-specific job-title vocabulary.

That model creates an n-1 oscillation when filtered pages are treated as the
only source of the next filter set. A company disappears because it is filtered,
then becomes ineligible for the following filter set, then returns.

## Decoupled control planes

### Baseline cadence

An unfiltered page-one run is the market census. It measures company dominance,
updates StepStone title vocabulary and emits deduplicated employer-origin
refresh or origin-discovery signals.

The next baseline becomes due when one of these conditions is met:

- the baseline refresh interval elapsed;
- the maximum number of filtered runs since the last baseline was reached;
- company vocabulary requires refresh;
- filtered-run novelty degraded;
- query-transport health requires recalibration;
- no active suppression set exists.

Only one StepStone request is planned per run.

### Stable suppression set

The filter set is built exclusively from the latest valid unfiltered baseline.
It remains stable across filtered runs until a later baseline replaces it.
Filtered-run companies provide discovery evidence and vocabulary, but they do
not silently rewrite the current dominance baseline.

The number of selected companies is bounded by the separately validated filter-
capacity policy. A static company list is forbidden; a stable list derived from
current baseline evidence is allowed.

### Origin-refresh cooldown

A dominant company with an existing employer-origin connector may emit one
refresh trigger. Repeated StepStone evidence is deduplicated while a refresh is
pending or while the origin-refresh cooldown is active.

This cooldown controls connector work only. It never removes the company from
or adds the company to the StepStone suppression set.

A dominant company without an origin connector emits one origin-discovery
signal instead.

### Company-title vocabulary

StepStone result cards remain useful even after the product focus moved from
jobs to companies. The system therefore stores a compact, aggregated vocabulary
per company, search term and normalized title:

- raw and normalized title;
- first and last observation time;
- observation count;
- deduplicated job keys;
- source mode: baseline or filtered.

Vocabulary staleness may bring the next baseline forward. It does not create an
additional StepStone request inside the current run.

## Intended cycle

```text
BASELINE RUN
  -> observe page-one company distribution
  -> build the stable suppression set
  -> update company-title vocabulary
  -> trigger/deduplicate origin refreshes

FILTERED RUN 1
  -> reuse the stable suppression set
  -> discover non-dominant companies and titles

FILTERED RUN 2..N
  -> reuse the same suppression set
  -> measure novelty, leakage and page fill

NEXT BASELINE
  -> replace the suppression set from fresh market evidence
```

## Long-term metrics

The model supports later analysis of:

- baseline company concentration;
- suppression-set stability and churn;
- novelty yield by filter count;
- marginal value of each additional filter;
- origin-refresh trigger and deduplication rates;
- connectorless dominant companies;
- vocabulary freshness by company and source mode;
- filtered runs required before novelty degradation;
- relationship between baseline cadence and employer discovery.

## Boundaries

- page one only;
- no pagination;
- no detail-page access;
- no provider call;
- no candidate creation;
- no source activation;
- no scheduler mutation;
- no automatic transport, capacity or threshold promotion;
- no second StepStone request inside one run.
