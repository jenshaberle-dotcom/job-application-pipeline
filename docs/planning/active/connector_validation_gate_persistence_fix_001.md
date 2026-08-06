# Connector Validation Gate Persistence Fix — 001

## Problem

The connector validation agent evaluates connector modules, tests and the bounded
preview correctly, but its gate persistence call did not bind the official numeric
gate order and gate name separately. The SQL statement expects eight values while
the parameter tuple supplied seven, placing `connector_validation_gate` in the
`gate_order` position.

This prevents the validated-connector A1 sequence from persisting its required
`connector_validation_gate = passed / ready_for_final_approval` evidence.

## Correction

The validation repository now:

- resolves the official numeric order through the canonical gate registry;
- persists `gate_order = 11` and `gate_name = connector_validation_gate` separately;
- preserves the existing upsert, evidence and reviewer behavior;
- adds a regression test for the exact SQL parameter contract.

## Boundary

This patch does not validate, approve, register or activate any connector. It makes
no database, provider, scheduler, ranking or application mutation during CI. The
private Accompio and Computacenter validation and registration flow remains a
separate DB-backed execution after merge.
