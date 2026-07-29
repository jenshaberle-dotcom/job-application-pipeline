# Active Roadmap

Status: current planning
Last rebaseline: BACKLOG-REFINE-001 on 2026-07-29

This roadmap is intentionally short. Executable detail, dependencies, boundaries
and acceptance criteria live in `backlog_catalog.json`.

## Critical path

| Order | Block | Status | Exit gate |
|---:|---|---|---|
| 1 | DOC-010 Planning Truth and Executable Backlog Control | current | One sequence and CI-valid catalog. |
| 2 | SI-020 Generic Evidence Closure | next | Fresh repo/DB evidence returns pass or finite blockers. |
| 3 | SI-030 Controlled Candidate Creation | blocked | Exact scope, approval, audit and rollback proof. |
| 4 | CC-010 Usable V1 Job Review | blocked | Reproducible Top-5 queue and safe actions. |
| 5 | OPS-030 / FREEZE-002 maturity | planned | Measurable targets and V1 entry gate. |
| 6 | OPS-030 / REFACTOR-001 | parked | Inventory and staged boundary plan. |
| 7 | Cloud/outbox/Kafka/Spark | parked | Core maturity and explicit value evidence. |

## Immediate implementation candidates

1. Refresh the GENERIC/EXPAND evidence chain.
2. Decide provider coverage only if the refresh still requires it.
3. Close generic proof or expose exact blockers.
4. Design a tiny candidate apply gate only after proof.
5. Prove apply outcome and rollback.
6. Then implement the V1 job-review journey.

## Parallel low-risk lanes

Planning-status and governance reconciliation, E402 cleanup, CSV marker cleanup,
CI/main observability, read-only scheduler audit, profile decision preparation and
defect-taxonomy design may proceed without changing the critical path.

## Explicitly not current

Broad candidate/Wave scaling, automatic source activation, scheduler changes,
autonomous provider runs, premature LLM/application generation, maturity scoring
without exit criteria, monolithic refactoring, cloud, Kafka and Spark.

## Retained architecture and governance anchors

These stable anchors preserve constraints and test contracts; they do not restore
the superseded historical steering sequence.

<!-- ARCH-001-SAFETY-SECURITY-STATE:START -->
### ARCH-001-SAFETY-SECURITY-STATE
Safety, security, data integrity, explicit transitions and dry-run/apply separation
remain mandatory.
<!-- ARCH-001-SAFETY-SECURITY-STATE:END -->

### DOC-001 Governance Foundation Gate
The governance foundation remains an active constraint.

### DOC-002 Documentation Drift Baseline
Current truth, planning truth and historical evidence stay visibly separate.

### EO-002B Candidate Reprocessing & URL Finder Validation
EO-002B remains bounded validation evidence, not the current steering block.

<!-- EO-002D-ROADMAP -->
### EO-002D-ROADMAP
The origin-source repair boundary remains a regression anchor; generic benchmark
work is represented by `SI-045`.

<!-- PLAN-001-ROADMAP-START -->
### PLAN-001 Future Readiness and Assumption Governance
Preserved catalog work includes:
- MARKET-003 Manual Market Observation Foundation
- ASSUMPTION-001 Simplification Validation Register
- WHALE-001 White-Whale Backlog Triage

Details remain in `future_readiness_and_assumption_governance.md`.
<!-- PLAN-001-ROADMAP-END -->

## Architecture boundary

All changes preserve safety, security, data integrity, explicit transitions,
dry-run/apply separation and the rule that reports/exports are not pipeline inputs.
Opportunistic breadth goes into the catalog rather than changing the critical path.
