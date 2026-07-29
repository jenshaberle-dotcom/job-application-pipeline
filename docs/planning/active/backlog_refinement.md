# BACKLOG-REFINE-001 Repository-Wide Backlog Refinement

Status: proposed current planning control surface  
Date: 2026-07-29  
Source commit: `e52b0095d1a2246c7be1e20d72f442bab4ca2ec8`

## Scope

This refinement treats the entire repository as an idea and unfinished-work source: current and reference documentation, active/root/future planning, archive reviews, code markers, governance registers, merged PR history, GitHub work state and CI evidence.

The executable truth is `backlog_catalog.json` plus the files under `backlog/`. Every story carries outcome, dependencies, evidence, risk zone, boundaries, acceptance criteria and validation.

## Canonical target profile decision

Operator decision recorded on 2026-07-29:

1. Foundation role family: **Machine Learning Engineer**.
2. Technical focus: **Data Engineering and data-centric ML systems**.
3. Future specialization: **AI Reliability / Data & AI Reliability Engineering**.
4. GenAI: **cross-cutting engineering competency**, not a standalone target profile.

Current application wording may adapt to a vacancy, but it must preserve this hierarchy and must not claim seniority or production capability without evidence. Runtime/search/CV alignment remains open under `DOC-018`.

## Current sequence

| Order | Story | Gate |
|---:|---|---|
| 1 | `DOC-011` | complete planning truth rebaseline |
| 2 | `SI-021` | fresh current repo/DB evidence |
| 3 | `SI-022` | run only when fresh evidence shows provider decision is still required |
| 4 | `SI-023` | generic proof must pass or return finite blockers |
| 5 | `SI-025` | start only after SI-023 passes |
| 6 | `SI-026` | operator-approved exact apply scope |
| 7 | `SI-027` | outcome and rollback proof |
| 8 | `CC-011` | begin V1 review path after candidate proof |

## Contradictions

| ID | Severity | Classification | Resolution |
|---|---|---|---|
| `CTR-001` | P0 | `active_steering_conflict` | `DOC-011` |
| `CTR-002` | P0 | `stale_active_status` | `DOC-015` |
| `CTR-003` | P0 | `superseded_gate_with_conditional_backlog` | `DOC-012` |
| `CTR-004` | P1 | `priority_order_ambiguity` | `SI-021` |
| `CTR-005` | P1 | `self_contradictory_document_authority` | `DOC-014` |
| `CTR-006` | P1 | `planning_lifecycle_drift` | `DOC-012` |
| `CTR-007` | P1 | `implemented_work_marked_planned` | `DOC-017` |
| `CTR-008` | P1 | `implemented_work_marked_planned` | `DOC-012` |
| `CTR-009` | P1 | `unfinished_work_package` | `DOC-016` |
| `CTR-010` | P1 | `runtime_profile_drift_after_operator_decision` | `DOC-018` — decision recorded, alignment open |
| `CTR-011` | P2 | `stale_governance_classification` | `DOC-021` |
| `CTR-012` | P1 | `ci_observability_gap` | `OPS-026` |

## Capability map

