# Active Roadmap

Status: current planning
Last rebaseline: Product-authority preparation after BACKLOG-REFINE-001

This roadmap is intentionally short. Executable engineering detail, dependencies,
boundaries and acceptance criteria live in `backlog_catalog.json`.

Desired product behavior is defined separately under `docs/product/` and has
higher authority than the engineering catalog.

## Product steering principle

```text
Exact on WHAT.
Adaptive on HOW.
```

Jens owns product semantics. DON may adapt technical design, slicing and sequencing
inside approved requirements. Unresolved product behavior remains blocked or a
`product_change_proposal`; it is never closed by inference.

## Critical path

| Order | Block | Status | Exit gate |
|---:|---|---|---|
| 0 | PRD-001 Product Intent Rebaseline | current | First-slice product decisions, scenarios and traceability are operator-approved. |
| 1 | DOC-010 Planning Truth and Executable Backlog Control | current parallel | One sequence and CI-valid engineering catalog. |
| 2 | SI-020 Generic Evidence Closure | next parallel | Fresh repo/DB evidence returns pass or finite blockers without defining product defaults. |
| 3 | SI-030 Controlled Candidate Creation | blocked | Generic evidence plus approved candidate/product semantics, exact scope, audit and rollback proof. |
| 4 | CC-010 Usable V1 Job Review | blocked | Approved Top-5/ranking/review contract plus reproducible queue and safe actions. |
| 5 | OPS-030 / FREEZE-002 maturity | planned | Measurable targets and V1 entry gate. |
| 6 | OPS-030 / REFACTOR-001 | parked | Inventory and staged boundary plan. |
| 7 | Cloud/outbox/Kafka/Spark | parked | Core maturity and explicit product-value evidence. |

## Immediate product-alignment work

1. Confirm the product truths already recorded in `docs/product/PRD.md`.
2. Resolve only the open decisions needed for the first useful vertical slice.
3. Approve representative acceptance scenarios.
4. Map the active candidate/V1 backlog to approved product intent.
5. Select a small vertical slice that exposes filtering, ranking, evidence, uncertainty and review behavior to Jens.
6. Obtain operator acceptance before scaling the product path.

## Engineering work allowed in parallel

1. Refresh the GENERIC/EXPAND evidence chain.
2. Decide provider coverage only if the refresh still requires it.
3. Close generic proof or expose exact blockers.
4. Continue safety, defect, documentation and runtime stabilization.
5. Do not introduce candidate, Top-5, ranking, queue or action semantics before the relevant PRD decisions are approved.

## Parallel low-risk lanes

Planning-status and governance reconciliation, E402 cleanup, CSV marker cleanup,
CI/main observability, read-only scheduler audit, target-profile evidence review
and defect-taxonomy design may proceed without changing the product critical path.

## Canonical target profile

The repository records Machine Learning Engineer as the foundation, with a Data
Engineering/data-centric ML focus and a future direction toward AI Reliability.
GenAI is treated as a cross-cutting engineering competency rather than a standalone
role profile.

This recorded hierarchy requires operator confirmation in the product decision
register before it becomes the approved basis for product filtering and ranking.

## Explicitly not current

Broad candidate/Wave scaling, automatic source activation, scheduler changes,
autonomous provider runs, premature LLM/application generation, maturity scoring
without exit criteria, monolithic refactoring, cloud, Kafka and Spark.

Product-shaping work without approved PRD traceability is also not current.

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
Current truth, product truth, planning truth and historical evidence stay visibly separated.

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

## Product boundary

All product-shaping changes preserve the operator-approved product contract.
DON may propose product changes, but it may not activate them without explicit
operator approval and corresponding acceptance scenarios.
