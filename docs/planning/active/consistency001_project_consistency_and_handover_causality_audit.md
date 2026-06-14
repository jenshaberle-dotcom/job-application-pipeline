# CONSISTENCY-001 Project-wide Consistency and Handover-Causality Audit

Status: Active next governance block  
Boundary: Review output only, no product-pipeline mutation

## Purpose

CONSISTENCY-001 checks whether the project contains inconsistencies across code,
documentation, governance, tests, scripts, validation, and project planning.

It must also distinguish:

- inconsistencies caused or amplified by chat handover artifacts
- independent project drift
- stale documentation
- stale planning state
- implementation/test mismatch
- governance rule mismatch

## Trigger

This block was triggered after repeated handover artifact failures transported
incorrect project-state claims.

Known failure classes:

- `exact_repo_snapshot=true` while no repository snapshot existed in the ZIP
- stale next-work recommendation after the work had already been merged
- excessive trust in generated handover artifacts
- attempted repair loops that consumed time without improving product capability

## Required sequence

1. Detect and measure inconsistencies.
2. Classify findings by area:
   - code
   - tests
   - documentation
   - governance
   - project plan
   - validation
   - DB/read-only state
   - workflow metadata
3. Classify cause:
   - handover-caused
   - handover-amplified
   - independent drift
   - unknown
4. Isolate active-risk findings from historical artifacts.
5. Contain the risk.
6. Repair current-truth artifacts in the repository.
7. Add validation or governance checks where appropriate.
8. Document lessons learned in repository artifacts only.
9. Proceed to MCP-001A only after current blocking inconsistencies are controlled.

## Non-goals

CONSISTENCY-001 must not:

- repair or optimize the old handover mechanism
- create new handover dependencies
- mutate production pipeline data
- activate candidates, sources, gates, connectors, Bronze, Silver, or Gold
- use exports as pipeline inputs
- treat chat content as project truth

## Success criteria

CONSISTENCY-001 is complete when:

- current repository state is clean and validated
- active project plan reflects the new sequence
- repo truth guardrails are documented
- historical handover artifacts are marked untrusted or excluded from active steering
- no current blocking inconsistency remains for MCP-001A planning
- MCP-001A scope explicitly follows the repo-truth guardrails
