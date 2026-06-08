# ADR-022: Define shared source and layer terminology

## Status

Accepted

## Context

The project ingests job data from multiple external sources. These sources differ in technical access patterns, HTML or API structures, naming conventions, identifiers and available fields.

Without a shared terminology, each connector and source analysis could accidentally introduce its own vocabulary. That would make the project harder to reason about, especially once Bronze, Silver and Gold layers are built on top of heterogeneous sources.

The project therefore needs one common vocabulary for architectural concepts, while still allowing source-specific details to be documented precisely.

## Decision

The project will use a shared source and layer terminology across documentation, source analyses, connector design and later transformation logic.

Source-specific differences must be represented as mappings, capabilities or source-specific metadata. They must not create separate project vocabularies per source.

The following terms are canonical for the project:

| Term | Meaning |
|---|---|
| Source | External system or website family that can provide job data. |
| Connector | Project code responsible for accessing one source and converting source data into project records. |
| Search intent | Source-independent description of what the project wants to find, for example role keywords and location. |
| Source query | Source-specific translation of a search intent into URL parameters, API parameters or form inputs. |
| Source capability | Documented property of a source, for example search support, stable identifiers, pagination or detail availability. |
| Raw source payload | Source-preserving response material, for example HTML, JSON or text received from a source. |
| Result card | One search-result item shown by a source before opening a detail page. |
| Detail page | Source page or endpoint containing a fuller job description. |
| External job ID | Identifier assigned by the source or extracted from source URLs or source markup. |
| Bronze record | Persisted source-preserving record, including provenance and raw/source-specific payload. |
| Canonical job | Source-independent Silver-layer representation of a job posting. |
| Source-specific metadata | Fields that are useful but not part of the canonical model. |

Layer terminology rules:

- **Bronze** keeps source provenance and source-specific payloads. Source-specific names are allowed there if they are clearly marked as source fields.
- **Silver** uses canonical project terminology. Source-specific values must be mapped into canonical fields or stored in source-specific metadata.
- **Gold** uses business-facing terms and must not depend on source-specific selectors, HTML structures or provider vocabulary.
- **Documentation** must distinguish observed source signals from project-level canonical fields.

## Later Terminology Extension

ADR-027 extends the shared terminology with `Source target`, `Acquisition mode` and `Acquisition policy`.

This does not replace the terminology defined here.

It adds acquisition-lineage concepts needed for ATS boards, company career pages and controlled discovery sources.

## Consequences

This creates a stable language for future connectors and transformations.

Commercial portals such as StepStone can still have dedicated source analyses, but those analyses must describe how source-specific observations map to the shared project vocabulary.

Python probe scripts may still use exploratory variable names while a source is under evaluation. Once a probe becomes connector logic, names should align with this terminology.

## Alternatives Considered

### Separate terminology per source

Rejected. It would preserve source nuance but would make cross-source comparison, deduplication and Silver-layer design harder.

### Normalize everything immediately in Bronze

Rejected. Bronze should preserve source evidence and raw/source-specific context. Premature normalization belongs in Silver, not Bronze.

### Delay terminology decisions until Silver implementation

Rejected. The project is already evaluating complex sources. Naming decisions made now influence scripts, documentation and architecture.
