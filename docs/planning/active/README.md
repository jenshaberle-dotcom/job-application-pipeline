# Active Planning

Status: current planning truth
Last rebaseline: REENTRY-001B deterministic V41 frontier after clean V40 `33/40`; intentional host-maintenance execution pause

## Product authority

The Pipeline is a **Class A — Intent Locked** project.

The active engineering backlog remains the implementation inventory, but it is subordinate to the operator-approved product contract under `docs/reference/product-contract/`.

DON may adapt technical design and sequencing. It may not infer unresolved product behavior or treat the current implementation as the desired product definition.

`PRD-001` is the current product-alignment gate. It is progressive: only the decisions required for the next useful vertical slice must be resolved. It is not a blanket freeze on safety, defect, evidence or operations work.

## Current steering rule

The repository has exited the old CONSISTENCY/MCP containment pause through
REENTRY-001A. Current continuation authority is now REENTRY-001B.

Product work may proceed only from current repository and DB/runtime evidence and only
through explicit item-level side-effect gates. Product-shaping work additionally
requires approved requirements and acceptance scenarios from
`docs/reference/product-contract/`.

For deterministic acquisition, the current authoritative accumulated Runtime truth is
**33/40 strict proven, 7/40 unresolved**. V40 run `32977904600` is the latest successful
acquisition evidence. V41 is diagnostic-only and has not produced acquisition evidence
yet. Technical/startup/infrastructure failures do not count as zero-rescue evidence.

The active control surfaces are:

1. `../../reference/product-contract/README.md` — product authority and decision status.
2. `prd001_product_intent_rebaseline.md` — progressive PRD-alignment gate.
3. `backlog_refinement.md` — operator-readable contradiction and work-item view.
4. `backlog_catalog.json` — machine-readable engineering work-item inventory.
5. `roadmap.md` — short sequencing view.
6. `reentry001b_deterministic_v41_frontier.md` — **current canonical re-entry and deterministic frontier**.
7. `reentry001a_mcp_backed_pipeline_reentry_decision.md` — historical V37-V39 re-entry boundary.
8. `canonical_target_profile.md` — recorded profile hierarchy pending PRD confirmation.

## Current sequence

1. Finish the intentional Windows/WSL host-storage maintenance and clean restart; do not interpret interrupted/queued runs as acquisition evidence.
2. Restore and prove self-hosted runner health, especially `job-pipeline-runtime-linux`.
3. Obtain a green exact-head V41 Chromium smoke for Runtime PR `#352`; keep `#352` **DO NOT MERGE** until that gate executes normally and passes.
4. If the smoke is green, reconsider/merge the technical-only Runtime overlay and run one fresh execution-only V41 diagnostic bound to Pipeline `4ada550e4a0ec0d84b62217528408e6e3d8b2956` + V40 `32977904600`.
5. Patch generic Pipeline URL recognition for `applylink` / `externallink` only if V41 proves reusable URL semantics; otherwise close that class cleanly without authority broadening.
6. Continue deterministic hardening until current evidence yields no further reusable generic class; only then admit the residual to the LLM booster layer.
7. The ML learning-foundation lane may continue in parallel where it does not redefine acquisition authority.
8. `PRD-001` remains the progressive gate for product-shaping behavior; deterministic read-only acquisition evidence and infrastructure stabilization may proceed without inventing product semantics.

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
- Technical failed, cancelled, skipped or startup-failed acquisition runs are non-evidence, not clean `+0` results.

## Parallel work allowed during PRD-001

- safety and security fixes;
- defect repair;
- documentation consistency;
- read-only evidence recomputation;
- CI and runtime stabilization;
- bounded deterministic acquisition diagnostics that preserve existing proof/authority boundaries;
- bounded infrastructure work that does not define product behavior;
- ML learning-foundation work that does not alter productive ranking/acquisition authority.

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

- V1 application intelligence and LLM features beyond the deferred residual booster layer.
- FREEZE-002 and REFACTOR-001.
- Cloud, outbox, Kafka and Spark.
- CV update automation.
- Provider calls, scheduler changes and all mutating paths without their explicit gates.

## Historical containment note

CONSISTENCY-001A, the external MCP freeze and the full-ZIP bridge remain useful
lessons and evidence. They are no longer the active sequence. The external MCP/DON
project remains an engineering control plane and target-work enabler, not an
implementation core inside this repository.
