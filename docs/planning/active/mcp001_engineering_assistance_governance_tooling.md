# MCP-001 Engineering Assistance / Governance Tooling

Status: planned after Generik and Safe-Apply/Gate stabilization
Boundary: engineering-assistance layer, not product-pipeline feature

## Placement in the current Ablaufplan

1. Finish the current Generik proof cleanly.
2. Stabilize Safe-Apply / Stop-Control / Review-Gates.
3. Add MCP-001A Read-only Project State Server as a small-to-medium tooling block before the full Product V1 phase.
4. Continue Product V1: Top-5 Jobs for Jens, GUI/Review Queue, and application artifacts.
5. Run the larger code/architecture refactor after V1 and before Cloud/Event/Streaming.
6. Add MCP-001B/C Validation Runner, Patch Builder, and PR Assistant only after MCP-001A and preferably after a minimal usable V1 or stable gates.
7. Keep fully write-capable agent functions long-term only: read-only-first, local, auditable, and strictly gated.

Target path:

    Generik -> Safe Apply / Gates -> MCP-001A Read-only State Server -> Product V1 -> Refactor -> MCP-001B/C Agentic Engineering Support -> Defect Management -> Cloud/Event/Streaming

## MCP-001A scope limit

- Read-only only.
- No commit.
- No push.
- No merge.
- No DB mutation.
- No candidate/source activation.
- No scheduler change.
- No CSV/export files as pipeline input.
- DB access only through allowed read-only queries.
- All outputs are audit-marked `review_output_only_not_pipeline_input`.
- Product pipeline and Engineering Assistance remain clearly separated.

## Rationale

MCP-001A does not directly close the Generik proof and must not displace it. It is still worth placing before the full Product V1 phase because it can reduce handover, ZIP, log, repo-state and validation friction in a controlled local/read-only way.

## Repo Truth Guardrails for MCP-001A

MCP-001A must follow `docs/reference/governance/repo_truth_guardrails.md`.

Hard design implications:

- repository state is the only project truth
- chat and handover artifacts are not truth sources
- documentation must be repository-backed
- missing or contradictory evidence must produce `unknown` or `needs_inspection`
- MCP-001A is read-only first
- no commits, merges, DB writes, candidate activation, scheduler changes, or pipeline mutation
- chat switches must be reconstructed from direct repo/DB inspection, not from generated handover artifacts
