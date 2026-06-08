# DOC-001J Link/Reference Check Before Larger Archive Moves

Status: completed documentation-safety block

## Purpose

DOC-001I physically archived only the old diagram pages. DOC-001J adds the
missing safety net before any larger physical movement of planning or
source-analysis documents.

The goal is not to make every historical document current. The goal is to avoid
silent documentation breakage while the project continues to reduce the active
Current Truth surface.

## Implemented guard

DOC-001J adds:

- `scripts/check_documentation_references.py`
- `tests/test_doc001j_documentation_reference_check.py`

The guard checks Markdown documentation for two different surfaces:

1. local Markdown links such as `../design/README.md`, and
2. repository-path references in prose/backticks such as
   `docs/architecture/system_diagrams.md`.

A reference passes when it resolves to an existing repository path or when it is
explicitly classified as an intentional retired/planned path.

## Intentional non-existing references

The following non-existing references are allowed because they are archive and
migration control language, not active navigation:

- `docs/diagrams/`
- `docs/diagrams/architecture.md`
- `docs/diagrams/bronze_data_model.md`
- `docs/archive/planning/`
- `docs/archive/source_analysis/`

Old `docs/diagrams/` references are allowed only as historical source paths in
DOC-001I archive mapping. Current replacements are:

- `docs/architecture/system_diagrams.md`
- `docs/database/schema_relationships.md`

The planned archive directories are allowed only as future physical archive
targets. They do not exist yet.

## Cleanup included

DOC-001J also removes two stale source-analysis path references from
`docs/source_analysis/aggregator_discovery_assessment.md`:

- an uncreated discovery-log file path was converted to an explicit optional
  future artifact description,
- the employer-origin review reference was corrected to the existing
  `docs/source_analysis/employer_origin_source_candidate_review.md` file.

This keeps the historical document useful without pretending uncreated files are
active documentation.

## Operator command

```bash
python scripts/check_documentation_references.py --write-report --json
```

A successful run has `status=pass` and `unresolved_count=0`. The report is a
human-readable export only; it must not become a pipeline input or architecture
source of truth.

## Archive move rule after DOC-001J

Before moving larger `docs/planning/` or `docs/source_analysis/` batches:

1. run the reference check,
2. fix any unresolved references or classify them explicitly,
3. update navigation/index pages,
4. run targeted DOC tests,
5. run full `pytest -q` before commit/PR.

No mass archive move should happen without this guard staying green.
