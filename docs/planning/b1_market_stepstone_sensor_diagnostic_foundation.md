# B1 Market + StepStone Diagnostic Foundation

B1 bundles three read-only diagnostic surfaces after FREEZE-001C:

- MARKET-001 Market Sensor Diagnostic Metrics
- STEPSTONE-001 StepStone Discovery Cycle Diagnostics
- SENSOR-001F BA Remote/Nationwide Result Decision Scaffold

## Boundary

B1 is a diagnostic foundation, not a product execution block.

It must not:

- run external source requests,
- write database state,
- start ingestion runs,
- mutate scheduler configuration,
- create or promote candidates,
- change gate, connector, Bronze, Silver, or Gold state.

## Why this is safe to bundle

The bundled parts are horizontal and read-only. They prepare measurement and decision surfaces before the separate SENSOR-001E bounded BA sample execution review. B1 does not change production decision logic and does not activate any market sensor.

## MARKET-001

MARKET-001 exposes current market-sensor coverage and missing coverage dimensions. It keeps the question separate from activation: a sensor can have a valid gap without being activated immediately.

Useful questions:

- Is the local Hannover target market represented?
- Is a Germany-wide remote-option review profile represented?
- Which source/profile family needs a bounded validation before activation?

## STEPSTONE-001

STEPSTONE-001 exposes the StepStone company-discovery cycle in a measurable way:

- planned baseline or temporary company-NOT probe,
- selected cooldown wave,
- known-company hits,
- new-company count,
- relevance and drift signals,
- recommended adaptive interval.

The goal is to make repeated-known-company blindness visible before changing the Türsteher or discovery logic.

## SENSOR-001F scaffold

SENSOR-001F is intentionally only a decision scaffold in B1. It defines the metrics that a later SENSOR-001E bounded sample must provide before any activation, repeat-sample, monitor, or rejection decision.

Required metrics include total loaded, inserted/duplicate counts, distinct and new companies, known-company overlap, remote signal quality, profile relevance, irrelevant-title noise, and errors.

## Validation

```bash
python -m pytest -q tests/test_b1_diagnostic_foundation.py
python scripts/run_b1_diagnostic_foundation.py
python scripts/run_validate001_unified_validation.py --profile commit
git diff --check
git status --short
```
