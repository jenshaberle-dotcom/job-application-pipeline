# GOV-001E Documentation and Governance Drift Guard

Status: current governance guardrail  
Scope: read-only drift detection, PR validation, and DOC-001 preparation  
Created from: GOV-001A static inventory intake and GOV-001B-D governance foundation

## Why this exists

GOV-001A-D made agent and documentation drift visible. That is useful, but not sufficient.
A project can still drift again if new agents, helper scripts, planning notes, or
retired restart artifacts are added without a governance trail.

This guard adds a small enforceable boundary:

- new agent-like scripts must be visible in governance documentation,
- project-state retired restart files must not accidentally become current architecture truth,
- agent counts are compared against the GOV-001A baseline,
- the check is read-only and safe to run before PRs.

## What this guard prevents

It does not prevent all documentation drift. It prevents the most dangerous form of
silent drift during the maturity/freeze phase:

```text
new agent/helper/orchestrator appears
-> no registry/classification/capability entry
-> docs and architecture slowly describe a different system than the code
```

## What this guard does not replace

This guard does not replace DOC-001.

DOC-001 still has to:

- classify ADRs as Current / Superseded / Historical / Needs rewrite,
- reduce the current documentation set,
- archive or deprecate outdated source-analysis/planning artifacts,
- rebuild the current architecture and system representations,
- establish a small Current Truth documentation layer.

## Guard command

Advisory mode:

```bash
python scripts/check_governance_drift.py --json
```

Strict mode for PR validation:

```bash
python scripts/check_governance_drift.py --strict --json
```

Strict mode should fail when a new agent-like script is not represented in governance
documentation.

## Baseline

The first baseline comes from GOV-001A:

- 49 agent-like scripts
- 52 agent-like tests

Increasing these counts is not forbidden, but it requires explicit governance
classification and capability-audit consideration.

## Relationship to GOV-001

- GOV-001B defines the governance registry foundation.
- GOV-001C defines classification rules.
- GOV-001D defines capability-audit expectations.
- GOV-001E makes drift visible in a repeatable check.

## Relationship to DOC-001

DOC-001 should decide whether this guard remains a lightweight repository check,
moves into CI, or becomes part of a broader architecture contract check.
