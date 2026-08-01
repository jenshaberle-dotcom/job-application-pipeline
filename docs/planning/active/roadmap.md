# Active Roadmap

Status: current planning
Last rebaseline: Product-authority preparation after BACKLOG-REFINE-001

The engineering catalog supplies implementation detail. Desired product behavior
is defined under `docs/reference/product-contract/` and has higher authority.

## Steering principle
```text
Exact on WHAT.
Adaptive on HOW.
```
Jens owns product semantics. DON may adapt design, slicing and sequencing inside
approved requirements. Unresolved product behavior remains open.

## Critical path
| Order | Block | Status | Exit gate |
|---:|---|---|---|
| 0 | PRD-001 Product Intent Rebaseline | current | First-slice decisions, scenarios and traceability approved. |
| 1 | DOC-010 Planning Truth | current parallel | One sequence and CI-valid engineering catalog. |
| 2 | SI-020 Generic Evidence Closure | next parallel | Fresh evidence returns pass or finite blockers. |
| 3 | SI-030 Controlled Candidate Creation | blocked | Generic proof plus approved candidate semantics and rollback. |
| 4 | CC-010 Usable V1 Job Review | blocked | Approved Top-5/ranking/review contract and safe queue. |
| 5 | OPS-030 maturity/refactor | planned | Measurable V1 gate and staged boundary plan. |
| 6 | Cloud/outbox/Kafka/Spark | parked | Explicit product-value evidence. |

## Immediate product-alignment work
1. Confirm recorded product truths.
2. Resolve only decisions needed for the first useful vertical slice.
3. Approve representative acceptance scenarios.
4. Map active candidate/V1 items to approved intent.
5. Build a small visible slice covering filtering, ranking, evidence, uncertainty and review.
6. Obtain operator acceptance before scaling.

## Engineering work allowed in parallel
- read-only GENERIC/EXPAND evidence;
- conditional provider-coverage decision without automatic call;
- safety, defects, documentation and runtime stabilization;
- CI, scheduler audit and target-profile evidence review.

These lanes may not introduce candidate, Top-5, ranking, queue or action semantics
before the relevant product decisions are approved.

## Recorded target profile
The repository records Machine Learning Engineer as foundation, Data Engineering
and data-centric ML as focus, AI Reliability as future direction and GenAI as a
cross-cutting competency. Operator confirmation is required before this becomes
the approved filtering/ranking basis.

## Explicitly not current
Broad scaling, automatic source activation, autonomous provider runs, premature
LLM/application generation, monolithic refactoring, cloud, Kafka and Spark.
Product-shaping work without approved PRD traceability is also not current.

## Retained anchors
<!-- ARCH-001-SAFETY-SECURITY-STATE:START -->
### ARCH-001-SAFETY-SECURITY-STATE
Safety, security, data integrity, explicit transitions and dry-run/apply separation
remain mandatory.
<!-- ARCH-001-SAFETY-SECURITY-STATE:END -->

### DOC-001 Governance Foundation Gate
The governance foundation remains active.

### DOC-002 Documentation Drift Baseline
Current truth, product contract, planning truth and history remain separate.

### EO-002B Candidate Reprocessing & URL Finder Validation
EO-002B remains bounded evidence, not current steering.

<!-- EO-002D-ROADMAP -->
### EO-002D-ROADMAP
Origin-source repair remains a regression anchor; generic benchmark work is `SI-045`.

<!-- PLAN-001-ROADMAP-START -->
### PLAN-001 Future Readiness and Assumption Governance
Preserved catalog work includes MARKET-003, ASSUMPTION-001 and WHALE-001.
<!-- PLAN-001-ROADMAP-END -->

## Boundaries
All changes preserve safety, data integrity, explicit transitions, dry-run/apply
separation and the rule that exports are not pipeline inputs. Product changes
require operator approval and acceptance scenarios.
