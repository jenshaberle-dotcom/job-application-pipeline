# DOC-001E Archive and Deprecation Index

Status: implemented as archive/deprecation index foundation  
Scope: planning and source-analysis historical documentation

## Intent

DOC-001E makes the historical documentation surface explicit without moving or
deleting files.

The project has many planning and source-analysis documents. They are valuable
for traceability, but they must not remain an ambiguous reader path for current
architecture.

## Implemented artifacts

- `scripts/build_documentation_archive_index.py`
- `tests/test_documentation_archive_index.py`
- generated/committed archive indexes under `docs/archive/`

## Boundary

- documentation/indexing only
- no source document moves
- no deletion
- no database access
- no pipeline execution
- no source/connector/scheduler changes

## How to refresh the indexes

```bash
python scripts/build_documentation_archive_index.py
```

Check mode:

```bash
python scripts/build_documentation_archive_index.py --check
```

## Why indexes instead of moves first

DOC-001 should not create a massive file-move diff before the Current Truth layer
is stable. Archive indexes provide a safe intermediate step:

```text
historical docs remain in place
-> active navigation points away from them
-> archive indexes make their historical role explicit
-> later moves/deprecations can be done selectively
```

## Follow-up

Recommended next block:

- DOC-001F: README rewrite or operator runbook, depending on reader-path needs.
