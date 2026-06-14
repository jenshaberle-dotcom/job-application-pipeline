# Repo Truth Guardrails

Status: Current Truth  
Boundary: Governance / Engineering Assistance / MCP-001A  
Decision: Repository-backed truth only

## Context

Repeated chat handover artifact failures created false or stale project-state
signals. The concrete failure mode was not only a broken artifact layout, but a
trusted handover mechanism transporting incorrect claims about repository state
and next work selection.

The key process correction is:

> The assistant did not stop the faulty handover optimization path. The operator
> stopped it.

This must be treated as a governance failure and as an MCP-001A design input.

## Hard rules

### 1. Repository Truth Rule

The repository is the only source of truth for the project.

This applies to:

- project plan
- architecture
- documentation
- governance rules
- work-item status
- validation state
- implementation state
- tests
- known lessons learned
- MCP behavior and boundaries

### 2. No Chat-as-Truth Rule

Chat history, generated handover text, ZIP handovers, local exports, assistant
memory, or conversational summaries must not define project truth.

They may be used only as hints for follow-up inspection.

### 3. Repo-backed Documentation Rule

Documentation is valid only when it exists as a repository artifact.

A project rule, lesson learned, architecture decision, or plan that exists only
in chat does not count as implemented project knowledge.

### 4. Non-Repo Non-Existence Rule

If it is not in the repository, it does not exist for the project.

Exceptions require explicit repository-backed references or read-only database
evidence.

### 5. Validation and Fallback Rule

Every project-state report must include validation and fallback behavior.

If evidence is missing, stale, contradictory, or incomplete, the system must
report `unknown`, `stale`, `inconsistent`, or `needs_inspection`.

It must not infer a clean state from missing evidence.

### 6. Defensive Chat Switch Rule

If a chat switch is unavoidable, the restart must be based on direct repository
and, where needed, read-only database inspection.

A chat switch must not depend on free-form handover artifacts as trusted truth.

### 7. MCP-001A Read-only-first Rule

MCP-001A must start as read-only engineering assistance.

Allowed:

- inspect repository state
- inspect git state
- inspect tracked documentation
- inspect tests and validation commands
- inspect allowed read-only DB state
- report inconsistencies
- produce review outputs

Forbidden in MCP-001A:

- commits
- pushes
- merges
- database writes
- candidate/source/gate/connector activation
- scheduler changes
- treating exports as pipeline inputs
- using chat/handover artifacts as truth

## Consequences

Generated handover artifacts are no longer trusted project-state sources.

Future project continuation must use direct repo/DB inspection. If context size
becomes a problem, the solution is MCP-style repository state access, not
increasingly complex chat handovers.

## Lessons learned

- A handover mechanism can become more dangerous than useful if it creates
  confident but false state claims.
- Validation must check semantic truth claims, not only whether artifacts exist.
- A green test run is insufficient if the artifact contract itself is wrong.
- Chat convenience must not override repository-backed governance.
- Trust must be earned from inspectable repo/DB evidence each time.
