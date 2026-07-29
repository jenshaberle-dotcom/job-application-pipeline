# Active Roadmap

Status: current planning
Last rebaseline: BACKLOG-REFINE-001 on 2026-07-29

This roadmap is intentionally short. The executable detail, dependencies,
boundaries and acceptance criteria live in `backlog_catalog.json`.

## Critical path

| Order | Block | Status | Exit gate |
|---:|---|---|---|
| 1 | DOC-010 Planning Truth and Executable Backlog Control | current | One contradiction-free active sequence and CI-valid catalog. |
| 2 | SI-020 Generic Evidence Closure | next | Fresh repo/DB evidence returns pass or finite blockers. |
| 3 | SI-030 Controlled Candidate Creation | blocked | Exact dry-run/apply scope, operator approval, audit and rollback proof. |
| 4 | CC-010 Usable V1 Job Review | blocked | Reproducible Top-5 review, usable queue and approval-safe actions. |
| 5 | OPS-030 / FREEZE-002 maturity | planned | Measurable maturity targets and completed V1 entry gate. |
| 6 | OPS-030 / REFACTOR-001 | parked | Inventory and staged boundary plan before implementation. |
| 7 | Cloud/outbox/Kafka/Spark | parked | Core maturity and explicit value evidence. |

## Current implementation candidates

The immediate work is not broad product expansion. It is:

1. refresh the GENERIC/EXPAND evidence chain;
2. decide provider coverage only if the refresh still requires it;
3. close the generic proof or expose exact blockers;
4. design a tiny candidate apply gate only after proof;
5. prove apply outcome and rollback;
6. then define and implement the V1 job-review journey.

## Parallel low-risk lanes

These may proceed when they do not interfere with the critical path:

- planning-status and governance-register reconciliation;
- E402 policy/cleanup;
- CSV producer marker cleanup;
- CI/main-run observability;
- read-only scheduler/orchestrator capability audit;
- target-profile decision preparation;
- defect/failure taxonomy design.

## Explicitly not current

- broad candidate creation or Wave scaling;
- automatic connector/source activation;
- scheduler behavior changes;
- autonomous provider runs;
- LLM scoring or application generation before deterministic/profile foundations;
- FREEZE-002 scoring without written exit criteria;
- monolithic refactoring;
- cloud, Kafka or Spark implementation.

## Architecture boundary

New changes must preserve safety, security, data integrity, explicit state
transitions, dry-run/apply separation and the rule that reports/exports are not
pipeline inputs. Opportunistic breadth goes into the catalog rather than silently
changing the critical path.
