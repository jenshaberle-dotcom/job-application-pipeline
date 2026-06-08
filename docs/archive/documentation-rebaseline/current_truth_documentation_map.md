# Current Truth Documentation Map

Status: DOC-001 current truth map
Scope: reduced documentation entry points and archive/deprecation direction
Last rebaseline: DOC-001G

## Purpose

This document defines the intended reduced documentation structure after DOC-001.

It is not a complete rewrite of every historical document. It is the target map
that prevents DOC-001 from becoming a sentimental patchwork of old artifacts.

## Current problem

The full repository documentation surface is too large for the current project
phase. The full ZIP reviewed for DOC-001 contains a large documentation surface,
including many historical source-analysis and planning documents.

That is useful for traceability, but it is harmful when old build notes look like
current architecture.

## Current Truth layer

The active reader path should be small.

Current Truth documents:

| Document | Role |
|---|---|
| `README.md` | Product/repository entry point, motivation, Deep Ocean identity, concise current positioning. |
| `docs/README.md` | Documentation entry point and reader order. |
| `docs/current/architecture.md` | Current system architecture, dataflow, boundaries and lifecycle overview. |
| `docs/current/system-diagrams.md` | Current diagrams only; rebuilt from GOV/DOC truth. |
| `docs/archive/documentation-rebaseline/architecture_document_status.md` | Architecture file classification and conflict-resolution order. |
| `docs/current/pipeline.md` | Candidate/source lifecycle state contract. |
| `docs/reference/governance/README.md` | Governance entry point. |
| `docs/reference/governance/agent_governance_registry.md` | Agent registry and responsibility overview. |
| `docs/reference/governance/agent_capability_audit_matrix.md` | Capability audit truth for agents. |
| `docs/reference/governance/documentation_rebaseline_strategy.md` | DOC-001 documentation policy. |
| `docs/guides/operator-runbook.md` | Operator commands and safe workflows. |
| `docs/reference/glossary.md` | Shared terminology after cleanup. |

## Reference layer

Reference docs may remain available, but they must not be the main narrative.

Candidates:

| Area | Candidate docs |
|---|---|
| Database | `docs/reference/database/tables.md` |
| Source capabilities | `docs/reference/sources/source_capabilities.md` |
| Connector/search contracts | `docs/reference/sources/search_result_connector_contract.md` |
| Security | `docs/reference/security/search_intelligence_security_baseline.md` |
| Design | `docs/design/*` |
| Observability | `docs/observability/*` |
| Classification/relevance | `docs/classification/*`, `docs/relevance/*` |
| Architecture terminology | `docs/reference/search-intelligence/terminology.md`, `docs/reference/search-intelligence/source_taxonomy.md` |

## Historical/archive layer

Historical docs should be preserved only as traceability, not as current truth.

Default archive/deprecation candidates:

- `docs/archive/planning/*`
- `docs/archive/source-analysis/*`
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

## Architecture conflict-resolution rule

When two docs disagree, the active architecture path wins over old planning or
source-analysis notes.

Within `docs/architecture/`, use `architecture_document_status.md` to determine
whether a file is Current Truth, Active Contract, Current Reference, Historical
Reference or Needs Consolidation.

## Reader promise

After DOC-001, a new reader should be able to understand the project from the
Current Truth layer without reading historical planning notes.

## DOC-001H database and archive note

DOC-001H adds the active database reference entry points:

- `docs/reference/database/README.md`
- `docs/reference/database/schema_overview.md`
- `docs/reference/database/schema_relationships.md`

It also adds `docs/archive/documentation_path_status.md` as the first
docs-path triage surface before any large physical archive move.

## DOC-001I physical archive note

DOC-001I physically archives the former `docs/diagrams/` pages into
`docs/archive/diagrams/`.

Current replacements:

- `docs/current/system-diagrams.md` replaces the old connector architecture diagram.
- `docs/reference/database/schema_relationships.md` replaces the old Bronze/Silver data model diagram.

This is the first small physical archive move. Larger planning/source-analysis
moves still require a dedicated reference/link check.
