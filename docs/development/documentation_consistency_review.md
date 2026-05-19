# Documentation Consistency Review

## Purpose

This review tracks consistency, completeness, freshness and redundancy across the project documentation after ADR-027.

The goal is not to rewrite all documentation.

The goal is to identify documentation drift and then apply small, reviewable corrections.

## Review Scope

- README.md
- docs/roadmap.md
- docs/adr/
- docs/glossary.md
- docs/data_sources/
- docs/database/tables.md
- docs/diagrams/
- docs/source_evaluation.md
- docs/source_analysis/
- docs/relevance/
- docs/planning/
- docs/observability/
- docs/visualization/

## Review Dimensions

- Consistency: terms are used with the same meaning across documents.
- Completeness: current implemented features are documented in the expected places.
- Freshness: documentation reflects the current repository, schema, scripts and source status.
- Redundancy: duplicated explanations do not contradict each other.
- Boundaries: ADR decisions, source analyses, database docs and diagrams do not blur layer responsibilities.

## Initial Findings

### README.md

- README.md needs a focused freshness review.
- Repository structure, migration list, ADR list, scripts, tests and current source status should be checked against the repository.
- StepStone should be described as limited result-card acquisition, not as a generic planned connector.
- First Canonicalization Layer and Silver Source Value Exploration should be reflected if missing or outdated.

### docs/roadmap.md

- Roadmap should reflect completed StepStone limited connector work.
- Roadmap should include First Canonicalization Layer as completed.
- Roadmap should include Source Value Exploration and Source Target Acquisition Model.
- Future work should distinguish source-target lineage from broader source expansion.

### docs/database/tables.md

- Verify that all current migrations are reflected.
- Verify that silver_jobs canonicalization fields from migration 014 are documented.
- Verify whether silver_processing_decisions is documented as a table.
- Check dashboard view column documentation for duplicate or outdated entries.

### docs/diagrams/

- Architecture diagram should reflect current connectors instead of placeholder-only connector naming.
- Bronze/Silver data model should reflect ingestion run search-term lineage.
- Bronze/Silver data model should reflect job observations and Silver processing decisions if missing.
- Silver canonicalization fields should be considered for diagram representation without overcrowding it.

### docs/source_evaluation.md

- StepStone status should be updated from exploratory candidate to limited defensive discovery source if outdated.
- Greenhouse should be positioned as implemented ATS/company-board source.
- Source value evaluation should align with ADR-026 and the Silver source value exploration script.

### docs/source_analysis/greenhouse.md

- Check whether expected fields and implementation status still read like pre-implementation notes.
- Align with current Greenhouse connector and Silver transformation status.
- Avoid presenting isolated boards as search profiles.

### docs/source_analysis/stepstone.md

- Check for mixed language between planned connector and existing limited result-card connector.
- Ensure defensive boundaries remain explicit: no full crawl, no detail pages, no uncontrolled pagination.
- Align recommended next step with Source Target Lineage and Source Value analysis.

### docs/glossary.md and docs/data_sources/source_capabilities.md

- Ensure Search Profile, Search Term, Source, Source Query, Source Target, Acquisition Mode and Acquisition Policy are clearly separated.
- Avoid making Source Target look like only a connector-contract term.
- Ensure terminology aligns with ADR-015, ADR-022, ADR-023, ADR-026 and ADR-027.

### docs/visualization/dashboard_vision.md

- Check whether existing views are still described as future views.
- Align dashboard vision with current lifecycle, source heartbeat, source value and Silver processing documentation.

## Patch Plan

### Patch A1: README and Roadmap

- Update only stale status and structure sections.
- Avoid large README rewrite.
- Keep current writing style where possible.

### Patch A2: Database Tables and Diagrams

- Align tables.md with current schema and migrations.
- Update diagrams carefully without overcrowding them.

### Patch A3: Source Evaluation and Source Analyses

- Align Greenhouse and StepStone status.
- Align Source Evaluation with current source roles and acquisition boundaries.

### Patch A4: Terminology and Redundancy Pass

- Review glossary, source capabilities and connector contract together.
- Remove or clarify redundant wording only where it creates ambiguity.

## Review Rule

ADRs should not be rewritten historically unless they contain a hard inconsistency.

Current-state documentation such as README.md, roadmap, database docs, diagrams and source analyses should carry the latest operational truth.

