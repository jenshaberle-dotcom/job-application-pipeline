# F4A-R8 — Operator Acceptance

Status: ACTIVE / gated acceptance preparation

R8 begins from canonical `main@07512822bd170a6f46fd0d5cceb2312d8c913afc` after R7 skill-evidence hardening was merged and post-merge CI plus re-entry passed.

## Purpose

Requalify the current live cohort through the existing truth path before the next installed operator acceptance:

`Employer Origin -> Bronze evidence -> Silver requirement sidecar -> Product V1 presentation -> Control Center`

R8 adds no new requirement semantics. It only orchestrates already-proven JAP scripts on the current main-derived tree.

## Sequence

1. Read-only exact-Origin/Silver refresh plan.
2. Read-only persisted Silver -> Product -> Control Center audit using the actual Product V1 presentation runtime.
3. Full CI and repository re-entry on the exact R8 head.
4. Only if all gates pass and the Silver plan reports changes: one single-purpose trigger commit authorizes `refresh-current-cohort-silver-sidecar-only`.
5. Guarded apply rebuilds the exact-Origin plan before mutation and uses the existing R3 Silver backfill approval contract.
6. After the Silver sidecar refresh, the plan must converge to `would_change_count = 0`.
7. The persisted Silver -> Product -> Control Center audit must pass with zero projection loss, zero legacy ambiguity, zero violations, and the existing coverage gate.
8. Only then prepare the installed desktop/operator acceptance.

The older Product-assessment refresh is deliberately not part of R8. Product V1 now prefers the persisted Silver requirement sidecar and the Bronze2E audit verifies the exact read-only Product/Control-Center projection. R8 therefore does not duplicate requirement truth into a second Product mutation path.

The first R8 guarded apply run `34966762652` stopped before database mutation because its wrapper supplied a new R8 approval token while the existing backfill implementation correctly accepts only `F4A-R3-SILVER-REQUIREMENT-BACKFILL-001`. The corrected minimal v2 wrapper reuses that established approval contract; no backfill/product semantics are changed.

## Boundaries

- No learned/Shadow observer is part of R8.
- No Candidate Fact, fit, ranking, Top-5 or application authority is introduced.
- Preflight is read-only.
- Apply authority is bound to the exact qualified parent plus preflight, CI and re-entry run IDs.
- The corrected apply trigger commit may change only `.github/triggers/f4a-r8-operator-apply-v2.trigger`.
- The only permitted mutation is the current-cohort Silver requirement sidecar refresh through the existing R3 backfill implementation.
- Product and Control Center verification remain read-only consumers of persisted Silver evidence.
- R8 ends after convergence and installed operator acceptance; further skill/ML refinement is explicitly outside the critical path unless acceptance reveals a new correctness blocker.
