# CONSISTENCY-001 Finding: Export and Report-chain Drift

Status: Active finding
Boundary: Review output only, no pipeline input

## Finding

The project has repeatedly produced useful review artifacts under `exports/`, but export/report chains also created confusion when outputs were treated as steering truth or when multiple generated artifacts contradicted repository state.

## Decision

Exports remain review outputs only. They must not become:

- pipeline input
- gate input
- activation prerequisite
- source of truth
- chat-restart truth
- MCP truth source

## Current containment

- Retired restart/NEXT steering is not trusted.
- Full-repository ZIP review remains a temporary bridge until MCP maturity.
- MCP must inspect repository and DB state directly, not consume exports as truth.
- Report-chain refresh work is paused until MCP-backed state exists or explicit repo-backed re-entry is approved.
