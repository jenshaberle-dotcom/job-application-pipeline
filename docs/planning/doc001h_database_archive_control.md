# DOC-001H Database and Archive Control Surface

Status: implemented documentation build log
Scope: database schema map, relationship overview, docs-path archive triage

## Intent

DOC-001H answers two documentation gaps left visible after the architecture
diagram rebaseline:

1. The repository had architecture diagrams, but no current high-level map of the
   database table/view network behind Search Intelligence.
2. The docs tree still looked chaotic because historical content had been indexed
   but not yet physically archived or clearly triaged by path.

## Implemented changes

- Added `docs/database/README.md` as the database documentation entry point.
- Added `docs/database/schema_overview.md` with domain-level table/view grouping.
- Added `docs/database/schema_relationships.md` with Mermaid relationship maps.
- Marked `docs/database/tables.md` as useful but incomplete for the current
  Search Intelligence schema.
- Added `docs/archive/documentation_path_status.md` to classify docs directories
  as Current Truth, Reference, Historical or Archive Candidate.
- Updated documentation navigation to point to the database schema map and archive
  triage surface.
- Added regression tests that protect the new database/archive documentation
  surfaces.

## Important decision

DOC-001H does not mass-move old documentation yet.

That is deliberate. A mass archive move should happen only after a link/reference
check exists, because old planning and source-analysis files are heavily
interlinked with historical handovers and some existing contract tests.

## Next recommended block

DOC-001I should perform a first physical archive pass on the small
`docs/archive/diagrams/` directory after DOC-001I, because current replacement diagrams now exist in
`docs/architecture/system_diagrams.md` and database relationship diagrams now
exist in `docs/database/schema_relationships.md`.

After that, a generated link/reference check should precede any large
`docs/planning/` or `docs/source_analysis/` moves.
