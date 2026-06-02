# S7L Origin Source URL Assignment Policy

## Purpose

S7L reduces approval noise in the employer-origin pipeline. A human should not
have to approve every harmless technical URL assignment when the system already
has strong, persisted URL evidence. The gate may therefore set
`employer_origin_source_candidates.candidate_url` automatically for low-risk,
public HTTPS, career-like origin URLs.

## What May Be Automatic

The system may auto-assign only the origin URL field when all conditions hold:

- the URL is already persisted as evidence in the database
- the normalized URL uses HTTPS
- the host is public, not local/private
- the domain is not a known aggregator domain
- the path looks career/job related
- the selected source type is employer-origin career-site compatible
- the confidence score is at least `0.80`
- there is no conflicting existing candidate URL

This is not a source approval. It only records technical evidence.

## What Still Requires Approval

Manual approval remains required for decisions that change system behavior or
business meaning:

1. promote noisy/ambiguous market observations into candidates
2. accept ambiguous or weak origin URL evidence
3. approve connector artifact generation
4. register connector code
5. activate recurring ingestion

## Why This Avoids Approval Hell

The chain should not replace manual job search with manual pipeline clicking.
Technical evidence can move automatically when it is safe and explainable.
Human approval is reserved for meaningful risk: unclear source identity,
ambiguous candidate value, connector build, registration and activation.

## Boundary

S7L still does not browse the web, register connectors, activate sources, write
Bronze data, change scheduler state or use CSV/Excel as pipeline inputs.
