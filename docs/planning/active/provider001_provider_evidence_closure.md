# PROVIDER-001 Provider Evidence Closure

Status: Paused / superseded for active steering by CONSISTENCY-001A and external MCP-001 Freeze
Boundary: historical provider-evidence planning anchor, not current next work

## Purpose

PROVIDER-001 preserves the provider-backed origin-evidence closure idea for a later repo-backed re-entry decision. It is not the active steering item while CONSISTENCY-001A and the external MCP-001 Freeze are in control.

Earlier provider planning was useful for the Generik proof, but the current priority changed after the retired restart/NEXT steering failure. The active project sequence is now:

1. CONSISTENCY-001A Active Truth Containment.
2. External MCP-001 Freeze / Engineering Agent Control Plane.
3. MCP-backed consistency re-check or explicit repo-backed re-entry decision.
4. Only then resume product-pipeline work.

## Preserved future provider sequence

When this work is explicitly re-entered, the intended future sequence remains:

1. PROVIDER-001C Provider Coverage Decision Bundle
   - decide whether the provider-backed origin coverage gap is closed
   - identify remaining provider/source families that need a bounded probe
   - produce a decision artifact before any GENERIC final recheck
2. GENERIC final recheck
   - re-run the positive proof / generic evidence chain after provider coverage
   - keep outputs review-only
3. APPLY-001 only after the evidence gap is closed or explicitly accepted as open

PROVIDER-001B read-only provider evidence discovery is treated as completed by the merged read-only provider evidence work.

## Current non-goals

This document must not be interpreted as:

- the immediate next work item
- permission to run provider follow-up work now
- permission to resume Generik, EXPAND, APPLY, UI, MATCH, GOLD, DOCGEN or V1 work
- permission to use exports as source of truth
- permission to trust NEXT/restart steering

## Re-entry conditions

Provider follow-up may be re-entered only after one of these is true:

1. MCP-backed repo/DB state inspection is mature enough to replace full-ZIP review for this project.
2. An explicit full-repository-ZIP-based re-entry decision is made while the temporary bridge is still active.

Any re-entry decision must include:

- current repo truth basis
- affected files/scripts/tables/tests
- safety and false-positive/false-negative impact
- validation plan
- rollback or fallback plan
- proof that Retired restart/NEXT/export artifacts are not being used as steering truth

## System-impact boundary

Provider evidence is a proof input, not an activation decision. It may improve confidence that origin evidence can be found generically across provider-backed career portals, but it must not directly move a candidate through gates or create source targets.

## DB-backed evidence run hardening

For a future provider-backed evidence decision, the report should run with `--include-db --require-db`. If no read-only DB scan can complete, the report is intentionally not sufficient evidence for PROVIDER-001C/APPLY-001.
