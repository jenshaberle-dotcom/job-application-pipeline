# RULES-001 Project Rules Index

Status: Current Truth
Boundary: Governance / Workflow / Repo Truth

## Source-of-truth order

Current project truth must be derived in this order:

1. Git working tree and committed repository files.
2. Directly inspected repository documentation, tests, scripts and configuration.
3. Explicitly allowed read-only database inspection where relevant.
4. Local validation and test outputs produced from the current repository state.
5. Repository-backed ADRs, governance docs and active planning docs.

The following are not project truth:

- chat history
- assistant memory
- retired generated chat-continuation artifacts
- NEXT reports
- export reports
- markdown summaries outside the repository
- JSON summaries outside the repository
- retired restart ZIPs

They may be used only as hints for direct inspection.

## Chat continuation rule

Retired chat-continuation artifacts remain abolished as a steering mechanism.

Until MCP reaches sufficient maturity, continuation in a new chat requires a fresh full repository ZIP export and direct repository inspection. This is a temporary bridge, not a permanent process.

After MCP maturity is demonstrated, MCP-backed repo/DB state inspection replaces full-ZIP review. The retired chat-continuation mechanism does not return.

## MCP-001 externalization rule

MCP-001 is implemented as an external Engineering Agent Control Plane project. The job-application-pipeline repository is its first target and integration consumer.

This repository may later contain only project profile, adapter configuration, allowed validation definitions, DB read-only inspection contracts, rollback scope declarations and governance references.

## Level-5 action rule

No Level-5 mutating action may execute without:

- current repo/DB-backed truth basis
- decision flight
- policy approval
- operator approval or later mature confidence-gated approval
- audit record
- backup or rollback plan
- dry-run where feasible
- validation plan
- postcondition checks
- failure quarantine path
- cost estimate for any external LLM involvement

## Chief Agent rule

The Chief Engineering Agent may coordinate specialized agents. It must never be the root of truth, policy or recovery.

## Local-first cost rule

MCP must run local checks before LLM usage. LLM calls must use compact evidence packets and must not receive full-repository dumps or secrets by default.

## Export boundary rule

Exports are `review_output_only_not_pipeline_input`. No CSV, Excel, Markdown, JSON, ZIP or export artifact may become pipeline input, gate input, activation prerequisite or source of truth.

## Unknown-state rule

If state cannot be verified, the correct output is `unknown`, `stale`, `inconsistent`, or `needs_inspection`, not a guessed recommendation.

## Active planning governance anchors

PLAN-001 Future Readiness and Assumption Governance remains the canonical
planning anchor for future-readiness assumptions, backlog placement and
assumption-risk handling. Planning ideas are not implementation truth until they
are represented by current repo files, tests, migrations or validated scripts.

Manual company group-by outputs belong to MARKET-003A. They are review-output
only, not a pipeline input, not source-of-truth, not automatically truth, not a
gate pass and not a Gold metric.

## Event-readiness boundary

The project remains event-capable, but not event-driven yet. Event vocabulary,
stable identifiers, timestamps, auditability and outbox-ready boundaries may be
prepared, but Kafka/Spark/event backbone work is not part of this active MCP
containment patch.

## Company normalization boundary

Company normalization or same-company assumptions must not be accepted as truth
without evidence. Manual grouping can support review, but it is not source-of-
truth, not a pipeline input, not a gate pass and not a Gold metric.
## PLAN-001 reference file

The canonical PLAN-001 planning document is
`docs/planning/active/future_readiness_and_assumption_governance.md`.

This reference is retained as an active governance anchor. It does not restore
chat handover, NEXT steering or export-based project truth.

## CONSISTENCY-001B retired next-action steering boundary

`next safe action` must not be treated as active chat, handover, export or
restart steering. If the phrase remains in domain language, it is restricted to
local MCP/agent decision evidence backed by current repo/DB/test inspection.
It must not carry the retired planned-command field, the retired child-run hook or other executable child-run
instructions as active pipeline steering.
