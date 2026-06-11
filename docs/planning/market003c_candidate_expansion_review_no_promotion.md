# MARKET-003C Candidate Expansion Review without Automatic Promotion

Status: planned implementation block
Scope: Search Intelligence / external market observation review

## Purpose

MARKET-003C turns manually anchored market evidence into a reviewable candidate-expansion surface without promoting anything automatically.

It exists because MARKET-003A/B made manual market observations persistent enough to be useful, but those observations must not become employer-origin candidates by default.

## Boundary

This block is review-only.

It must not:

- create rows in `employer_origin_source_candidates`
- write candidate-expansion or candidate-promotion decisions
- write gate decisions
- activate connectors
- mutate Bronze, Silver or Gold
- change scheduler state
- treat local exports as pipeline input

Recommendations produced by the report are review prompts only.

## Implemented Shape

The block adds:

    python scripts/run_market003c_candidate_expansion_review.py

The script reads market evidence and known employer-origin candidates from the database through a read-only Docker/psql query and writes export artifacts under:

    exports/market003c_candidate_expansion_review/

Expected outputs:

- `market003c_candidate_expansion_review.json`
- `market003c_candidate_expansion_review_items.csv`
- `market003c_candidate_expansion_review.md`

## Classification

The report classifies evidence into review states such as:

- `known_candidate_review_context_only`
- `manual_review_required_manual_market_signal`
- `manual_review_required_evidence_rich_market_signal`
- `insufficient_evidence_review_context_only`
- `insufficient_evidence_missing_company`

The classifications deliberately avoid names like `create_candidate_recommended` because the block is not an automatic promotion workflow.

## Interpretation Boundary

A `manual_review_required_*` item means:

> This market evidence is worth looking at as a possible future candidate.

It does not mean:

> Create a candidate, pass a gate, build a connector, register a source, or run ingestion.

## Next Step

After reviewing the report, a later explicitly approved block may add a human-confirmed promotion workflow. That future workflow must be separate and must preserve auditability.
