# F4A-R8 — Operator Acceptance

Status: COMPLETE / OPERATOR ACCEPTED

Accepted Product source: `main@ec2e411ad5240f38e3cc38ee7f76dbac369a8388`
Accepted immutable desktop release: `1.0.32`
Installed acceptance date: 2026-09-15

## Purpose

R8 requalified the current live cohort through the existing truth path before installed operator acceptance:

`Employer Origin -> Bronze evidence -> Silver requirement sidecar -> Product V1 presentation -> Control Center`

R8 added no new requirement semantics. It orchestrated already-proven JAP scripts on the current main-derived tree and closed the remaining F4A acceptance boundary.

## Final sequence and result

1. Read-only exact-Origin/Silver refresh plan.
2. Read-only persisted Silver -> Product -> Control Center audit using the actual Product V1 presentation runtime.
3. Full CI and repository re-entry on the exact qualified R8 head.
4. One single-purpose guarded trigger authorized `refresh-current-cohort-silver-sidecar-only`.
5. The corrected v2 wrapper reused the established R3 backfill approval contract without changing backfill/Product semantics.
6. Before Apply, `41` current-cohort Silver sidecars required refresh.
7. After Apply, the plan converged to `would_change_count = 0`.
8. Persisted Silver -> Product -> Control Center audit passed with zero projection loss, zero legacy ambiguity, zero violations and the existing coverage gate.
9. R8 was merged; post-merge `main` qualification passed.
10. Immutable desktop `1.0.32` was released from the accepted Product SHA and automatically deployed locally.
11. Release-triggered local deploy run `34970391624`, attempt `2`, completed successfully after one transient fail-closed WSL/Git handoff on attempt `1`.
12. Installed operator review accepted the F4A slice.

## Final live-cohort truth

At R8 closure:

- `70` current proposals were accounted for;
- post-refresh convergence was clean;
- all reachable jobs projected without extractor gap;
- coverage gate passed;
- legacy ambiguity = `0`;
- Silver -> Product/Control-Center projection loss = `0`;
- acceptance violations = `0`.

Live Origin availability may legitimately drift after capture; explicit `origin_unavailable` remains the fail-closed representation rather than silently retaining stale truth.

## Installed operator disposition

The operator judged the installed surface materially more coherent and directionally correct, both semantically and visually, while explicitly accepting that it is not perfect.

Non-blocking residuals are tracked separately:

- `#883` — About/version discoverability;
- `#884` — Hannover Re Profile Fit conflict, carried into F4B calibration.

Neither residual reopens F4A unless new evidence proves an acceptance-critical false-truth defect.

## Boundaries

- No learned/Shadow observer was promoted to Product authority by R8.
- No Candidate Fact, ranking, Top-5 or application authority was introduced by R8.
- The only mutation was the guarded current-cohort Silver requirement sidecar refresh through the existing backfill contract.
- Product and Control Center remained consumers of persisted truth.
- Further skill/ML refinement is outside the critical path unless future evidence proves it necessary.

## Closure

F4A is accepted and complete. The frozen campaign proceeds directly to F4B.