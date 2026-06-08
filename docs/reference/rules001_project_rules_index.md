# RULES-001A Project Rules Index

RULES-001A is the compact index of active project collaboration and engineering
rules for the Job Application Pipeline. It is not a replacement for ADRs,
architecture docs, or implementation documentation. It is a navigational anchor:
short enough to read at handover time, explicit enough to prevent repeated
workflow and architecture mistakes.

## Purpose

The index exists to make active rules referencable without carrying the full
project history into every chat.

It should help answer:

- What constraints must be respected before changing the project?
- Which workflow rules are mandatory?
- Which ideas are backlog only?
- Which safety boundaries must not be crossed?
- Which artifacts should a new chat read first?

## Rule source-of-truth order

When there is a conflict, use this order:

1. Current repository files and tests.
2. Current local validation exports.
3. STATE-001 project state snapshot.
4. INSPECT-001 Repo/DB/Docs inspection report.
5. HANDOVER-001 chat handover contract.
6. ADRs and current architecture documents.
7. This RULES-001 index.
8. Chat memory and historical notes.

This index is an orientation layer. It must not overrule executable tests,
current repository state, or explicit ADRs.

## Architecture and safety rules

Active architecture rules:

- Prefer clean architecture over shortcuts that create cloud or production debt.
- Every meaningful change needs a short system-impact check.
- The impact check should cover Discovery, Evidence, Candidate/Gate, Connector,
  Bronze/Silver/Gold, UI/Observability, tests, docs, and rollback.
- Employer-specific fixes must improve generic pipeline capability.
- Aggregators are discovery inputs, not uncontrolled full-crawl sources.
- Defensive, bounded acquisition is mandatory.
- Avoid external requests during validation unless explicitly intended.
- Secrets, local credentials, caches, virtual environments, and database dumps
  must not be added to handovers or committed.

## Workflow rules

Mandatory workflow rules:

- Do not commit directly on `main`.
- Use a branch guard before staging or committing.
- Full `pytest -q` is required before commit and PR.
- Use VALIDATE-001 as the default local validation entry point once available; do not use it to hide failing underlying checks.
- Commit/PR/merge instructions are only provided after green local validation.
- PR blocks include `git push -u origin <branch>` before `gh pr create`.
- Merge blocks derive the PR number from the current branch or use safe current
  branch merge behavior.
- Cleanup after merge includes returning to `main`, pulling, deleting local and
  remote feature branches when applicable, pruning, and final validation.
- Long console outputs should be written to timestamped files under `exports/`.
- Prefer file artifacts or checked patch files over large chat Here-Docs.

## State and handover rules

Active handover rules:

- A new chat normally needs State JSON plus Handover ZIP.
- Standalone Markdown handover is optional when included in the ZIP.
- Exact repo state must come from STATE/INSPECT/current validation, not chat
  memory alone.
- If repo-state uncertainty exceeds roughly 5-10 percent, request current ZIP,
  state export, or concrete inspection output before patching.
- Handover artifacts should be compact and should not repeat the whole project
  history.
- Current validation output outranks older summaries.

## Documentation and governance rules

Active documentation rules:

- So wenig wie möglich, so viel wie nötig.
- Prefer a lean documentation hierarchy over a documentation operating system.
- Current documentation should be separated from planning and archive material.
- ADRs should be classified as Current, Superseded, Historical, or Needs rewrite
  when rebaselining.
- Documentation reviews should validate executable reality where feasible, not
  just wording consistency.
- Naming should use reusable, professionally understandable domain terms where
  possible.
- Bug fixes should include a lessons-learned or recurrence-guard check.

## Product and UI rules

Active product rules:

- Treat the project as a product-quality engineering project, not a tutorial.
- Ocean Deep / Deep Ocean Intelligence is the primary visual identity.
- UI logic should stay presentation-oriented; business decisions belong in
  Python view models, DB views, or explicit services.
- Review actions in the GUI must remain approval-safe and auditable.
- Candidate reset, reprocess, and removal are future gated operations, not
  implicit side effects.
- Agent Monitor must distinguish derived lifecycle status from true runtime health until a real agent-observability model exists.

## Search Intelligence rules

Active Search Intelligence rules:

- False-negative discovery is a first-class concern.
- StepStone and other aggregators should support feed-forward known-company suppression where defensively possible.
- Suppression must be temporary and learning-oriented, not permanent blindness.
- Market sensors should eventually track novelty, duplicate rate, promotion
  outcomes, and downstream gate results.
- High-travel jobs should later receive a strong matching malus or exclusion
  based on generic travel-requirement extraction.
- Candidate-company seeds from the user's own search intelligence signals have
  a minimal relevance prior, but this prior does not pass evidence gates alone.

## Backlog boundary rules

Backlog-only ideas should not be built as immediate product features unless the
current work item explicitly promotes them.

Currently backlog/tooling-governance items include:

- VALIDATE-001 Unified Validation Command (implemented foundation)
- NEXT-001 Next Safe Action Report
- MCP-001 Project State Server, read-only-first
- Market Sensors & Growth Metrics
- reset/reprocess/removal UI under explicit gates
- agent-level observability and health narratives
- Project Drift Index as a calculated metric
- DRIFT-001 Project Drift Metrics Foundation
  - Documentation Drift Index
  - Architecture Drift Index
  - ADR Currency Score
  - Validation Freshness Score
  - State Snapshot Freshness
  - Handover Completeness Score
  - Rule Coverage Score
  - Implementation-vs-Docs Mismatch Count
  - Open Governance Warnings
  - Broken/Unavailable Inspection Anchors

MCP-001 is explicitly read-only-first and must not become a hidden automation
layer for commits, DB writes, crawler activation, or approval bypassing.

## Backlog file escalation rule

A backlog item may stay as a compact entry in this RULES-001 index while:

- it is not being implemented yet
- it does not need a concrete architecture decision
- it does not carry enough detail to overload this index
- it is not the next or near-next work item

Create a dedicated planning, architecture, or ADR file only when:

- implementation starts
- design or ADR relevance appears
- multiple decisions must be documented
- the RULES-001 section becomes too large
- validation or operational behavior needs an executable contract

This keeps the repository readable: backlog ideas are not forgotten, but they
also do not become a premature documentation operating system.

## White-Whale rule

Valuable but oversized ideas should be parked in the White-Whale Backlog instead
of being forgotten or forced into the current implementation path.

Saving an idea is not abandoning it. Nicht jeder Wal muss heute gefangen werden.

## Validation command

The unified validation command can be run with:

```bash
python scripts/run_validate001_unified_validation.py --profile commit
```

The index can also be checked directly with:

```bash
python scripts/run_rules001_validate_index.py
```

The validator confirms that this document contains the required active-rule
anchors for architecture, workflow, handover, documentation, product,
Search Intelligence, backlog boundaries, and the White-Whale rule.

## Safety boundary

RULES-001A is documentation and validation tooling only.

It must not:

- perform external network requests
- write to the database
- mutate pipeline data
- activate sources or connectors
- change candidates, gates, Bronze/Silver/Gold, scheduler, or UI state
- create commits, PRs, or merges
