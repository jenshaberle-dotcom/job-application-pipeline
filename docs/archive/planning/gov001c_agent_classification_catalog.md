# GOV-001C Agent Classification Catalog

Status: completed documentation/governance foundation
Scope: classification baseline after GOV-001A/B

## Context

GOV-001A produced a read-only inventory intake and found a large governance
surface:

- 49 agent-like scripts,
- 8 agent-like source files,
- 52 agent-like tests,
- 155 governance-relevant documentation files,
- 17 planning documents.

GOV-001B introduced the first agent governance registry foundation. GOV-001C
extends that foundation with a classification catalog and decision rules so the
project can distinguish product agents from helpers, stubs, historical spikes,
and consolidation candidates.

## Problem

The project increasingly uses agent-like names for multiple responsibilities:

- queue routing,
- stop reassessment,
- repair,
- source URL recovery,
- origin discovery,
- gate review,
- connector build readiness,
- connector validation,
- approval,
- lifecycle tracking,
- orchestration,
- learning loops.

Without classification, every new file that contains `agent` appears equally
important. That creates governance risk, documentation drift, and false trust in
scripts that may be helpers, historical artifacts, or placeholders.

## Implemented artifacts

This block adds:

- `docs/reference/governance/agent_classification_catalog.md`
- `docs/reference/governance/agent_classification_decision_rules.md`

The block is documentation-only.

## Main decisions

### Classification states

Agent-like artifacts are classified as one or more of:

- `product_core_agent`,
- `product_support_agent`,
- `operator_helper`,
- `historical_spike_or_legacy`,
- `stub_or_placeholder`,
- `consolidation_candidate`,
- `needs_capability_audit`.

### STOP-001 classification

The Pipeline Stopper Reassessment Agent is classified as a product core agent
for stop-validity audit and Stage-2 repair planning.

It is not an automatic unblocker.

### Queue-agent classification

The EO Candidate Queue Agent is classified as a product core router/planner.

It should route and prioritize. It should not absorb repair, stop validation,
gate evaluation, or approval responsibilities.

### Stubs/placeholders

Very small agent-like scripts are not automatically product agents. They require
inspection and one of:

- implementation behind a real contract,
- rename to helper/spike,
- retirement or archival.

### Consolidation candidates

The catalog highlights high-risk overlap zones:

- next-safe-action routing,
- stop/gate-stop handling,
- connector chain,
- URL and origin discovery,
- learning loops.

## Validation

This block should be validated with:

    python -m pytest -q
    git diff --check

There are no runtime effects.

## Boundaries

- No code changes.
- No database migration.
- No pipeline execution.
- No source activation.
- No connector changes.
- No scheduler changes.
- No attempt to rewrite current documentation yet.

## Follow-up

The next GOV-001 block should be:

    GOV-001D Agent Capability Audit Matrix

Goal:

- turn the classification catalog into an audit table,
- list expected inputs, edge cases, false-negative risks, stop classes, writes,
  tests, runtime evidence, and gaps for current product agents,
- prepare DOC-001 to rewrite the public documentation against the canonical
  registry instead of historical planning fragments.

After GOV-001D, the project should decide whether DOC-001 starts immediately or
whether one more small governance block is needed to mark helper/legacy/stub
docs before the full documentation rebaseline.
