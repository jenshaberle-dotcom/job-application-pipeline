# Active Planning

Status: current planning truth
Last rebaseline: Product-authority preparation after BACKLOG-REFINE-001

## Product authority

The Pipeline is a **Class A — Intent Locked** project.

The active engineering backlog remains the implementation inventory, but it is subordinate to the operator-approved product contract under `docs/product/`.

DON may adapt technical design and sequencing. It may not infer unresolved product behavior or treat the current implementation as the desired product definition.

`PRD-001` is the current product-alignment gate. It is progressive: only the decisions required for the next useful vertical slice must be resolved. It is not a blanket freeze on safety, defect, evidence or operations work.

## Current steering rule

The repository has exited the old CONSISTENCY/MCP containment pause through
REENTRY-001A. Product work may proceed, but only from current repository and
DB/runtime evidence and only through explicit item-level side-effect gates.

Product-shaping work additionally requires approved requirements and acceptance scenarios from `docs/product/`.

The active control surfaces are:

1. `../../product/README.md` — product authority and decision status.
2. `prd001_product_intent_rebaseline.md` — progressive PRD-alignment gate.
3. `backlog_refinement.md` — operator-readable contradiction and work-item view.
4. `backlog_catalog.json` — machine-readable engineering work-item inventory.
5. `roadmap.md` — short sequencing view.
6. `reentry001a_mcp_backed_pipeline_reentry_decision.md` — re-entry boundary.
7. `canonical_target_profile.md` — recorded profile hierarchy pending PRD confirmation.

## Current sequence

1. `PRD-001` confirm the product decisions required for the first useful vertical slice.
2. `DOC-011`/planning reconciliation may continue in parallel where it does not define product semantics.
3. `SI-021` recompute the GENERIC/EXPAND evidence chain from current repo/DB truth.
4. `SI-022` run PROVIDER-001C only when fresh evidence still requires it.
5. `SI-023` obtain a current GENERIC pass or a finite named blocker set.
6. Reclassify the active candidate/V1 items against approved product requirements and scenarios.
7. Start candidate apply, Top-5, ranking, queue or review behavior only when the relevant product contract is approved.

## Canonical target profile

The repository currently records:

- Foundation: Machine Learning Engineer.
- Technical focus: Data Engineering and data-centric ML systems.
- Future direction: AI Reliability / Data & AI Reliability Engineering.
- GenAI is a cross-cutting engineering competency, not a separate target profile.

This hierarchy remains recorded repository truth pending explicit confirmation in the product decision register. No runtime or product behavior should silently expand it.

## Truth rules

- Operator-approved product requirements and scenarios define desired behavior.
- Repository code, tests and migrations are implementation truth.
- DB/runtime evidence is required for live-state claims.
- Current docs and this backlog steer planning only after contradictions are resolved.
- Merged PRs prove implementation, not current runtime health or product desirability.
- Reference and archive artifacts may supply ideas; they do not steer directly.
- Exports, retired NEXT/restart artifacts, chat and assistant memory are not project truth.
- Missing evidence yields `needs_inspection` or a blocked item, never a guessed continuation.
- Missing product intent yields `open_operator_decision`, never an inferred default.

## Parallel work allowed during PRD-001

- safety and security fixes;
- defect repair;
- documentation consistency;
- read-only evidence recomputation;
- CI and runtime stabilization;
- bounded infrastructure work that does not define product behavior.

## Product-shaping work gated by PRD-001

- candidate apply semantics;
- Top-5 and ranking behavior;
- queue composition;
- operator review actions;
- target-profile interpretation;
- application intelligence;
- autonomous product decisions.

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
