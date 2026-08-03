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
features for each actual filter alias and selects the strongest current analog
to seed A, excluding seed A and seed B.

The comparison deliberately prioritizes:

- raw, UTF-8 and URL-encoded length;
- word count;
- parentheses and parenthetical acronyms;
- punctuation, ampersands and digits;
- uppercase ratio, all-caps aliases and single-token aliases.

This is not semantic company-name matching and does not claim causality. The
purpose is to provoke a second directed failure with a structurally similar
alias.

## Fixed live matrix

After a baseline-relative 24-hour cooldown and exact operator approval, the
probe performs exactly nine page-one requests:

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
- the selected structural analog reproduced the same directed failure.

It may not adopt a production ordering rule, transport, workaround, filter
capacity, source activation or scheduler behavior.

## Next evidence step

If the analog reproduces the failure, compare the common features and construct
minimal counterexamples. If it does not, replace one feature dimension at a
time or test a B-like analog while keeping A fixed. Maximum filter capacity is
measured only after the failure mechanism is explained or reliably detected by
a fail-closed compiler contract.
