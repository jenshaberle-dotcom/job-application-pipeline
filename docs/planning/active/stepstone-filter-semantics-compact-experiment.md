# StepStone Compact Directed-Order Experiment

## Decision

The current root-cause campaign is closed as far as possible without additional
StepStone traffic. The first live follow-up is intentionally limited to one
locked analog and one explicit hypothesis.

- Seed A: `Technische Informationsbibliothek (TIB)`
- Seed B: `HDI`
- Analog C: `CompuGroup Medical SE & Co. KGaA`
- Hypothesis: `syntax_encoding_shape`

CompuGroup is selected because it leads the current production-baseline
candidate pool for syntax/encoding similarity and also leads the broad
length/token-shape ranking. It does not share TIB's full critical signature;
that limitation is preserved as evidence and prevents overclaiming.

## Compact request matrix

The live matrix is reduced from nine to eight page-one requests:

1. A0 unfiltered baseline;
2. A alone;
3. C alone;
4. A then B;
5. B then A;
6. C then B;
7. B then C;
8. A1 unfiltered baseline control.

The individual B request is omitted. A usable reverse pair demonstrates that B
can participate in an interpretable expression in the same observation window,
while preserving both directed comparisons and the temporal baseline control.

## Execution gate

The experiment remains blocked until 24 hours after the persisted baseline
observation and requires the existing exact approval token. Plan mode makes zero
StepStone requests.

## Interpretation

The experiment may establish only:

- whether the known A/B directed failure reproduces now; and
- whether the syntax/encoding analog C reproduces the same directionality.

It cannot activate a production ordering rule, transport, workaround, filter
capacity, source, connector, scheduler, provider, or application action.

## Stop rule

After this eight-request experiment, no second analog experiment is started
automatically. The next step is selected from the evidence:

- analog reproduces: isolate the shared syntax/encoding feature offline;
- seed reproduces but analog does not: record the hypothesis as unsupported and
  avoid further StepStone calls until a stronger candidate or synthetic parser
  test exists;
- seed does not reproduce: treat the behavior as temporally unstable and keep
  multi-company NOT production blocked;
- indeterminate page: stop without retry escalation.
