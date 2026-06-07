# GOV-001B Agent Responsibility Model

Status: foundation draft.

## Purpose

This model prevents agent sprawl by defining when logic belongs in an existing agent, when it should be routed to another agent, and when a new agent is justified.

## Core rules

1. A router routes; it does not repair.
2. A repair agent repairs one bounded evidence/source/connector problem; it does not approve activation.
3. A gate agent evaluates one gate and records/returns a decision; it does not discover unrelated evidence.
4. A stopper agent reassesses stop validity and proposes Stage-2 plans; it does not silently unblock.
5. An orchestrator sequences known agents; it does not hide failed gates.
6. Any write-capable action needs an explicit safety contract and review metadata.
7. Any new agent must improve clarity more than it increases governance burden.

## New-agent decision test

Create a new agent only when all are true:

- The responsibility is distinct from existing agents.
- Adding it to an existing agent would mix roles or hide a safety boundary.
- The agent can be named by its responsibility, not by a historical work item.
- It has a clear input/output contract.
- It has tests or a documented test plan in the same PR.
- It is registered in the governance registry.

Otherwise, extend an existing agent or park the idea in the White-Whale/Backlog.

## Responsibility map

| Pipeline responsibility | Primary owner | Secondary/routed owner | Human/operator role |
|---|---|---|---|
| Candidate ordering and next safe action | EO Candidate Queue Agent | Stopper Agent, EO Chain Agent | choose whether to run suggested command |
| Stop validity reassessment | Pipeline Stop Reassessment Agent | relevant repair agent | decide whether to run Stage-2 apply |
| Source URL recovery | Origin Source Discovery / Source URL Recovery Agents | Stopper Agent for stale stops | approve apply when URL changes state |
| Detail evidence discovery/repair | Detail Evidence Repair Agent | Multi-origin/detail-link discovery components | review weak evidence or strictness changes |
| Initial/gate review | Gate-specific agents | Stopper Agent for suspicious stops | approve/reject gate decisions where required |
| Connector artifact build | Approval-gated Connector Build / Generation Agents | Connector Validation Agent | approve build/registration |
| Connector validation | Connector Validation Agent | Implementation/repair logic | approve next transition |
| Source lifecycle tracking | Source Lifecycle Tracking Agent | Orchestrator | monitor active source health |
| Search/discovery loops | StepStone Discovery Cycle / Aggregator Agents | Learning/strategy agents | inspect novelty and false-negative signals |
| Scheduling/orchestration | Nightly Orchestrator | Control Center/Attention views | act on attention states |

## STOP-001 classification

STOP-001 is governance-approved as a separate agent because it protects a cross-cutting safety boundary:

- It does not belong in the queue because the queue should not judge stop validity.
- It does not belong in detail repair because repair should not decide whether a historical stop is valid.
- It does not belong in a gate agent because stops can originate from multiple gates and operational states.

Therefore the Pipeline Stop Reassessment Agent is classified as:

- primary role: stop-audit/planner
- allowed default behavior: read-only audit and Stage-2 command planning
- forbidden default behavior: automatic unblocking, source activation, connector registration
- future requirement: STOP-002 stop taxonomy and repair strategy registry

## GOV-001 exit criteria

GOV-001 is not complete until:

- all product agents are listed in the registry
- helpers/stubs/historical scripts are separated from product agents
- write posture is explicit for each product agent
- capability audit priorities are assigned
- STOP-001 is registered
- DOC-001 can start from one canonical governance truth
