# Active Planning

Status: current planning truth
Last rebaseline: BACKLOG-REFINE-001 on 2026-07-29

## Current steering rule

The repository has exited the old CONSISTENCY/MCP containment pause through
REENTRY-001A. Product work may proceed, but only from current repository and
DB/runtime evidence and only through explicit item-level side-effect gates.

The active control surfaces are:

1. `backlog_refinement.md` — operator-readable contradiction and work-item view.
2. `backlog_catalog.json` — machine-readable DON-style work-item truth.
3. `roadmap.md` — short sequencing view.
4. `reentry001a_mcp_backed_pipeline_reentry_decision.md` — re-entry boundary.
5. `canonical_target_profile.md` — operator-approved profile hierarchy.

## Current sequence

1. `DOC-011` rebaseline active steering and remove containment-era ambiguity.
2. `SI-021` recompute the GENERIC/EXPAND evidence chain from current repo/DB truth.
3. `SI-022` run PROVIDER-001C only when the fresh evidence still requires it.
4. `SI-023` obtain a current GENERIC pass or a finite named blocker set.
5. `SI-025`/`SI-026` design and execute only a tiny operator-approved candidate apply.
6. `SI-027` prove outcome and rollback.
7. `CC-011` begin the usable V1 Top-5/job-review path.

## Canonical target profile

- Foundation: Machine Learning Engineer.
- Technical focus: Data Engineering and data-centric ML systems.
- Future direction: AI Reliability / Data & AI Reliability Engineering.
- GenAI is a cross-cutting engineering competency, not a separate target profile.

## Truth rules

- Repository code, tests and migrations are implementation truth.
- DB/runtime evidence is required for live-state claims.
- Current docs and this backlog steer planning only after contradictions are resolved.
- Merged PRs prove implementation, not current runtime health.
- Reference and archive artifacts may supply ideas; they do not steer directly.
- Exports, retired NEXT/restart artifacts, chat and assistant memory are not project truth.
- Missing evidence yields `needs_inspection` or a blocked item, never a guessed continuation.

## Parked and conditional tracks

The following remain visible but are not immediate steering:

- V1 application intelligence and LLM features.
- FREEZE-002 and REFACTOR-001.
- Cloud, outbox, Kafka and Spark.
- CV update automation.
- Provider calls, scheduler changes and all mutating paths without their explicit gates.

## Historical containment note

CONSISTENCY-001A, the external MCP freeze and the full-ZIP bridge remain useful
lessons and evidence. They are no longer the active sequence. The external MCP/DON
project remains an engineering control plane and target-work enabler, not an
implementation core inside this repository.
