# Parallel Product Roadmap after EXPAND-003

Status: planning anchor

This roadmap keeps the next product phase parallelizable while preserving safety boundaries.
## GENERIC-001 Pipeline Generics Proof Gate

Before any production-like candidate throughput, broad candidate apply, or TOP5 product claim, the pipeline must prove generic behavior across a representative candidate set.

This gate is inserted between the controlled evidence/review loop and broad candidate creation or Wave Search scaling:

1. EXPAND-003 Candidate Review Delta Report
2. GENERIC-001 Pipeline Generics Proof Gate
3. GENERIC-002 Benchmark Gap Closure Plan, when GENERIC-001 reports gaps
4. GENERIC-001 rerun with explicit controls and/or new stop-case evidence
5. EXPAND-004 Controlled Candidate Creation Dry-Run
6. Wave Search / Scheduler Intelligence
7. Matching / TOP5 Product MVP

GENERIC-001 has an implemented read-only artifact runner and remains review-artifact-only. It must not create candidates, write gates, activate connectors, mutate Bronze/Silver/Gold, change scheduler behavior, or perform uncontrolled external requests.

The benchmark should start with 8 to 12 reviewed candidates covering strong origin evidence, weak-only aggregator evidence, ambiguous identity risk, acronym/alias-heavy company identity, provider-backed origin URLs, no-actionable-evidence candidates, at least one known positive control and at least one known blocked/negative control.

See `docs/planning/generic_pipeline_proof_gate.md`.

If GENERIC-001 reports gaps, close them through `docs/planning/generic002_benchmark_gap_closure_plan.md` and the read-only runner:

    python scripts/run_generic002_benchmark_gap_closure_plan.py

Current operational runner:

    python scripts/run_generic001_pipeline_generics_proof_gate.py

The first current-artifact run is expected to expose benchmark gaps rather than immediately pass, especially explicit positive/negative controls and a clean no-actionable-evidence stop case. Those gaps must be closed before candidate apply or wave-search scaling.
