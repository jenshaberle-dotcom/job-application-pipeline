# UI-001 Approval-Safe Review Actions Foundation

Status: planned design contract

## Purpose

UI-001 prepares the Control Center for useful operator actions without turning
buttons into hidden pipeline mutations.

The near-term goal is to make review-required states actionable through visible
review dialogs and auditable service calls. This should support the product path
toward candidate creation, gate review, and source lifecycle operation while
respecting the current freeze and safety boundaries.

## Required interaction pattern

Every mutating UI action must follow this pattern:

1. User opens an action from a reviewable object.
2. Dialog shows evidence, current state, boundary, and expected result.
3. Dialog shows side effects explicitly.
4. User confirms.
5. Backend calls an existing safe service or a new bounded service.
6. Service writes audit/event/provenance.
7. UI refreshes from DB/read model.

## Hard boundaries

The UI must not:

- execute direct SQL in templates or route handlers
- bypass dry-run/apply boundaries
- activate sources or connectors implicitly
- mutate scheduler state as a side effect
- write Bronze/Silver/Gold through UI-only logic
- hide candidate/gate changes behind a generic button
- accept CSV/Excel upload as pipeline input

## First safe action candidates

Recommended early action candidates are review actions that already have clear
backend semantics or can be introduced with a narrow service boundary:

- mark candidate seed as `manual_review_required`
- acknowledge known duplicate/known-company risk
- park candidate for later URL discovery
- request bounded URL-discovery rerun as a queued/reviewed instruction
- approve candidate creation only after EXPAND-005C apply boundary exists

## Agent Monitor wording boundary

Until a dedicated agent-observability model exists, Agent Monitor cards should
use language such as:

- `derived lifecycle status`
- `gate-history signal`
- `orchestrator attention signal`
- `no runtime-health signal yet`

They should not imply that a real runtime heartbeat, quality metric, or failure
rate exists unless it is backed by a dedicated agent run/health table or view.
