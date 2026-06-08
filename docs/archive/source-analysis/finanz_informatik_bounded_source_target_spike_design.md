# Finanz Informatik Bounded Source-Target Spike Design

## Status

Historical design record.

This document explains the reasoning that led to the bounded Finanz Informatik source-target exploration. The executable S2J/S2K spike scripts were retired in S2O-A1 because the project now has a cleaner connector-preview-backed and DB-backed path.

## Original Purpose

The original design existed to avoid repeating the Greenhouse mistake of broad, weakly differentiated ingestion.

The intended source behavior was:

- inspect only a small employer-origin target
- avoid broad crawling
- avoid Bronze persistence until source value was demonstrated
- prefer strict request boundaries and stop conditions
- apply relevance gates before any connector activation decision

Those principles remain valid.

## Superseding Implementation Path

The active implementation path is now:

- `src/connectors/finanz_informatik.py`
- `scripts.review_finanz_informatik_incremental_uniqueness`
- `scripts.review_finanz_informatik_activation_gate`

This path builds candidates from bounded connector-preview logic and compares them against current database evidence.

Generated review artifacts are outputs only. They must not become hidden pipeline inputs, activation gates, destructive-operation inputs or cloud/CI dependencies.

## Source Scope Rules Preserved

The Finanz Informatik source remains a precision-source candidate, not a broad-volume source.

The preserved scope rules are:

- one bounded listing target
- limited detail-page fetching
- target scope: Hannover or credible remote/Germany-wide signal
- exclude training, dual-study, working-student, internship and trainee paths from activation candidates
- treat a small number of relevant, incrementally unique jobs as valuable source evidence
- do not approve recurring ingestion from spike evidence alone

## Current Decision Boundary

Finanz Informatik may move only through controlled inactive preview or explicitly reviewed source-target activation.

Broad recurring ingestion remains out of scope until a later decision explicitly approves it.
