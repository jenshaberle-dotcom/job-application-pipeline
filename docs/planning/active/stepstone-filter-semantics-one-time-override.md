# StepStone Compact Experiment One-Time Early Override

## Status

Consumed successfully on 2026-08-03. This exception is closed and must not be
reused.

## Decision

The operator explicitly approved one early execution of the already locked
compact eight-request experiment on 2026-08-03. The normal compact runner and
its 24-hour baseline-relative cooldown remained unchanged.

The exception was implemented as a separate wrapper and restricted to:

- the persisted baseline observation `2026-08-03T07:01:28.906225+00:00`;
- baseline review `4`;
- the compact experiment with TIB, HDI and CompuGroup;
- the existing eight-request budget;
- the existing exact operator approval token;
- an additional exact one-time override token;
- execution before the normal cooldown expired;
- one atomic local consumption marker.

## Consumption evidence

The wrapper passed its timing gate and the compact experiment completed with:

- `execution_allowed_now: true`;
- requests: `8/8`;
- result: `STEPSTONE_COMPACT_ORDER_FAILURE_REPRO_PROBE_COMPLETED`.

Before network activity the wrapper atomically created its local consumption
marker:

`~/.local/state/job-application-pipeline/stepstone_compact_review4_early_override.used.json`

The exception is therefore consumed. A second invocation through the early
override path is expected to fail closed.

## Preserved boundaries

The override changed only the timing gate for one experiment. It did not change:

- the eight-request maximum;
- page-one-only behavior;
- database read-only behavior;
- the diagnostic-only decision boundary;
- the prohibition on production rule, transport or capacity adoption;
- source, connector, scheduler, provider and application boundaries.

## Closure

No further cooldown exception is implied or authorized by this decision. Any
future StepStone diagnostic experiment requires a new bounded experiment
contract and separate operator approval.
