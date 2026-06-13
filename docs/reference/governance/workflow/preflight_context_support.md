# Preflight Context Support

Status: implemented foundation

## Purpose

Preflight context bundles are review artifacts only. They are used to move
current repo/report context between chats without turning exports, JSON, CSV, or
ZIP files into pipeline inputs.

## Fixed failure modes

- Relative paths are resolved under the repository root before calling
  `relative_to`, avoiding pathlib errors when relative paths are compared with an
  absolute repo root.
- Read-only DB diagnostic helpers isolate query failures by rolling back after a
  failed query before the next query is executed.
- Paths outside the repository are skipped instead of being archived.

## Boundaries

- No pipeline mutation.
- No database writes.
- No candidate creation or gate decision.
- No connector activation.
- No CSV/export artifact becomes an input.
