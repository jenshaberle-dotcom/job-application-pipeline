# ADR-016: Use source-aware Silver transformations

## Status

Accepted

## Context

The project now ingests heterogeneous Bronze job payloads from multiple source types.

Current implemented sources:
- Bundesagentur für Arbeit
- Greenhouse ATS boards

These sources expose significantly different payload structures and field naming conventions.

Examples:
- Bundesagentur uses German API field names
- Greenhouse uses ATS-oriented payload structures
- field completeness differs between sources

A single generic transformation layer would either:
- hide source-specific assumptions
- or become increasingly difficult to maintain

## Decision

The Silver layer uses source-aware transformation logic.

Each supported source type can provide dedicated transformation logic into the shared canonical `silver_jobs` model.

The current implementation intentionally keeps this lightweight through:
- source-specific transformation functions
- a small dispatcher in `transformer.py`

The project intentionally avoids premature framework-style abstraction while the number of sources remains small.

## Consequences

Bronze payloads remain source-preserving and heterogeneous.

Silver normalization becomes the explicit canonicalization boundary.

Source onboarding can evolve incrementally while preserving maintainability and reviewability.

The current implementation may later evolve into modular transformer structures if the number of heterogeneous sources increases significantly.
