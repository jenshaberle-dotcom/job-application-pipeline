# StepStone Compact Directed-Order Experiment

## Status

Completed on 2026-08-03. The diagnostic campaign is closed at the current
evidence boundary. Baseline-only StepStone production remains active;
multi-company NOT production remains blocked.

## Experiment contract

- Seed A: `Technische Informationsbibliothek (TIB)`
- Seed B: `HDI`
- Analog C: `CompuGroup Medical SE & Co. KGaA`
- Tested hypothesis: `syntax_encoding_shape`
- Baseline review: `4`
- Baseline observed at: `2026-08-03T07:01:28.906225+00:00`
- Live artifact:
  `/home/jens_h/product_v1_runtime_artifacts/stepstone_compact_order_failure_repro_20260803T091241Z/result.json`

CompuGroup was selected because it led the current production-baseline candidate
pool for syntax/encoding similarity and also led the broad length/token-shape
ranking. It did not share TIB's full critical signature; that limitation was
preserved before execution and remains relevant to interpretation.

## Executed request matrix

The one-shot live experiment used exactly eight page-one requests:

1. A0 unfiltered baseline;
2. A alone;
3. C alone;
4. A then B;
5. B then A;
6. C then B;
7. B then C;
8. A1 unfiltered baseline control.

The individual B request was omitted. The reverse-pair observations retained the
ability to determine whether B participated in an interpretable expression in
the same observation window.

## Observed result

The operator-reported runner output was:

- requests: `8/8`;
- seed result: `directed_forward_failure_reproduced`;
- analog result: `both_orders_usable`;
- conclusion: `seed_reproduced_but_syntax_encoding_analog_did_not`;
- rule or workaround adoption allowed: `false`.

Therefore the known directed seed behavior reproduced:

- `TIB -> HDI` remained the failing direction;
- `HDI -> TIB` remained usable.

The selected CompuGroup analog did not reproduce the same directionality:

- `CompuGroup -> HDI` was usable;
- `HDI -> CompuGroup` was usable.

## Supported conclusion

The experiment rejects only the tested broad analog hypothesis:

> The syntax/encoding characteristics represented by `CompuGroup Medical SE &
> Co. KGaA` are not sufficient to reproduce the TIB/HDI directed failure.

It does **not** prove that encoding, punctuation or query syntax are irrelevant
in general. The current evidence cannot distinguish among:

- a TIB-specific feature not present in CompuGroup, including parentheses or a
  parenthetical acronym;
- an exact TIB/HDI pair interaction;
- a different tokenization, parser or transport mechanism;
- another unobserved condition in StepStone's query evaluation.

## Runtime decision

No production rule is promoted from this experiment.

- `transport_status` remains conceptually unvalidated for multi-company NOT;
- no canonical company ordering is approved;
- no filter compiler workaround is approved;
- maximum filter capacity is not evaluated because semantic correctness remains
  unresolved;
- filtered multi-company production remains fail-closed;
- unfiltered baseline production may continue under its existing controls.

## Stop and reopen rule

No further StepStone analog calls are authorized by this campaign. Reopen only
when at least one of the following exists:

1. a materially stronger live analog that shares TIB's missing critical
   signature, especially parentheses plus a parenthetical acronym;
2. offline or synthetic evidence isolating a minimal parser/serialization
   mechanism;
3. a new transport representation with a locally verifiable round-trip contract
   and a bounded causal test;
4. a StepStone interface change that materially alters the query semantics.

Until then, the finding is retained as a reproducible unresolved directed parser
interaction, not as an ordering policy and not as a production workaround.
