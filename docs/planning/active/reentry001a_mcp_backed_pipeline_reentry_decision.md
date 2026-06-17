# REENTRY-001A MCP-backed Pipeline Re-Entry Decision

Status: current re-entry gate
Date: 2026-06-17
Boundary: planning and governance truth only; not a product-pipeline mutation

## Purpose

REENTRY-001A records the first repo-backed decision point for resuming
job-application-pipeline product work after the external MCP control-plane freeze.
It converts the temporary pause condition into an explicit, auditable re-entry gate.

This document does not authorize apply-capable work by itself. It defines the
minimum evidence and the bounded next product path that may be planned after MCP
has demonstrated safe read-only inspection against this repository.

## Evidence considered

The re-entry decision is based on direct repository and MCP-backed inspection,
not on chat handovers, retired NEXT artifacts, exports, assistant memory or
stale generated summaries.

Accepted evidence for this gate:

- the job-application-pipeline repository is on `main`, clean, and repo-backed
  project-state reports `ready_for_target_work`;
- patch-readiness reports `ready_to_patch` with validation configured and
  passing;
- the external MCP control-plane can run a plan-only flight against this target
  with `authorization_scope=read_only_plan`;
- mutating rights remain explicitly false for mutation, apply, commit, PR,
  DB write, provider call, scheduler mutation and remote-state mutation;
- side-effect boundaries remain enforced for plan-only work;
- the operator brief and context-pack commands can read this target and surface
  repository-index, target-profile, patch-readiness and governance packs;
- active planning snippets were reviewed from repository files and not from
  retired steering artifacts.

## Decision

Product-pipeline work may re-enter planning only through a bounded, repo-backed
path. The next product direction is:

1. close the current GENERIC/EXPAND stop-control and generic-evidence blocker;
2. keep all candidate/source/gate/connector/pipeline mutations behind dry-run,
   affected-object visibility and explicit operator approval;
3. after the generic evidence blocker is closed, prove a minimal controlled V1
   job-review path with Top-5/job-review direction and approval-safe GUI/review
   workflow;
4. only after that, run FREEZE-002 to raise remaining areas toward the >=90%
   target maturity;
5. run REFACTOR-001 before cloud migration, DB-backed outbox, Kafka/event
   backbone, Spark or serious productionization.

## Non-goals

REENTRY-001A does not authorize:

- DB writes or migrations;
- scheduler behavior changes;
- provider/API calls;
- candidate, source, gate, connector or pipeline-state mutation;
- apply, commit, PR or merge by MCP;
- a return of retired NEXT/restart artifacts as steering truth;
- exports, CSV, JSON or Markdown review outputs as pipeline inputs or source of
  truth;
- provider follow-up work as the immediate default path unless a later
  repo-backed decision explicitly selects it.

## Required next-work constraints

The next implementation block must remain narrow enough to preserve the
re-entry decision:

- start with read-only diagnosis or patch planning;
- name the exact blocker being closed;
- cite repository evidence, not chat-state evidence;
- declare affected files before patching;
- avoid database, scheduler, provider and activation side effects unless a
  separate dry-run/apply gate explicitly authorizes them;
- run the project validation configured for patch-readiness before commit;
- keep MCP-specific implementation in the external MCP control-plane project,
  not inside this repository.

## Re-entry status

This repository may resume product-pipeline planning after REENTRY-001A is
merged, but only under the constraints above. The first valid product candidate
is the GENERIC/EXPAND stop-control and generic-evidence blocker. If evidence is
missing, stale or contradictory, the correct state is `needs_inspection`, not an
invented clean continuation.
