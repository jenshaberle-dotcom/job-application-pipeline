# Finanz Informatik Incremental Uniqueness Review — S2L

## Purpose

S2L checks whether the bounded Finanz Informatik connector-candidate preview adds incremental source value compared with existing raw and Silver evidence.

This is a read-only review. It does not write to the database, activate a source target or approve a connector.

## Why This Matters

Employer-origin sources should not be evaluated mainly by volume.

BA remains the broad-volume source so far. Employer-origin sources are precision sources: even one relevant, non-duplicate candidate can be valuable if it adds a job not already visible through BA, StepStone, Greenhouse or existing Silver evidence.

## Workflow

Set DB environment variables and run:

    python -m scripts.review_finanz_informatik_incremental_uniqueness

The review builds its candidate set from the bounded Finanz Informatik connector-candidate preview and checks it against current database evidence.

The review writes artifacts to:

    exports/s2l_finanz_informatik_incremental_uniqueness_review/

## Outputs

- `finanz_informatik_incremental_uniqueness_review.md`
- `finanz_informatik_incremental_uniqueness_manifest.json`

## Interpretation

Possible decisions:

- `incrementally_unique_candidate`: no sufficiently similar raw or Silver evidence found
- `possible_known_elsewhere_review`: some overlap exists; manual review needed
- `likely_known_elsewhere`: title and evidence overlap are high
- `known_exact_url_match`: the same URL is already known
- `manual_review_db_unavailable`: the database could not be checked

## Boundary

S2L does not approve Bronze persistence or connector activation.

It only answers whether the bounded Finanz Informatik connector-candidate preview appears to add incremental source value.
