# Documentation Consistency Review

## Purpose

This document defines how documentation consistency reviews are performed in this project.

A documentation review is not only a textual consistency pass.

A documentation review is an executable validation against the current repository and, where relevant, the current local database state.

The goal is to keep documentation:

- current
- correct
- linked
- non-redundant
- useful

The guiding principle is:

> as extensive as necessary, as small as possible

## Review Scope

A full documentation review may include:

- `README.md`
- `docs/roadmap.md`
- `docs/adr/`
- `docs/glossary.md`
- `docs/data_sources/`
- `docs/database/tables.md`
- `docs/diagrams/`
- `docs/source_evaluation.md`
- `docs/source_analysis/`
- `docs/relevance/`
- `docs/planning/`
- `docs/observability/`
- `docs/visualization/`

The review should not create new documents unless the existing structure cannot hold the information cleanly.

## Review Dimensions

| Dimension | Review question |
|---|---|
| Consistency | Are terms used with the same meaning across documents? |
| Completeness | Are implemented features documented in the expected places? |
| Freshness | Does documentation reflect current repository, schema, scripts and source status? |
| Correctness | Are commands, profile names, migrations, tables and diagrams factually correct? |
| Links | Are ADRs, source analyses and capability documents connected where needed? |
| Redundancy | Do duplicated explanations create contradictions or unnecessary maintenance burden? |
| Boundaries | Are Bronze, Silver, Gold, connector and source-evaluation responsibilities kept separate? |

## Executable Validation

Documentation claims should be validated with commands whenever feasible.

Typical checks:

- `git status --short`
- `git diff --check`
- `python -m compileall scripts src`
- `pytest`
- `find docs -maxdepth ...`
- `grep -RIn ...`
- database introspection through `psql`
- source-specific scripts such as `show_ingestion_run_summary` or `explore_silver_source_value`

Examples of claims that should be validated instead of guessed:

- migration numbers and file names
- current connector files
- available scripts
- active search profiles
- database tables and columns
- implemented source families and source targets
- Mermaid diagram field names
- README example commands

## ADR Rule

ADRs record decisions at the time they were made.

Historical ADRs should not be rewritten just because the project has advanced.

Exceptions:

- hard factual errors
- broken links
- terminology that contradicts a later accepted ADR and would mislead readers

Current-state documents such as README, roadmap, database docs, diagrams, source analyses and source evaluation pages carry the latest operational truth.

## Source Terminology Rule

Source documentation must distinguish:

- search profile
- search term
- source family
- source target
- source type
- source capability
- acquisition mode
- acquisition policy

This is required by ADR-027 and ADR-028.

Compound operational values such as `greenhouse:stripe` or `personio:eraneos` may remain valid short-term identifiers, but documentation must not treat them as the final analytical model.

## Documentation Structure Rule

The documentation tree should stay compact.

A new document or directory is justified only when it:

- has a clear owner topic
- avoids overloading an existing page
- will remain useful beyond one implementation step
- reduces confusion more than it adds navigation cost

Short-lived notes should usually be folded into an existing source analysis, roadmap, ADR or development document.

## Current Review Baseline

The current review baseline after ADR-028 and ingestion diagnostics work is:

- README and roadmap reflect the current implemented source and diagnostics status.
- Database and diagram docs include persisted ingestion failure diagnostics.
- Source terminology is aligned with source family, source target and source type separation.
- Personio is documented as technically integrated but still pending source-value validation.
- StepStone is documented as a limited defensive discovery and aggregator source, not a preferred canonical source.
- Future source health work should build on ADR-028 instead of relying only on compound `source_name` values.

## Open Review Focus

Future reviews should pay special attention to:

- whether Personio Batch 1 results justify further expansion
- whether Greenhouse expansion remains source-target based
- whether direct employer sources require explicit source-target metadata before scaling
- whether Gold/dashboard documentation reflects the actual implemented views
- whether source health metrics separate source family, source target and source type
