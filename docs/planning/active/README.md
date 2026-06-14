# Active Planning

Status: Current Truth
Last updated for: CONSISTENCY-001A v8 and external MCP-001 Freeze

## Current active sequence

Project work is currently in containment mode.

The active priority is:

1. CONSISTENCY-001A Active Truth Containment in this repository.
2. Repo-Truth Guardrails in this repository.
3. Removal of active Retired restart/NEXT steering from current planning.
4. Full-repository ZIP review as a temporary bridge until MCP maturity.
5. External MCP-001 Freeze as priority 1 for sustainable throughput recovery.
6. MCP-backed consistency re-check.
7. Retirement of the full-ZIP bridge only after MCP maturity is demonstrated.
8. After CONSISTENCY-001A closes, dedicate project capacity to the external MCP project until it can replace the temporary full-ZIP bridge.
9. Resume product-pipeline work only from repo/DB/MCP-backed state.

## MCP-001 Freeze scope

MCP-001 is now the priority-1 throughput recovery campaign. It supersedes the previous active freeze campaign for steering purposes.

The MCP agent core is not implemented inside this repository. This repository remains the first target project and integration consumer.

Future integration in this repository is limited to:

- project profile / adapter configuration
- allowed validation definitions
- DB read-only inspection contracts
- rollback scope declarations
- governance references
- evidence-packet contracts

The agent core, policy engine, capability registry, decision flight, audit ledger, rollback manager, confidence loop, cost control, tool integrity checks, red-team evals and GUI control plane belong in a separate MCP / Engineering Agent Control Plane project.

## Current truth rules

- The repository is the only project truth.
- Chat retired restarts remain abolished as a steering mechanism.
- Retired restart artifacts, NEXT reports, exports, assistant memory and chat summaries are not project truth.
- Full-repository ZIP review is a temporary bridge, not a permanent operating model.
- The full-ZIP bridge is retired only after MCP can reliably provide repo/DB-backed state inspection, validation reliability, fallback/unknown handling, consistency checks, auditability and enough successful confidence-scored iteration flights.
- Exports remain review outputs only and must not become pipeline input, gate input, activation prerequisite, or source of truth.
- MCP must be local-first and cost-controlled: repo, git, DB read-only, validation, policy, audit, rollback, confidence and reports run locally; LLM calls receive only compact evidence packets.

## Active anchors

- `consistency001_project_consistency_and_state_truth_audit.md`
- `repo_truth_guardrails.md`
- `mcp001_external_engineering_agent_control_plane.md`
- `mcp001_external_integration_contract.md`
- `rules001_project_rules_index.md`

## Product-pipeline pause

Provider, GENERIC, EXPAND, APPLY, UI, MATCH, GOLD, DOCGEN and V1 product work is paused. After CONSISTENCY-001A closes, the next active work is the external MCP project until MCP can take over repo-state continuation from the temporary full-ZIP bridge. Product-pipeline work resumes only from repo/DB/MCP-backed state or an explicit repo-backed re-entry decision.

## Superseded planning

Previous active planning that placed PROVIDER-001B/C, Generik, Safe-Apply, V1 or the old freeze path before MCP-001 is superseded for active steering. It may remain only as historical context in archived documents, not as current project direction.
