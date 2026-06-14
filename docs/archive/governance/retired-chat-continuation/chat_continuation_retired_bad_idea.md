# Retired Chat-Continuation Anti-Pattern

Status: Archived / Retired / Do Not Use
Decision owner: CONSISTENCY-001A
Project status: bad idea, explicitly retired

## Decision

The former generated chat-continuation mechanism is fully retired.

It must not be used, repaired, reintroduced, renamed, or treated as a project
steering mechanism again.

This includes the former generated restart bundle flow, generated continuation
bundles, contract validation for those bundles, NEXT-based chat restart
steering, and freeze-exit gates that relied on generated restart freshness.

## Why this is archived as a bad idea

The mechanism created a false sense of state continuity. Generated artifacts
claimed repository truth that was incomplete, stale, or contradicted by the
actual repository. The result was repeated repair loops, context-load growth,
wrong next-work steering, and loss of operator trust.

The root lesson is not "make better generated restart bundles". The root lesson is:

> Do not use generated chat-continuation artifacts as project truth.

## What is prohibited

- Creating generated continuation bundles as project truth.
- Using generated state summaries as next-work steering.
- Treating NEXT reports as current work selection.
- Treating exports as restart truth.
- Treating assistant memory or chat summaries as repository truth.
- Rebuilding the same mechanism under a different name.

## What replaces it

Until the external MCP / Engineering Agent Control Plane reaches sufficient
maturity, project continuation uses a fresh full-repository ZIP plus direct
repository inspection.

After MCP maturity is demonstrated, MCP-backed repo/DB state inspection
replaces the temporary full-ZIP bridge.

Generated chat-continuation artifacts do not return.

## Historical artifacts

Legacy files were moved here as non-executable historical evidence only. They
are not active workflow documentation, not validation targets, not project
truth and not implementation templates.
