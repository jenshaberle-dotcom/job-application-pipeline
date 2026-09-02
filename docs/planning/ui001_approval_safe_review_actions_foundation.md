# UI-001 Approval-Safe Review Actions Foundation

Status: partially implemented foundation; broader action set planned

## Purpose

UI-001 prepares the Control Center for useful operator actions without turning
buttons into hidden pipeline mutations.

The near-term goal is to make review-required states actionable through visible
review dialogs and auditable service calls. This should support the product path
toward candidate creation, gate review, and source lifecycle operation while
respecting the current safety boundaries.

## Current truth — 2026-09-02

The foundation is no longer entirely hypothetical:

- the React Product V1 Control Center already exposes a narrowly allowlisted
  source-connector final-approval action;
- job-review labels append reviewed evidence through a bounded action and do not
  mutate ranking, Top-5 membership, lifecycle or application state;
- the DEMO-001 Application Workspace exposes one explicit review-draft generation
  action, but that action grants no application approval, submission or send
  authority;
- the wider candidate/gate repair action set described below remains planned and
  must not be added to the 2026-09-03 demo critical path merely for presentation.

The Jinja2 Search Intelligence Control Center remains an operational fallback.
Its Agent Monitor is now DB-backed Agent Monitor v1, but it still summarizes
persisted lifecycle/gate/orchestrator signals rather than a dedicated runtime
heartbeat/quality/failure-rate model.

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

- execute direct SQL in templates or route handlers;
- bypass dry-run/apply boundaries;
- activate sources or connectors implicitly;
- mutate scheduler state as a side effect;
- write Bronze/Silver/Gold through UI-only logic;
- hide candidate/gate changes behind a generic button;
- accept CSV/Excel upload as pipeline input;
- treat an LLM/model classification as state authority without the owning product
  contract and reviewed transition boundary.

## First safe action candidates

Already implemented examples:

- reviewed source-connector final approval through the narrow React/API allowlist;
- append-only Product V1 job-review labels;
- explicit DEMO-001 `draft_for_review` generation after a ready Application
  Workspace, with no submission/send authority.

Remaining recommended candidates are review actions that already have clear
backend semantics or can be introduced with a narrow service boundary:

- mark candidate seed as `manual_review_required`;
- acknowledge known duplicate/known-company risk;
- park candidate for later URL discovery;
- request bounded URL-discovery rerun as a queued/reviewed instruction;
- approve candidate creation only after the relevant guarded apply boundary
  exists.

## Agent Monitor wording boundary

Agent Monitor v1 may describe persisted signal quality, gate history and current
lifecycle/orchestrator state. It must not imply that a dedicated runtime heartbeat,
quality metric or failure-rate telemetry model exists when it does not.

Preferred language includes:

- `DB-backed lifecycle/gate/orchestrator signal`;
- `current lifecycle state`;
- `latest persisted gate outcome`;
- `orchestrator attention signal`;
- `historical pass superseded`;
- `no runtime-health signal yet` when speaking specifically about runtime health.

The demo should not introduce a second Agent Monitor dependency into the canonical
Product V1 launcher. Agent Monitor v1 is supporting operational/backup evidence;
the canonical DEMO-001 presentation remains the React Product V1 journey.

## Post-application boundary

APP-TRACK-001 / issue #737 extends the future product journey beyond manual
submission. Gmail communication classification will be evidence/event-candidate
input, not silent application-state authority. It remains outside the DEMO-001
readiness path and must not add Gmail/runtime dependencies before the 2026-09-03
demo.
