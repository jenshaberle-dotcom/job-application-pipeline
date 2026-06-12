# Parallel Product Roadmap after EXPAND-003

Status: planning anchor

This roadmap keeps the next product phase parallelizable while preserving safety boundaries.
## GENERIC-001 Pipeline Generics Proof Gate

Before any production-like candidate throughput, broad candidate apply, or TOP5 product claim, the pipeline must prove generic behavior across a representative candidate set.

This gate is inserted between the controlled evidence/review loop and broad candidate creation or Wave Search scaling:

1. EXPAND-003 Candidate Review Delta Report
2. GENERIC-001 Pipeline Generics Proof Gate
3. EXPAND-004 Controlled Candidate Creation Dry-Run
4. Wave Search / Scheduler Intelligence
5. Matching / TOP5 Product MVP

GENERIC-001 is review-artifact-only. It must not create candidates, write gates, activate connectors, mutate Bronze/Silver/Gold, change scheduler behavior, or perform uncontrolled external requests.

The benchmark should start with 8 to 12 reviewed candidates covering strong origin evidence, weak-only aggregator evidence, ambiguous identity risk, acronym/alias-heavy company identity, provider-backed origin URLs, no-actionable-evidence candidates, at least one known positive control and at least one known blocked/negative control.

See `docs/planning/generic_pipeline_proof_gate.md`.

