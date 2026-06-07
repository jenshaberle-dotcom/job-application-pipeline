# Current Truth Documentation Map

Status: DOC-001 target map  
Scope: reduced documentation entry points and archive/deprecation direction

## Purpose

This document defines the intended reduced documentation structure after DOC-001.

It is not a complete rewrite of the system yet. It is the target map that prevents
DOC-001 from becoming a sentimental patchwork of old artifacts.

## Current problem

The full repository documentation surface is too large for the current project
phase. The full ZIP reviewed for DOC-001 contains a large documentation surface,
including many historical source-analysis and planning documents.

That is useful for traceability, but it is harmful when old build notes look like
current architecture.

## Current Truth layer

The active reader path should be small.

Proposed Current Truth documents:

| Document | Role |
|---|---|
| `README.md` | Product/repository entry point; concise current positioning. |
| `docs/architecture/current_system_overview.md` | Current system architecture, dataflow, and lifecycle overview. |
| `docs/architecture/pipeline_state_machine.md` | Candidate/source lifecycle state contract. |
| `docs/architecture/system_diagrams.md` | Current diagrams only; rebuilt from GOV/DOC truth. |
| `docs/governance/README.md` | Governance entry point. |
| `docs/governance/agent_governance_registry.md` | Agent registry and responsibility overview. |
| `docs/governance/agent_capability_audit_matrix.md` | Capability audit truth for agents. |
| `docs/governance/documentation_rebaseline_strategy.md` | DOC-001 documentation policy. |
| `docs/operations/runbook.md` | Operator commands and safe workflows. |
| `docs/glossary.md` | Shared terminology after cleanup. |

## Reference layer

Reference docs may remain available, but they must not be the main narrative.

Candidates:

| Area | Candidate docs |
|---|---|
| Database | `docs/database/tables.md` |
| Source capabilities | `docs/data_sources/source_capabilities.md` |
| Connector/search contracts | `docs/data_sources/search_result_connector_contract.md` |
| Security | `docs/security/search_intelligence_security_baseline.md` |
| Design | `docs/design/*` |
| Observability | `docs/observability/*` |
| Classification/relevance | `docs/classification/*`, `docs/relevance/*` |

## Historical/archive layer

Historical docs should be preserved only as traceability, not as current truth.

Default archive/deprecation candidates:

- `docs/planning/*`
- `docs/source_analysis/*`
- old source-specific candidate narratives,
- old MVP/spike documents,
- old generated or handover state docs that describe a previous architecture.

DOC-001 should not delete these blindly. It should first label, move, or index them
so that a reader understands they are historical.

## ADR layer

ADRs need a rebaseline.

Each ADR should be classified as:

- Current
- Superseded
- Historical
- Needs rewrite

ADR status must become explicit. The current project should avoid creating many
new ADRs until the reduced Current Truth layer is stable.

## First rewrite targets

DOC-001B/C should prioritize:

1. `docs/architecture/current_system_overview.md`
2. `docs/architecture/system_diagrams.md`
3. `README.md`
4. `docs/governance/README.md`
5. `docs/operations/runbook.md`

## Reader promise

After DOC-001, a new reader should be able to understand the project from the
Current Truth layer without reading historical planning notes.
