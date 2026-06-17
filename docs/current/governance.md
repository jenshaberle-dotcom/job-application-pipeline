# Governance Current Truth

Status: current truth

Governance exists to keep the project product-grade while it grows through
agent-like helpers, gates, source discovery and UI actions. The higher-level
engineering philosophy lives in `engineering_principles.md`; this document
focuses on operational governance rules and reference surfaces.

Current rules:

- Safety, legal risk and data integrity override speed.
- Discovery, evidence, gates, connector build, Bronze/Silver/Gold and UI changes
  need a short system-impact check.
- Agent-like artifacts must be represented in governance reference docs before
  they are treated as part of the system.
- Dry-run/apply separation is required for mutating actions.
- Planning and source-analysis notes are historical unless promoted into
  `current/`, `reference/`, `decisions/`, or active planning.

Reference surfaces:

- `../reference/governance/governance_foundation.md`
- `../reference/governance/agent_governance_registry.md`
- `../reference/governance/agent_capability_audit_matrix.md`
- `../reference/governance/documentation_drift_baseline.md`
- `../decisions/adr_status_table.md`

<!-- REENTRY-001A START -->
## MCP-backed re-entry guardrail

After an external MCP freeze, product-pipeline work may resume only through a
repository-backed re-entry decision. REENTRY-001A defines the current gate:
read-only MCP evidence may support planning, but it does not authorize mutation,
DB writes, scheduler changes, provider calls, apply, commit, PR or merge.

The first allowed product direction after the gate is the bounded GENERIC/EXPAND
stop-control and generic-evidence blocker.
<!-- REENTRY-001A END -->
