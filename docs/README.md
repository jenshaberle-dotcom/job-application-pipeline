# Documentation Entry Point

Status: current truth entry point
Scope: DOC-001C active reader path
Last rebaseline: DOC-001C

## Purpose

This file is the active entry point for repository documentation.

The project documentation is being rebaselined because the repository contains a
large amount of historically useful but no longer current planning and
source-analysis material. A reader should not have to infer the current system
from old build notes.

## Read this first

For the current system, read in this order:

1. `docs/architecture/current_system_overview.md`
2. `docs/architecture/system_diagrams.md`
3. `docs/architecture/current_truth_documentation_map.md`
4. `docs/governance/README.md`
5. `docs/governance/agent_governance_registry.md`
6. `docs/governance/agent_capability_audit_matrix.md`
7. `docs/governance/documentation_rebaseline_strategy.md`

## Current Truth

Current Truth documents describe the current intended system.

| Area | Document |
|---|---|
| System overview | `docs/architecture/current_system_overview.md` |
| Current diagrams | `docs/architecture/system_diagrams.md` |
| Documentation map | `docs/architecture/current_truth_documentation_map.md` |
| Governance overview | `docs/governance/README.md` |
| Agent registry | `docs/governance/agent_governance_registry.md` |
| Capability audit | `docs/governance/agent_capability_audit_matrix.md` |
| Responsibility model | `docs/governance/agent_responsibility_model.md` |
| Drift guard | `docs/governance/documentation_drift_guard.md` |
| Documentation policy | `docs/governance/documentation_rebaseline_strategy.md` |

## Reference documentation

Reference documents may remain useful, but they are not the main project story.

| Area | Examples |
|---|---|
| Database | `docs/database/tables.md` |
| Source capabilities | `docs/data_sources/source_capabilities.md` |
| Connector contracts | `docs/data_sources/search_result_connector_contract.md` |
| Security | `docs/security/search_intelligence_security_baseline.md` |
| Design | `docs/design/` |
| Observability | `docs/observability/` |
| Relevance | `docs/relevance/` |

## Historical documentation

The following areas are historical by default unless a document is explicitly
promoted into Current Truth:

- `docs/planning/`
- `docs/source_analysis/`
- `docs/project_state/`
- old source-specific candidate and connector notes
- old spike and MVP documents

Historical does not mean useless. It means:

```text
useful for traceability,
not authoritative for current architecture.
```

## ADRs

ADRs are under rebaseline.

Do not assume that every accepted ADR still fully describes the current system.
DOC-001 will classify ADRs as:

- Current
- Superseded
- Historical
- Needs rewrite

See `docs/governance/adr_rebaseline_plan.md`.

## Exports

`exports/` contains generated runtime reports and review artifacts. Exports are
not maintained documentation and must not become pipeline input or architecture
truth.

## Maintainer rule

When changing the project:

1. update the Current Truth layer if architecture or responsibilities changed,
2. update governance classification if a new agent-like artifact appears,
3. keep planning/source-analysis notes historical unless explicitly promoted,
4. do not patch obsolete documents into a half-current hybrid.
