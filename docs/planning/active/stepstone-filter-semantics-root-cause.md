# StepStone Filter Semantics Root-Cause Campaign

## Status

Active diagnostic campaign. Baseline-only production is proven and remains the
only active StepStone runtime mode. Multi-company NOT production remains
blocked.

## Known seed failure

The current validated seed is a directed pair interaction:

- `Technische Informationsbibliothek (TIB)` alone produced a usable page;
- `HDI` alone produced a usable page;
- `Technische Informationsbibliothek (TIB) -> HDI` produced zero cards;
- `HDI -> Technische Informationsbibliothek (TIB)` produced a full page.

The failure is therefore not assigned to one alias in isolation. It is treated
as a directed interaction until further evidence explains it.

## First slice: structural analog reproduction

`STEPSTONE-ORDER-FAILURE-REPRO-001` uses the latest persisted production
baseline review as the candidate pool. It computes parser-relevant structural
features for each actual filter alias, excluding seed A and seed B.

The initial aggregate ranking over-weighted broad length and word-count
similarity and selected `adesso business consulting`, even though it shares
neither parentheses nor a parenthetical acronym with TIB. That result is useful
evidence that a single aggregate score is not a safe experimental selector.

The revised plan separates three explicit hypotheses:

1. `length_token_shape`: raw/encoded length, word count and broad token shape;
2. `acronym_name_shape`: acronym-bearing, expanded multiword name structure;
3. `syntax_encoding_shape`: punctuation, parentheses, encoded length,
   ampersands and digits.

The plan reports leaders for every hypothesis. It never selects an analog
automatically. The operator must provide both an explicit alias and the
hypothesis being tested before a live request can run.

A critical-signature check separately reports whether a candidate shares TIB's
parentheses, parenthetical acronym and acronym-token characteristics. Absence of
such a candidate is preserved as evidence rather than hidden by a medium global
score.

This is not semantic company-name matching and does not claim causality. The
purpose is to provoke a second directed failure under one clearly stated
structural hypothesis.

## Fixed live matrix

After a baseline-relative 24-hour cooldown, explicit analog/hypothesis selection
and exact operator approval, the probe performs exactly nine page-one requests:

1. unfiltered A0 baseline;
2. seed A alone;
3. seed B alone;
4. selected analog C alone;
5. A then B;
6. B then A;
7. C then B;
8. B then C;
9. unfiltered A1 baseline control.

The probe records the logical query, requested and final URLs, URL lengths,
response classification, parsed cards, excluded-company leakage and local HTML
hashes through the existing bounded StepStone probe helpers.

## Decision boundary

This slice may conclude only whether:

- the known seed failure reproduced in the current observation window; and
- the operator-selected analog reproduced the same directed failure under the
  declared hypothesis.

It may not adopt a production ordering rule, transport, workaround, filter
capacity, source activation or scheduler behavior.

## Next evidence step

If the analog reproduces the failure, compare the common features and construct
minimal counterexamples. If it does not, select the leader from a different
hypothesis or test a B-like analog while keeping A fixed. Maximum filter
capacity is measured only after the failure mechanism is explained or reliably
detected by a fail-closed compiler contract.
