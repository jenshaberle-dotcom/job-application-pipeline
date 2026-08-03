# StepStone Compact Experiment One-Time Early Override

## Decision

The operator explicitly approved one early execution of the already locked
compact eight-request experiment on 2026-08-03. The normal compact runner and
its 24-hour baseline-relative cooldown remain unchanged.

The exception is implemented as a separate wrapper and is restricted to:

- the persisted baseline observation `2026-08-03T07:01:28.906225+00:00`;
- the existing compact experiment with TIB, HDI and CompuGroup;
- the existing eight-request budget;
- the existing exact operator approval token;
- an additional exact one-time override token;
- execution before the normal cooldown expires;
- one atomic local consumption marker.

## Consumption marker

Before the compact runner can issue its first request, the wrapper atomically
creates:

`~/.local/state/job-application-pipeline/stepstone_compact_review4_early_override.used.json`

A second invocation is blocked when this marker exists. The marker is consumed
before network activity, so a crashed or interrupted invocation is not silently
retried through the exception path.

## Boundaries

The override changes only the timing gate for this one experiment. It does not
change:

- the eight-request maximum;
- page-one-only behavior;
- database read-only behavior;
- the diagnostic-only decision boundary;
- the prohibition on production rule, transport or capacity adoption;
- source, connector, scheduler, provider and application boundaries.

After the ordinary cooldown expires, the one-time wrapper refuses execution and
the normal compact runner must be used instead.
