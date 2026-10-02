# Repo Truth Guardrails

Status: Current Truth
Boundary: Governance / Engineering Assistance / MCP-001
Decision: Repository-backed truth only

## Context

Repeated chat retired restart artifact failures created false or stale project-state signals. The failure was not just an artifact-layout problem. It was a trusted steering mechanism transporting incorrect claims about repository state and next work selection.

The key process correction is:

> The assistant did not stop the faulty retired restart optimization path. The operator stopped it.

This is a governance failure and a mandatory MCP-001 design input.

## Hard rules

### 1. Repository Truth Rule

The repository is the only source of truth for the project. This applies to project plan, architecture, documentation, governance rules, work-item status, validation state, implementation state, tests, known lessons learned, MCP behavior and boundaries.

### 2. No Chat-as-Truth Rule

Chat history, generated retired restart text, ZIP retired restarts, local exports, assistant memory, or conversational summaries must not define project truth. They may be used only as hints for direct repository inspection or explicitly allowed read-only database inspection.

### 3. Chat-Retired restart Abolition Rule

Chat retired restarts remain abolished as a steering mechanism. They must not return under another name as trusted project-state artifacts.

### 4. Direct inspection rule

Use current Git/repository/PR/check inspection and explicitly allowed read-only runtime
inspection. A full repository ZIP is optional inspection material, not a readiness or
continuation prerequisite. Unknown, stale and inconsistent evidence must remain explicit.

### 5. Non-Repo Non-Existence Rule

If it is not in the repository, it does not exist for the project. Exceptions require explicit repository-backed references or read-only database evidence.

### 6. Validation and Fallback Rule

If evidence is missing, stale, contradictory, or incomplete, the system must report `unknown`, `stale`, `inconsistent`, or `needs_inspection`. It must not infer a clean state from missing evidence.

### 7. MCP Externalization Rule

The MCP / Engineering Agent Control Plane is externalized into a separate project. This repository is the first target and integration consumer, not the implementation home of the agent core.

### 8. MCP Level-5 Guardrail Rule

MCP targets genuine Level-5 autonomous engineering capability across all project areas, including repo, git, PR, merge, DB migrations/writes, scheduler, candidate/source/gate/connector and pipeline actions. Every mutating action must pass a fresh decision flight before execution.

Autonomy is continuously re-earned per decision. It is not permanently assumed.

### 9. Chief Agent Rule

The Chief Engineering Agent may coordinate specialized agents, but it is not the root of trust.

The Chief Agent may be chief of agents, but never chief of truth, policy, or recovery.

Repository truth, policy engine, capability wrappers, audit ledger, validation and rollback controls have veto power.

### 10. Backup / Rollback Rule

No Level-5 action may execute without a recoverable checkpoint or an explicitly classified non-reversibility decision. Repository actions require a backup ref, tag, branch, or equivalent rollback path. DB, scheduler and pipeline actions require dry-run, affected-object inventory, before-state snapshot where feasible, rollback or compensation plan, validation, postconditions and audit logging.

### 11. Confidence Loop Rule

Expanded rights require sustained high confidence over repeated iterations, and also high confidence for the concrete action currently being considered. A high historical score never replaces the current decision flight.

### 12. Local-first Cost Control Rule

MCP must minimize paid LLM usage. Repository inspection, git inspection, DB read-only probes, validation, policy checks, audit logging, rollback planning, confidence scoring, report generation and GUI state must run locally by default. External LLM calls may receive only minimal evidence packets, not full repository dumps, and T5 decision flights must include estimated token and EUR cost before execution.

### 13. Tool Integrity and Context Firewall Rule

Tools, tool descriptions, logs, exports, markdown and external content are untrusted unless explicitly verified. Critical tools require allowlists, version checks or integrity checks. Secrets must not enter LLM context, audit logs, patches, exports or commits.

## Consequences

Generated restart artifacts and NEXT recommendations are not trusted state sources.
Continue from directly inspected repository/runtime evidence. Neither a ZIP export nor a
future MCP-maturity campaign is required before ordinary repository assessment.

## Lessons learned

- A retired restart mechanism can become more dangerous than useful if it creates confident but false state claims.
- Validation must check semantic truth claims, not only whether artifacts exist.
- A green test run is insufficient if the artifact contract itself is wrong.
- Chat convenience must not override repository-backed governance.
- Trust must be earned from inspectable repo/DB evidence each time.
- A Level-5 agent needs control architecture, not prompt-level trust.
