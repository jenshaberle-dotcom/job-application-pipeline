# ARCH-001 Safety, Security and Pipeline State Architecture Baseline

Status: active architecture contract
Scope: Search Intelligence maturity campaign
Mode: architecture freeze / maturity mode

## Purpose

ARCH-001 freezes the safety, security and state architecture before further pipeline transitions are automated.

The project is no longer allowed to change architecture opportunistically. New ideas enter the active plan only when they are expected to improve a named area by roughly 15 to 20 points or close a measured pipeline gap. Everything else goes to the White-Whale or product backlog.

## Current maturity target

The target is functional 90+ maturity before polish.

Functional 90+ means:

- architecture contracts are explicit
- safety zones are known before implementation
- agent permissions are bounded
- security boundaries are not implicit
- lifecycle transitions are explainable
- gates produce diagnosis, not only stop states
- read-only analysis is separated from write/apply modes
- scheduler automation is deferred until its inputs are mature

## Safety zones

| Zone | Name | Write boundary | Required control |
|---|---|---|---|
| SZ0 | Read-only analysis and reporting | exports and logs only | default allowed; no database mutation |
| SZ1 | Candidate metadata write | candidate URL, candidate status, candidate notes | dry-run first plus explicit apply |
| SZ2 | Evidence and gate event write | evidence rows, gate events, gate reviews | dry-run first plus gate contract |
| SZ3 | Connector artifact generation | connector artifacts and review exports | approval-required state; no registration side effect |
| SZ4 | Source registration and activation | source registry and active profiles | manual approval gate only |
| SZ5 | Scheduled production execution | orchestrator runs and scheduled run state | bounded schedule policy plus maturity evidence |
| SZ6 | Destructive, disabling, cleanup or compliance | disable markers, cleanup events, removal events | dry-run inventory plus explicit protected-target override |

## Escalation rule

A workflow may move from a lower zone to a higher zone only when all of these conditions are true:

- the lower-zone report exists
- selected targets are visible before write/apply
- protected targets such as active_controlled are excluded unless explicitly opted in
- the next zone has a documented gate contract
- an audit event can explain who or what made the decision

## Architecture freeze rule

During maturity mode, active work may only close an architecture contract, fix a measured pipeline gap, or improve measurability or diagnosis.

## Non-goals for ARCH-001

ARCH-001 does not implement new connectors, change scheduler behavior, activate sources, rewrite the UI, or relax gates. It defines the contracts that later implementation must obey.
