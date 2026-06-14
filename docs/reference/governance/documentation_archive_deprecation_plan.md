# Documentation Archive and Deprecation Plan

Status: DOC-001B current plan  
Scope: archive/deprecation rules for documentation rebaseline

## Intent

DOC-001 should reduce confusion, not preserve every artifact in the active reader
path.

This plan defines how to treat documents that are valuable historically but
misleading as current architecture documentation.

## Inventory basis

DOC-001A found a large documentation surface:

- 193 markdown files in the inventory,
- 191 markdown files under `docs/`,
- 34 ADR files,
- 22 planning docs,
- 87 source-analysis docs,
- 109 archive/historical candidates,
- 24 current-truth candidates.

This is too large for a coherent active documentation path.

## Default decisions

### Keep as Current Truth candidate

Keep only a small set of documents as the active reader path:

- README,
- current system overview,
- system diagrams,
- pipeline state machine,
- governance entry points,
- agent governance registry,
- capability audit matrix,
- drift guard and documentation rebaseline strategy,
- operator runbook once created,
- glossary after cleanup.

### Keep as Reference candidate

Keep technical details that are useful but not narrative entry points:

- database table documentation,
- source capability contracts,
- connector/search contracts,
- security and design baselines,
- observability references,
- relevance/classification references.

### Deprecate or archive by default

Treat these as historical unless explicitly promoted:

- `docs/archive/planning/*`,
- `docs/archive/source-analysis/*`,
- old source-specific review documents,
- old connector candidate narratives,
- old MVP/spike documents,
- old retired restart/project-state artifacts.

## Archive/deprecation options

DOC-001 can use one or more of these approaches:

### Option A: Status headers only

Add clear status headers such as:

```text
Status: historical build note
Current truth: see docs/current/architecture.md
```

Pros: low-risk, little churn.  
Cons: many files remain in the visible tree.

### Option B: Archive index

Create an archive index that lists historical docs by topic and status.

Pros: improves navigation without many file moves.  
Cons: old docs still exist in their current directories.

### Option C: Move to archive directory

Move historical docs under an archive area.

Pros: strongest signal to readers.  
Cons: large git diff and link churn.

### Recommended sequence

1. Add status/indexing first.
2. Rebuild Current Truth docs.
3. Move only the most misleading or redundant docs later.
4. Avoid a mass-move PR before the new architecture docs are stable.

## Hard rule

Do not patch obsolete docs into a hybrid narrative.

If a document describes a previous architecture, mark it historical or rewrite it
from current truth. Do not make it half-old and half-current.

## What must not happen

- `exports/project_state/` must not become active architecture documentation.
- `exports/` must not become documentation source of truth.
- Planning docs must not be linked as the main explanation of current behavior.
- Source-analysis docs must not be the first reader path for system architecture.

## DOC-001B outcome

This plan authorizes later DOC-001 blocks to:

- deprecate obsolete documents,
- replace outdated architecture documents,
- consolidate navigation,
- reduce the active documentation set,
- create an archive index,
- move files only after a clear Current Truth layer exists.
