# Architecture Documentation

Status: current truth navigation  
Scope: DOC-001G architecture reader path

## Current architecture entry points

Read these first:

1. `current_system_overview.md`
2. `system_diagrams.md`
3. `architecture_document_status.md`
4. `current_truth_documentation_map.md`
5. `pipeline_state_machine.md`
6. `safety_security_state_architecture.md`
7. `gate_contract_baseline.md`
8. `agent_permission_matrix.md`

## Current role of this directory

This directory explains the current Search Intelligence architecture and the
contracts that protect it.

Architecture documents should answer:

- What is the current system?
- What are the main stages and state transitions?
- Which agents are responsible for what?
- Which boundaries must not be crossed?
- Which diagrams represent the current system?
- Which older architecture files are reference or historical context only?

## Document status groups

| Group | Role | Examples |
|---|---|---|
| Current Truth | Main reader path and system narrative | `current_system_overview.md`, `system_diagrams.md` |
| Active Contract | Rules that implementation/tests should respect | `pipeline_state_machine.md`, `gate_contract_baseline.md` |
| Reference | Useful terminology/taxonomy, not the main narrative | `search_intelligence_terminology.md`, `source_taxonomy_and_source_roles.md` |
| Historical / Needs consolidation | Older narratives that must not override Current Truth | `search_intelligence_architecture.md`, `search_intelligence_current_state.md` |

See `architecture_document_status.md` for the full DOC-001G classification.

## Deep Ocean architecture style

Architecture docs should be calm, concrete and product-readable:

- use Mermaid diagrams for versioned architecture visuals,
- describe signal depth, evidence, gates and repair loops explicitly,
- avoid hype language and decorative metaphors that do not clarify responsibility,
- keep the Ocean Deep identity as orientation, not as visual clutter.

## Current vs historical warning

Some older architecture documents still contain useful context but also stale
entry-point language. During DOC-001, Current Truth wins over older narratives.

Prefer:

- `current_system_overview.md`
- `system_diagrams.md`
- `architecture_document_status.md`
- `current_truth_documentation_map.md`

over older Search Intelligence architecture narratives.
