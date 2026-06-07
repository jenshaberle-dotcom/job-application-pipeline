# GOV-001E Documentation and Governance Drift Guard

Status: implemented as read-only guard foundation  
Scope: governance and documentation drift prevention

## Intent

GOV-001E turns the governance work from passive documentation into a lightweight
guardrail. It answers the question:

```text
Does GOV-001A-D now effectively prevent further documentation drift?
```

Answer: not fully by itself. GOV-001E adds the first enforceable read-only check.

## Implemented artifacts

- `scripts/check_governance_drift.py`
- `tests/test_governance_drift_check.py`
- `docs/governance/documentation_drift_guard.md`

## Boundaries

- no database access
- no external network
- no pipeline execution
- no connector/source/scheduler changes
- no mutation of repository files
- default mode is advisory
- strict mode can fail PR validation on hard governance drift findings

## Key rule

Any new agent-like script must be represented in the governance registry,
classification catalog, capability matrix, gap register, or responsibility model.

## Why this is needed before DOC-001

DOC-001 will reduce and rebuild the documentation system. Until then, GOV-001E
prevents the most damaging new drift: adding new product-like agents without a
governance trace.

## Follow-up

After DOC-001, revisit the guard and decide whether it should:

- be included in the architecture contract check,
- become a CI step,
- check ADR status classification,
- check that Current Truth docs exist and obsolete docs are archived/deprecated.
