# StepStone Dynamic Company-Filter Control Loop

## Status

Design and persistence foundation only. The current StepStone NOT planner is not
switched to this policy until a permutation-invariant query transport is
validated and explicitly approved.

## Product objective

The daily filter set must never be a static company list. It is derived from the
immediately previous observation (`n-1`) so companies that currently displace
potentially new employers are suppressed in the next run.

```text
Run n-1 page one
→ aggregate company distribution
→ apply reselection cooldown and dominance override
→ select the bounded filter set for Run n
→ measure variation and displacement
```

Historical companies that are absent from run `n-1` cannot enter the next
filter set merely because they existed in an old cooldown pool.

## Three separate states

### Suppression selection

A company selected from run `n-1` is proposed as a NOT filter for run `n`.
This is a one-run decision derived from current evidence.

### Reselection cooldown

After a company has been filtered, a reselection cooldown encourages rotation
and gives other observed companies a chance to become the next suppression
set. It is not a blacklist and does not mean that the company is ignored.

### Dominance override

A currently observed company may override its active reselection cooldown when
its card count or page share crosses the configured, versioned dominance
threshold. Example: if HDI occupies 25 of 25 cards, HDI must be selected again
for the next run even when its reselection cooldown has not expired.

Thresholds are policy inputs and must not be silently inferred from one probe.
They remain versioned and adjustable.

## Deterministic selection order

Eligible companies from run `n-1` are ordered by:

1. descending card count;
2. first page position;
3. canonical company key.

The filter count is bounded by the currently approved capacity policy. A fixed
number such as five is not assumed permanently.

## Maximum filter-length experiment

Filter breadth materially affects variation quality. It must therefore be
measured independently from company selection and independently from query
transport.

The experiment is allowed only when:

- the query transport is already `validated`;
- the candidate companies were selected from the same run `n-1`;
- the cooldown window for live StepStone traffic has elapsed;
- an explicit approval token and bounded request budget are present.

For each cardinality `1..N`, the same prefix is tested in forward and reverse
order. Cardinality one has one unique request. With `N=5`, this means nine
filtered requests plus two baseline controls: eleven total requests.

A cardinality can only be considered supported when the filter set is
permutation-invariant, leak-free and produces a usable page. The longest
supported cardinality is evidence, not an automatic production promotion.

## Long-term metrics

Per company and search space:

- observed run count;
- total observed cards;
- average and maximum page share;
- number of next-run selections;
- number of dominance overrides;
- latest observation and reselection-cooldown timestamps.

Per filter-capacity trial:

- filter count and permutation;
- intended query, requested URL and final URL;
- page type and page fill `0..25`;
- excluded-company leakage;
- new companies and new jobs;
- job overlap with the baseline;
- permutation invariance;
- explicit zero-result versus technical-indeterminate classification.

These metrics support later analysis of recurring quasi-static filters, company
market concentration, novelty yield by filter count and whether the selected
capacity remains stable over time.

## Boundaries

- page one only;
- no pagination;
- no detail pages;
- no candidate creation from this control layer;
- no provider calls;
- no source activation;
- no scheduler mutation;
- no automatic transport, threshold or capacity promotion.
