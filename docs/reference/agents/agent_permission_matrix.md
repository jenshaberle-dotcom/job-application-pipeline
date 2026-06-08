# Agent Permission Matrix

Status: active architecture contract
Scope: Search Intelligence agents and scripts

## Purpose

Every agent must have an explicit permission boundary. The project must avoid agents that can discover, decide, write, activate and clean up in the same flow.

## Permission matrix

| Agent | Zone | External network | Writes | Activation | Delete/disable | Required control |
|---|---|---:|---|---:|---:|---|
| Market Sensor | SZ0/SZ1 by runner | yes | raw observations only when ingestion runner allows | no | no | source policy and bounded connector behavior |
| Candidate Promotion / Türsteher | SZ1 | no | candidate metadata and recommendations | no | no | dry-run first for bulk promotion |
| Origin URL Finder | SZ0 | yes | reports only | no | no | bounded HTTP probing; no candidate_url write |
| Origin URL Recovery Writer | SZ1 | no | candidate_url and review state | no | no | dry-run first plus explicit apply |
| Detail Evidence Agent | SZ2 | yes | evidence and gate events | no | no | bounded page budget and gate contract |
| Connector Build Agent | SZ3 | limited/no | connector artifacts | no | no | approval-required state, artifacts are review candidates |
| Approval UI / Operator | SZ4 | no | approval and source activation events | yes | no | explicit human approval and audit event |
| Scheduler / Orchestrator | SZ5 | yes | orchestrator runs and scheduled run results | no | no | bounded wave plan and disabled-by-default escalation |
| Cleanup / Compliance Agent | SZ6 | no | disable, cleanup and removal events | no | yes | dry-run inventory and protected-target override |

## Rules

- Validation agents do not write production state.
- Writer agents do not call external networks unless explicitly allowed.
- Source activation is always human-gated.
- Destructive operations are never default targets for active_controlled entities.
- Connector artifacts are not registered connectors.
- Reports may recommend next actions, but recommendations are not automatic approvals.

<!-- BEGIN CAND-001-AGENT-PERMISSION -->
## CAND-001 Permission Boundary

The Validated Origin URL Persistence Gate belongs to the `origin_url_recovery_writer` permission family.

It may write `candidate_url` only under SZ1 with explicit apply and audit review. It may not write gates, evidence, connectors, sources or scheduler state.
<!-- END CAND-001-AGENT-PERMISSION -->
