# GENERIC-002 Benchmark Gap Closure Plan

Status: implemented foundation / read-only closure planner for GENERIC-001 gaps
Scope: Search Intelligence / Candidate Pipeline / Generics Proof / Freeze Path

## Purpose

GENERIC-002 turns the gaps found by GENERIC-001 into an explicit closure plan before any broader candidate apply, Wave Search scaling, scheduler change or TOP5 product claim.

It prevents a weak shortcut where positive examples are treated as proof while missing negative controls and safe-stop behavior remain untested.

## Placement

GENERIC-002 sits directly after GENERIC-001 when the proof gate reports gaps:

1. EXPAND-003 Candidate Review Delta Report
2. GENERIC-001 Pipeline Generics Proof Gate
3. GENERIC-002 Benchmark Gap Closure Plan
4. GENERIC-001 rerun with explicit controls and/or new stop-case evidence
5. EXPAND-004 Controlled Candidate Creation Dry-Run
6. Wave Search / Scheduler Intelligence
7. Matching / TOP5 Product MVP

## Runner

    python scripts/run_generic002_benchmark_gap_closure_plan.py

The runner reads the latest GENERIC-001 proof report by default and writes review artifacts under:

    exports/generic002_benchmark_gap_closure_plan/

It can also consume an explicit GENERIC-001 JSON:

    python scripts/run_generic002_benchmark_gap_closure_plan.py \
      --input exports/generic001_pipeline_generics_proof_gate/generic001_pipeline_generics_proof_gate.json

## Safety boundary

GENERIC-002 is a review-artifact step only.

It must not:

- create candidates
- write gate decisions
- activate connectors
- mutate Bronze, Silver or Gold
- change scheduler behavior
- perform external requests
- infer hidden control truth without explicit operator metadata

## Expected first outcome

The first current-artifact GENERIC-002 run is expected to show that the positive-control gap can likely be closed from an existing strong-detail candidate, while negative-control and no-actionable-evidence coverage still need a clean stop-case artifact.

This is intentional. It keeps the freeze path honest: EXPAND-004 may be designed next, but broad apply or product claims remain blocked until control coverage is explicit.


## Follow-up: GENERIC-003

GENERIC-003 should consume this plan and rerun GENERIC-001 with any explicit control keys that are already safe to close from existing review artifacts. It must keep missing negative-control and no-actionable-evidence gaps blocked instead of inferring them from weak-only market hints.
