# CONSISTENCY-001 Project-wide Consistency and State-Truth Audit

Status: Active containment block
Boundary: Review output only, no product-pipeline mutation

## Purpose

CONSISTENCY-001 checks whether the project contains inconsistencies across code, documentation, governance, tests, scripts, validation, and project planning. It also distinguishes restart-artifact-caused or restart-artifact-amplified issues from independent drift.

## Trigger

This block was triggered after repeated retired restart-artifact failures transported incorrect project-state claims.

Known failure classes:

- `exact_repo_snapshot=true` while no repository snapshot existed in the ZIP
- stale next-work recommendation after the work had already been merged
- excessive trust in retired generated restart artifacts
- attempted repair loops that consumed time without improving product capability
- active planning surfaces carrying old and new steering logic at the same time

## Required sequence

1. Detect and measure inconsistencies.
2. Classify findings by area.
3. Classify cause as restart-artifact-caused, restart-artifact-amplified, independent drift or unknown.
4. Isolate active-risk findings from historical artifacts.
5. Contain the risk.
6. Repair current-truth artifacts in the repository.
7. Add validation or governance checks where appropriate.
8. Document lessons learned in repository artifacts only.
9. Start external MCP-001 Freeze only after current blocking inconsistencies are controlled.

## CONSISTENCY-001A Active Truth Containment

CONSISTENCY-001A is the current containment block. Its scope is governance and planning truth only.

It must:

- mark generated chat-continuation artifacts as abolished for steering
- mark NEXT/restart artifacts as untrusted steering inputs
- preserve full-repository ZIP review as a temporary bridge only
- document MCP maturity criteria for retiring full-ZIP review
- externalize MCP implementation into a separate Engineering Agent Control Plane project
- preserve the job-application-pipeline repository as first target and integration consumer
- pause product-pipeline work until MCP-backed consistency or explicit repo-backed re-entry exists

## Non-goals

CONSISTENCY-001A must not:

- repair or optimize the old generated restart mechanism
- revive NEXT as steering truth
- perform DB writes
- change scheduler behavior
- mutate candidates, sources, gates, connectors or pipeline state
- build MCP agent core inside this repository
- use exports as pipeline input or source of truth

## Cause classification

Findings should use these labels:

- `restart_artifact_caused`
- `restart_artifact_amplified`
- `independent_drift`
- `unknown`

## Exit criteria

CONSISTENCY-001A may exit only after:

- active planning has a single current steering sequence
- Repo-Truth Guardrails exist in the repository
- old Retired restart/NEXT steering is removed from current planning
- MCP externalization is documented
- full-ZIP temporary bridge and retirement criteria are documented
- validation and review show no active contradictions in touched current-truth files
