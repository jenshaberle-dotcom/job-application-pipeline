# StepStone Filter Semantics Root-Cause Campaign

## Status

Closed at the current evidence boundary on 2026-08-03. Baseline-only production
remains the only active StepStone runtime mode. Multi-company NOT production
remains blocked.

## Validated seed failure

The directed seed interaction reproduced in the compact live experiment:

- `Technische Informationsbibliothek (TIB)` alone was usable;
- `Technische Informationsbibliothek (TIB) -> HDI` failed;
- `HDI -> Technische Informationsbibliothek (TIB)` was usable;
- runner classification: `directed_forward_failure_reproduced`.

The failure is therefore reproducible and cannot be dismissed as a transient
single observation. It is still not assigned to one alias in isolation.

## Structural-analog method

The campaign compared parser-relevant alias characteristics rather than semantic
company similarity. It separated three hypotheses:

1. `length_token_shape`;
2. `acronym_name_shape`;
3. `syntax_encoding_shape`.

The initial aggregate ranking selected `adesso business consulting`, revealing
that a broad combined score over-weighted length and word count. The selector was
therefore hardened to expose hypothesis-specific rankings and prohibit automatic
live-candidate selection.

No current candidate shared TIB's full critical signature of parentheses,
parenthetical acronym and acronym-token characteristics.

## Executed compact experiment

The final one-shot experiment locked:

- seed A: `Technische Informationsbibliothek (TIB)`;
- seed B: `HDI`;
- analog C: `CompuGroup Medical SE & Co. KGaA`;
- hypothesis: `syntax_encoding_shape`;
- baseline review: `4`;
- request budget: exactly eight page-one requests.

Observed classifications:

- seed pair: `directed_forward_failure_reproduced`;
- analog pair: `both_orders_usable`;
- conclusion: `seed_reproduced_but_syntax_encoding_analog_did_not`.

## What the evidence supports

The broad syntax/encoding characteristics represented by CompuGroup are not
sufficient to reproduce the TIB/HDI failure. The experiment does not establish
that punctuation, encoding or parser syntax are irrelevant in general.

Still-open causal possibilities include:

- TIB-specific features absent from CompuGroup, especially parentheses and a
  parenthetical acronym;
- an exact TIB/HDI pair interaction;
- another tokenization, parser or transport rule;
- an unobserved StepStone evaluation condition.

## Runtime decision

No production policy follows from this campaign:

- no preferred company order;
- no validated multi-NOT transport;
- no compiler workaround;
- no approved maximum filter count;
- no capacity experiment;
- no filtered multi-company production.

The safe runtime behavior is unchanged: baseline-only production may continue;
multi-company NOT remains fail-closed.

## Reopen conditions

Do not start another StepStone analog sequence from this campaign. Reopen only
with materially new evidence, such as:

1. a candidate matching TIB's missing critical signature;
2. an offline or synthetic minimal parser reproduction;
3. a transport with a verifiable local round-trip contract and bounded causal
   live test;
4. a material change in StepStone's query interface.

The current retained finding is:

> Reproducible unresolved directed parser interaction for TIB/HDI; broad
> CompuGroup-like syntax/encoding similarity is not sufficient; no safe generic
> production rule is available.
