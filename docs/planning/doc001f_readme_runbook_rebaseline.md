# DOC-001F README and Runbook Rebaseline

Status: implemented as current entry-point rewrite
Scope: root README and operator runbook

## Intent

DOC-001F performs a visible documentation rewrite instead of continuing to add
only plans and indexes.

It updates the public repository entry point and creates a current operator
runbook so that readers and operators do not have to infer the current project
from historical planning/source-analysis notes.

## Implemented artifacts

- `README.md`
- `docs/operations/runbook.md`

## Boundary

- documentation only
- no code changes
- no database access
- no pipeline execution
- no source/connector/scheduler changes
- no file moves
- no historical-doc rewrites

## Why this comes after DOC-001A-E

The repository first needed:

1. documentation inventory,
2. Current Truth map,
3. active documentation navigation,
4. ADR status table,
5. archive/deprecation index.

Only after those pieces existed could the root README be rewritten without
creating another hybrid narrative.

## Follow-up

Recommended next blocks:

1. DOC-001G architecture consolidation: reconcile older architecture docs with
   `current_system_overview.md` and `system_diagrams.md`.
2. DOC-001H ADR status classification pass.
3. DOC-001I selective archive/deprecation markers for the most misleading old docs.
