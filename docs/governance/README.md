# Governance Documentation

Status: current truth entry point
Scope: GOV-001 and DOC-001 governance navigation

## Purpose

This directory defines how the Search Intelligence system is governed during the
architecture freeze and documentation rebaseline.

Governance is not decoration. It controls agent responsibilities, write
boundaries, documentation drift, and whether a new implementation belongs in the
current maturity path or in the backlog.

## Read this first

| Topic | Document |
|---|---|
| Agent registry | `agent_governance_registry.md` |
| Agent classification | `agent_classification_catalog.md` |
| Agent classification rules | `agent_classification_decision_rules.md` |
| Responsibility model | `agent_responsibility_model.md` |
| Capability audit | `agent_capability_audit_matrix.md` |
| Capability gaps | `agent_capability_gap_register.md` |
| Documentation drift guard | `documentation_drift_guard.md` |
| Documentation rebaseline | `documentation_rebaseline_strategy.md` |
| Archive/deprecation plan | `documentation_archive_deprecation_plan.md` |
| ADR rebaseline plan | `adr_rebaseline_plan.md` |
| ADR status table | `adr_status_table.md` |

## Current governance rules

### New agent-like artifacts

A new agent-like script must not appear silently.

It needs:

- governance classification,
- responsibility boundary,
- capability audit consideration,
- tests or explicit capability gap entry,
- routing decision if it overlaps existing agents.

### Agent responsibility boundaries

- Queue agents route; they do not repair.
- Repair agents produce evidence or repair output; they do not approve themselves.
- Gate agents evaluate evidence; they do not discover evidence.
- Stopper reassessment audits stops and proposes Stage-2 plans; it does not auto-unblock.
- Approval/lifecycle agents control state transitions.

### Documentation drift

Current Truth documents must be kept small and coherent. Planning and
source-analysis documents are historical by default.

### Freeze / maturity

New ideas should not change the active architecture unless they materially
improve safety, diagnosis, generics, or product maturity. Otherwise they go into
the backlog.

## Relationship to DOC-001

DOC-001 uses this governance layer to rebuild documentation without sentimental
patchwork. Obsolete documents may be archived, deprecated, or rewritten.