| Capability | Status | Priority | Stories | Outcome |
|---|---|---|---:|---|
| `DOC-010` Planning Truth and Executable Backlog Control | `in_progress` | P0 | 9 | One contradiction-aware, machine-readable backlog becomes the sole active planning control surface. |
| `SI-020` Generic Evidence Closure | `ready_after_truth_rebaseline` | P0 | 4 | Generic origin/detail/stop-control evidence is recomputed from current repo and DB truth and yields a defensible go/no-go decision. |
| `SI-030` Controlled Candidate Creation | `blocked` | P1 | 3 | A tiny, exact candidate cohort can be created through dry-run, explicit approval, audited apply and rollback proof. |
| `CC-010` Usable V1 Job Review | `blocked` | P1 | 6 | The operator can review a small ranked set of real jobs, understand fit and safely record review decisions in the Control Center. |
| `SI-040` Discovery, Coverage and Target-Profile Quality | `planned` | P1 | 8 | The pipeline finds relevant Hannover/remote roles with measurable coverage, current profile truth and controlled false-negative analysis. |
| `EO-020` Employer-Origin and Connector Lifecycle Consolidation | `planned` | P2 | 5 | Each discovery, repair, gate, build, validation, registration and activation boundary has one authoritative owner. |
| `OPS-020` Reliability, CI and Runtime Operations | `planned` | P1 | 7 | CI, local validation, provider credentials, scheduler runs, defects and reruns are observable, bounded and reproducible. |
| `DOC-020` Agent Estate and Governance Reconciliation | `planned` | P2 | 6 | Agent names, maturity, permissions and ownership match actual code and runtime evidence. |
| `APP-010` Governed Application Intelligence | `parked_until_v1_inputs` | P2 | 8 | Matching, LLM scoring and application artifacts use approved profile/CV facts and remain proposal-first. |
| `OPS-030` Maturity Refactor and Platform Readiness | `parked` | P3 | 11 | The local batch product reaches explicit maturity, then is refactored in bounded slices before cloud/event expansion. |

## Stories

### DOC-010 — Planning Truth and Executable Backlog Control

| Story | Status | Priority | Risk | Dependencies |
|---|---|---|---|---|
| `DOC-011` Rebaseline Active Steering Sequence | `in_progress` | P0 | R0 | — |
| `DOC-012` Reconcile Planning Status Against Implemented PRs | `ready` | P0 | R0 | `DOC-011` |
| `DOC-013` Backlog Catalog CI Contract | `in_progress` | P0 | R0 | `DOC-011` |
| `DOC-014` Consolidate Search Intelligence Current-State Snapshot | `ready` | P1 | R0 | `DOC-011` |
| `DOC-015` Close or Reclassify CONSISTENCY-001A | `ready` | P0 | R0 | `DOC-011` |
| `DOC-016` Repair FREEZE-002 Exit Criteria | `ready` | P1 | R0 | — |
| `DOC-017` Reconcile Ruff Transition Documentation | `ready` | P1 | R0 | — |
| `DOC-018` Target-Profile Truth Alignment | `in_progress` | P1 | R0 | — |
| `DOC-019` Contradiction Regression Check | `planned` | P2 | R0 | `DOC-012` |

### SI-020 — Generic Evidence Closure

| Story | Status | Priority | Risk | Dependencies |
|---|---|---|---|---|
| `SI-021` Fresh GENERIC/EXPAND Evidence Recompute | `ready` | P0 | R1 | `DOC-011` |
| `SI-022` PROVIDER-001C Coverage Decision Bundle | `conditional_ready` | P0 | R1 | `SI-021` |
| `SI-023` GENERIC Final Recheck | `blocked` | P0 | R1 | `SI-021`, `SI-022` |
| `SI-024` Stop-Control Repair Strategy Coverage | `ready` | P1 | R1 | `SI-021` |

### SI-030 — Controlled Candidate Creation

| Story | Status | Priority | Risk | Dependencies |
|---|---|---|---|---|
| `SI-025` Candidate Apply-Gate Design | `blocked` | P1 | R2 | `SI-023` |
| `SI-026` Controlled Candidate Apply Implementation | `blocked` | P1 | R3 | `SI-025` |
| `SI-027` Candidate Apply Outcome and Rollback Proof | `blocked` | P1 | R2 | `SI-026` |

### CC-010 — Usable V1 Job Review

| Story | Status | Priority | Risk | Dependencies |
|---|---|---|---|---|
| `CC-011` Define V1 Top-5 Job Review Contract | `ready_after_candidate_proof` | P1 | R0 | `SI-027` |
| `CC-012` Job Review Read Model | `blocked` | P1 | R1 | `CC-011`, `DOC-018` |
| `CC-013` Review Queue Usability Slice | `blocked` | P1 | R1 | `CC-012` |
| `CC-014` Approval-Safe Review Actions Backend | `blocked` | P1 | R3 | `CC-013` |
| `CC-015` V1 End-to-End Operator Proof | `blocked` | P1 | R2 | `CC-014` |
| `CC-016` Runtime Agent Health Model | `planned` | P2 | R1 | `OPS-022` |

