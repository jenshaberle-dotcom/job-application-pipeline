# Architecture Document Status

Status: current truth control surface
Scope: DOC-001G architecture consolidation
Last rebaseline: DOC-001G

## Purpose

This document prevents `docs/architecture/` from becoming a mixed pile of current
truth, old snapshots and historical terminology.

A reader should be able to tell which files are authoritative, which files are
contracts, which files are reference material, and which files are historical or
awaiting consolidation.

## Status vocabulary

| Status | Meaning |
|---|---|
| Current Truth | Main architecture narrative. Prefer this for understanding the system. |
| Active Contract | Normative architecture rule. Code/tests should not contradict it. |
| Current Reference | Useful supporting terminology or taxonomy; not the main narrative. |
| Historical Reference | Preserved for context; not current system truth. |
| Needs Consolidation | Contains useful content but conflicts with or duplicates the Current Truth path. |

## Architecture files

| File | DOC-001G status | Reader instruction |
|---|---|---|
| `README.md` | Current Truth | Directory navigation and status groups. |
| `current_system_overview.md` | Current Truth | Start here for system intent, boundaries and stage responsibilities. |
| `system_diagrams.md` | Current Truth | Start here for architecture visuals and learning/repair loops. |
| `architecture_document_status.md` | Current Truth | Use this file to decide which architecture docs are authoritative. |
| `current_truth_documentation_map.md` | Current Truth | Defines the reduced Current Truth documentation layer. |
| `pipeline_state_machine.md` | Active Contract | Lifecycle state contract; local scripts must not invent incompatible states. |
| `safety_security_state_architecture.md` | Active Contract | Safety zones, maturity freeze and no-shortcut architecture rules. |
| `gate_contract_baseline.md` | Active Contract | Gate output and diagnosis contract. |
| `agent_permission_matrix.md` | Active Contract | Agent write/network/activation permission boundaries. |
| `search_intelligence_terminology.md` | Current Reference | Terminology support; promote only stable terms into Current Truth. |
| `source_taxonomy_and_source_roles.md` | Current Reference | Source type/source role distinction. |
| `historical_terminology.md` | Historical Reference | Preserves old wording and current interpretation; not a main entry point. |
| `search_intelligence_architecture.md` | Needs Consolidation | Older architecture narrative; do not treat as primary current truth. |
| `search_intelligence_current_state.md` | Needs Consolidation | Useful 2026-06-07 snapshot, but no longer the primary architecture entry point. |

## Current Truth rule

When a contradiction exists, resolve in this order:

1. active safety and governance contracts,
2. `current_system_overview.md`,
3. `system_diagrams.md`,
4. `pipeline_state_machine.md`,
5. `gate_contract_baseline.md`,
6. reference or historical architecture files.

Do not patch an older narrative into a half-current hybrid. Either promote its
stable content into Current Truth, mark it as reference/historical, or rewrite it
as a clean current document.

## Follow-up actions

- DOC-001H should classify ADRs against this architecture status surface.
- DOC-001I/J should decide whether the two `Needs Consolidation` files are
  rewritten, reduced to reference notes, or archived.
- README contract anchors should move toward Current Truth docs and tests once
  the rebaseline is stable.

## DOC-001H database and archive note

DOC-001H adds the active database reference entry points:

- `docs/reference/database/README.md`
- `docs/reference/database/schema_overview.md`
- `docs/reference/database/schema_relationships.md`

It also adds `docs/archive/documentation_path_status.md` as the first
docs-path triage surface before any large physical archive move.

