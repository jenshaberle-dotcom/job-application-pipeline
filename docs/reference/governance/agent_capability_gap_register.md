# Agent Capability Gap Register

Status: current governance register  
Scope: known capability gaps from GOV-001D  
Boundary: documentation only; no runtime changes

## Purpose

This register tracks capability gaps discovered during the agent capability audit.

It is intentionally not a backlog for all ideas. It only records gaps that can cause one of the following:

- false negatives,
- unsafe writes,
- misleading system state,
- confusing operator flow,
- duplicate agent responsibility,
- documentation that overstates what the system can do.

## Gap States

| State | Meaning |
|---|---|
| `open` | Gap exists and has no implemented mitigation. |
| `mitigated` | Guardrail exists but capability is not fully solved. |
| `accepted_for_now` | Known limitation accepted for current maturity stage. |
| `blocked` | Cannot proceed without architecture or operator decision. |
| `resolved` | Gap has been closed and validated. |

## Current Gap Register

| ID | Gap | Area | Risk | State | Next action |
|---|---|---|---|---|---|
| GOV-GAP-001 | Stop taxonomy incomplete | Stopper Reassessment | High false-negative risk if stale/over-sensitive stops are final. | `mitigated` | STOP-002 Stop Taxonomy & Repair Strategy Registry. |
| GOV-GAP-002 | Repair strategy registry missing | Stopper/Reprocess | Stage-2 plans exist for known cases but not all stop classes. | `open` | Define repair strategy per stop type. |
| GOV-GAP-003 | Router/orchestrator overlap | Queue / Next-Safe-Action / Chain / Nightly | Confusing or duplicated next-action logic. | `open` | GOV-001E Routing/Orchestration Consolidation Review. |
| GOV-GAP-004 | Agent write boundaries inconsistent | Safety / Governance | Some write-capable scripts do not expose a consistent dry-run/apply model. | `open` | GOV-001E Write Boundary Review. |
| GOV-GAP-005 | Connector chain fragmentation | Connector lifecycle | Many small agents can hide responsibility gaps. | `open` | GOV-001F Connector Chain Responsibility Contract. |
| GOV-GAP-006 | Stubs/placeholder agents look real | Documentation / Architecture | Diagrams/docs may imply capabilities that are not implemented. | `open` | Mark or archive stubs during DOC-001. |
| GOV-GAP-007 | Learning agents may be mistaken for gate decision agents | Learning / Gates | Learning outputs could accidentally be treated as evidence. | `open` | Add learning-output boundary to governance docs. |
| GOV-GAP-008 | Detail repair agent is large and multifunctional | Evidence repair | Hidden responsibility mixing and maintenance risk. | `open` | Audit subresponsibilities and consider extraction later. |
| GOV-GAP-009 | Promotion gate quality remains uncertain | Candidate promotion | Türsteher may still block relevant candidates. | `open` | EO-003 after GOV/DOC baseline. |
| GOV-GAP-010 | Doku drift hides current truth | Documentation | New contributors/operators may understand a different project than the current system. | `open` | DOC-001 Documentation Rebaseline. |
| GOV-GAP-011 | ADR decision anchor drift | Documentation / ADR | Major decisions have recently lived in planning/governance/PRs instead of ADRs. | `open` | DOC-001 ADR Rebaseline. |
| GOV-GAP-012 | Scheduler/runtime-health agent capability unclear | Operations | Scheduled automation and agent health are not yet fully modeled. | `open` | Future operations/health monitor audit. |

## Gap Escalation Rules

A gap must be escalated before further implementation if it affects:

- candidate status writes,
- source activation,
- connector registration,
- scheduler behavior,
- external requests,
- evidence/gate writes,
- false-negative control,
- legal/access-risk handling.

## Current Sequence

1. Finish GOV-001 capability/governance baseline.
2. Start DOC-001 rebaseline only after the agent responsibility model is stable.
3. Build STOP-002 after documentation and governance truth are coherent enough.
4. Resume EO/connector expansion only after stop taxonomy and promotion quality risks are controlled.
