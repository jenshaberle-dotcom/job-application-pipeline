# DOC-001C Active Documentation Navigation

Status: implemented as reader-path rebaseline
Scope: documentation entry points and historical-directory declassification

## Intent

DOC-001C starts the real documentation restructure without moving files yet.

It does not try to repair every old document. Instead, it makes the active reader
path explicit and marks planning/source-analysis areas as historical by default.

## Implemented artifacts

- `docs/README.md`
- `docs/architecture/README.md`
- `docs/reference/governance/README.md`
- `docs/archive/planning/README.md`
- `docs/archive/source-analysis/README.md`

## Why this is not flickwork

This block avoids editing dozens of outdated documents in place.

Instead, it changes the navigation model:

```text
Current Truth entry points first
Historical directories clearly marked
Old docs not deleted or rewritten yet
```

That allows the later large rewrite/archive work to happen from a clean reader
model.

## Boundary

- documentation only
- no file moves
- no deletion
- no database access
- no pipeline execution
- no source/connector/scheduler changes

## Follow-up

Recommended next DOC-001 blocks:

1. DOC-001D: ADR status table.
2. DOC-001E: archive/deprecation index for planning/source-analysis docs.
3. DOC-001F: README rewrite.
4. DOC-001G: replace older architecture docs with the new Current Truth structure.