### SI-040 — Discovery, Coverage and Target-Profile Quality

| Story | Status | Priority | Risk | Dependencies |
|---|---|---|---|---|
| `SI-041` DB-Backed Manual Market Observation Reconciliation | `status_reconciliation` | P1 | R1 | — |
| `SI-042` ASSUMPTION-001 Validation Register | `planned` | P1 | R1 | `SI-041` |
| `SI-043` StepStone/Wave Cycle Operational Validation | `ready` | P1 | R2 | — |
| `SI-044` Candidate Promotion Quality Benchmark | `ready` | P1 | R2 | `SI-042` |
| `SI-045` Generic Origin and Detail Evidence Benchmark | `ready` | P1 | R1 | `SI-044` |
| `SI-046` Sensor Contribution and Blind-Spot Audit | `planned` | P2 | R1 | `SI-043` |
| `SI-047` Search-Term Registry for Current Target Profile | `blocked` | P1 | R2 | `DOC-018` |
| `SI-048` Deterministic Matching Signal Model | `blocked` | P1 | R2 | `SI-047`, `SI-042` |

### EO-020 — Employer-Origin and Connector Lifecycle Consolidation

| Story | Status | Priority | Risk | Dependencies |
|---|---|---|---|---|
| `EO-021` Canonical Connector Lifecycle Responsibility Contract | `ready` | P2 | R0 | — |
| `EO-022` Connector Agent Consolidation Plan | `planned` | P2 | R1 | `EO-021` |
| `EO-023` URL Discovery Repair Persistence Ownership | `planned` | P2 | R1 | `EO-021` |
| `EO-024` Connector Write-Boundary Hardening | `planned` | P2 | R3 | `EO-021`, `DOC-024` |
| `EO-025` Connector and Source Health Read Models | `planned` | P2 | R1 | `EO-021`, `OPS-022` |

### OPS-020 — Reliability, CI and Runtime Operations

| Story | Status | Priority | Risk | Dependencies |
|---|---|---|---|---|
| `OPS-021` Env-Aware Controlled Provider Runs | `ready` | P1 | R2 | — |
| `OPS-022` Scheduler and Orchestrator Capability Audit | `ready` | P1 | R2 | — |
| `OPS-023` Defect and Failure Taxonomy Baseline | `planned` | P1 | R0 | `SI-024`, `OPS-022` |
| `OPS-024` E402 Import Policy and Baseline Closure | `ready` | P1 | R1 | — |
| `OPS-025` CSV Producer Marker Hardening | `ready` | P2 | R1 | — |
| `OPS-026` Main-Branch CI Observability and Required-Check Policy | `ready` | P1 | R1 | — |
| `OPS-027` Local VALIDATE and GitHub CI Contract Alignment | `planned` | P1 | R1 | — |

### DOC-020 — Agent Estate and Governance Reconciliation

| Story | Status | Priority | Risk | Dependencies |
|---|---|---|---|---|
| `DOC-021` Reconcile Agent Catalog Against Current Code | `ready` | P2 | R0 | — |
| `DOC-022` Classify Compatibility Wrappers and Aliases | `ready` | P2 | R0 | `DOC-021` |
| `DOC-023` Routing and Orchestrator Ownership Consolidation | `planned` | P2 | R1 | `DOC-021`, `OPS-022` |
| `DOC-024` Agent Write-Boundary Audit | `planned` | P1 | R1 | `DOC-021` |
| `DOC-025` Learning-Output Boundary Contract | `planned` | P2 | R0 | `DOC-021` |
| `DOC-026` Product-Agent Maturity Evidence Refresh | `planned` | P2 | R1 | `DOC-021` |

