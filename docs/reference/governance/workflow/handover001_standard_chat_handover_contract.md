# HANDOVER-001A Standard Chat Handover Contract

HANDOVER-001A defines the minimum useful handover shape for continuing this
project in a new chat without turning every handover into a project novel. It
complements STATE-001 and INSPECT-001:

- STATE-001 provides a compact machine-readable project state snapshot.
- INSPECT-001 provides a read-only Repo/DB/Docs inspection bundle.
- HANDOVER-001 defines how these artifacts should be passed into a new chat.

The goal is efficient continuity: enough context to restart safely, little
enough context to avoid wasting the new chat's attention budget.

## Required new-chat artifacts

A normal project continuation chat should start with these artifacts:

1. **State JSON** from the latest project state snapshot.
2. **Handover ZIP** containing the relevant reports, optional Markdown, and
   compact supporting files.

These two artifacts are the default restart anchor. The standalone Markdown
handover is optional when it is already included in the ZIP.

## Optional human-readable artifact

A standalone Markdown handover may be attached when useful for quick human
reading, but it must not become the source of truth.

Use it when:

- a human wants a quick narrative overview before reading JSON
- the ZIP already contains it and exporting it separately is convenient
- a complex transition needs a short executive summary

Do not use it to duplicate every project rule, historical decision, backlog
idea, or implementation detail.

## New chat opening template

A new chat should begin with a compact message like:

```text
We continue after <last completed work item>. The previous work item was
implemented, tested, merged, and cleaned up. I uploaded the latest State JSON
and Handover ZIP. Please read those first, then continue with <next work item>.
Before any patch, provide a short system-impact analysis.
```

Keep the opening to roughly 3-6 sentences unless there is a real incident or
blocked decision.

## Source of truth order

When the assistant needs state, use this order:

1. User-provided current terminal output or uploaded validation export.
2. Latest State JSON.
3. Latest INSPECT report.
4. Handover ZIP contents.
5. Repository files uploaded in the current chat.
6. Chat memory and project memory.

Chat memory is helpful context, not an exact repo-state source.

## Required content in a handover ZIP

A handover ZIP should include, when available:

- latest State JSON
- latest INSPECT JSON and Markdown reports
- short Markdown handover or README
- latest validation summary or report
- next-safe-action note
- optional backlog/governance deltas created during the chat

It should not include:

- secrets or local credentials
- large caches
- virtual environments
- database dumps unless explicitly requested and sanitized
- raw crawler outputs unless they are intentionally part of a review artifact

## Machine-readable handover expectations

Machine-readable handover state should be compact and explicit. It should
prefer booleans, lists, and short strings over long prose.

It should include:

- schema version
- generated timestamp
- exact or non-exact repo-state flag
- last completed work item
- validation summary
- current branch/head when known
- dirty-state indicator when known
- recommended next work item
- known blockers requiring user decision
- safety notes for the next assistant

If the state is not exact, it must say so explicitly.



## Minimal restart payload

The generated standard workflow handover should include a compact
`minimal_restart_payload` object in the handover JSON.

This payload is the preferred first-read surface for a new chat. It should
include:

- `required_new_chat_artifacts`
- current branch, HEAD, and dirty state
- completed standard workflow items
- validation summary
- standard workflow completion
- horizontal Freeze-Path bundle mode
- next safe action
- recommended next work item
- rules pointer
- safety boundary, including
  `requires_explicit_approval_before_external_or_product_action`

The payload should be short enough to paste into chat when uploads are limited
and structured enough that the assistant can restart without re-reading the
whole project history.

## Freeze-path bundle mode

A handover may include a Freeze-path bundle mode section when the next safe work
is a horizontal governance, validation, inspection, handover, and read-only
stabilization patch.

The handover should state whether the mode is available, which scopes are
allowed, which scopes are excluded, and which validation is required before
commit or PR.

This mode must not be mixed with product execution. External source runs,
database mutation, scheduler activation, candidate or gate changes, connector
activation, and Bronze/Silver/Gold behavior belong to separate vertical work
items unless explicitly justified.

## Freeze-path exit gate

When the freeze path is being closed, the handover may be followed by
FREEZE-001C.

FREEZE-001C should validate that the latest handover is fresh, the minimal
restart payload is present, NEXT-001 points to the next explicit product work
item, and the repository is ready to leave freeze work.

A passing exit gate does not approve external/product execution. The next
product action, such as SENSOR-001E, still requires explicit user approval.

## Anti-patterns

Avoid these handover anti-patterns:

- repeating the entire project history
- hiding exact state uncertainty behind confident wording
- copying large terminal output directly into chat when an export file is better
- treating Markdown narrative as more authoritative than JSON or validation
- mixing current truth, historical notes, and backlog ideas without labels
- creating a new governance/tooling platform when a small contract is enough

## Validation command

The contract can be checked with:

```bash
python scripts/run_handover001_validate_contract.py
```

The validator confirms that the contract document contains the required anchors
for artifacts, source-of-truth order, ZIP contents, machine-readable state,
anti-patterns, and the new-chat opening template.

## Safety boundary

HANDOVER-001A is documentation and validation tooling only.

It must not:

- perform external network requests
- write to the database
- mutate pipeline data
- activate sources or connectors
- change candidates, gates, Bronze/Silver/Gold, scheduler, or UI state
- create commits, PRs, or merges

## Relationship to future tooling

HANDOVER-001A intentionally stays smaller than MCP-001. It defines the contract
that future tools may follow, but it does not implement a project state server,
agent runtime, or broader engineering operating system.