### APP-010 — Governed Application Intelligence

| Story | Status | Priority | Risk | Dependencies |
|---|---|---|---|---|
| `APP-011` Approved Candidate and CV Fact Model | `blocked` | P2 | R1 | `DOC-018` |
| `APP-012` Deterministic Job-Fit Baseline | `blocked` | P2 | R1 | `SI-048`, `APP-011`, `CC-012` |
| `APP-013` Governed LLM Job-Fit Scoring | `blocked` | P2 | R2 | `APP-012` |
| `APP-014` Evidence-Backed Employer Classification | `parked` | P3 | R2 | `EO-021`, `APP-011` |
| `APP-015` CV Optimization Proposal | `parked` | P3 | R2 | `APP-011`, `APP-013` |
| `APP-016` Application Letter Drafting | `parked` | P3 | R2 | `APP-013`, `APP-015` |
| `APP-017` Application Artifact Review and Provenance Workflow | `parked` | P3 | R2 | `APP-015` |
| `APP-018` CV Update Proposal Agent | `parked` | P4 | R2 | `APP-017` |

### OPS-030 — Maturity Refactor and Platform Readiness

| Story | Status | Priority | Risk | Dependencies |
|---|---|---|---|---|
| `OPS-031` FREEZE-002 Maturity Scorecard and Entry Gate | `planned` | P2 | R1 | `CC-015`, `DOC-016` |
| `OPS-032` REFACTOR-001A Runtime Inventory and Risk Map | `parked` | P3 | R1 | `OPS-031` |
| `OPS-033` REFACTOR-001B Module Boundary Plan | `parked` | P3 | R0 | `OPS-032` |
| `OPS-034` REFACTOR-001C Defect and Stop Alignment | `parked` | P3 | R1 | `OPS-023`, `OPS-033` |
| `OPS-035` REFACTOR-001D Cloud/Event Readiness Pass | `parked` | P3 | R1 | `OPS-033` |
| `OPS-036` REFACTOR-001E Staged Implementation | `parked` | P3 | R2 | `OPS-034`, `OPS-035` |
| `DB-021` Cloud-Ready Batch Foundation | `parked` | P4 | R2 | `OPS-036` |
| `DB-022` DB-Backed Outbox and Event Foundation | `parked` | P4 | R3 | `DB-021` |
| `OPS-037` Kafka Event Backbone | `parked` | P4 | R3 | `DB-022` |
| `DB-023` Spark Analytics Replay or Feature Layer | `parked` | P4 | R2 | `OPS-037` |
| `DOC-027` Sustainability and Compliance KPI Maturity | `parked` | P4 | R0 | `OPS-031` |

## Unfinished or status-uncertain packages found

- FREEZE-002 has no written exit criteria.
- CONSISTENCY-001A still claims active containment although REENTRY-001A exists and later work merged.
- PROVIDER-001 still describes a pre-re-entry pause; remaining provider work is conditional.
- RUFF-GATE-001 is materially implemented except for the E402 policy/cleanup path.
- Multiple GENERIC, EXPAND, MARKET and UI plans remain marked planned after code/tests/PRs were merged.
- The Search Intelligence snapshot carries contradictory authority wording and a dated sequence.
- Agent governance registers contain rows that may now be wrappers, aliases or implemented capabilities rather than stubs.
- Runtime `DEFAULT_PROFILE` still targets `Data Engineer v1`; the operator-approved contract now requires a Machine Learning Engineer foundation, Data focus and future AI Reliability direction.
- Post-merge main CI is not observable through the available connector; PR green is the last verified evidence.

## Boundary

This refinement does not authorize provider calls, DB writes, scheduler changes, candidate/source/gate/connector mutation, automatic application generation, cloud/Kafka/Spark implementation or broad refactoring. Those remain behind item-level dependencies and risk gates.
