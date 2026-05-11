# ADR-016: Define ingestion scope and relevance boundaries

## Status

Accepted

## Context

The project ingests job postings from heterogeneous real-world sources.

Different sources expose different technical capabilities:

- some sources support keyword, location and radius search server-side
- some sources expose complete company job boards
- some sources may only allow broad fetches followed by local filtering

This creates an important architectural distinction.

Technical fetch capability does not automatically define which data should be stored, normalized or analyzed.

For example, a Greenhouse board may expose all jobs of a company. Fetching all jobs may be technically possible, but not all jobs are relevant for a personal job market intelligence platform focused on Data Engineering, analytics, platform engineering and related roles.

The project therefore needs explicit boundaries between:

- source fetch capability
- ingestion scope
- relevance filtering
- downstream scoring

## Decision

The project distinguishes between three conceptual stages.

### 1. Ingestion Scope

The ingestion scope defines which jobs are allowed to enter the Bronze layer.

Bronze is not intended to store every job technically available from every possible source.

Bronze stores raw jobs captured within a defined search or observation scope.

Valid scope examples:

- regional jobs around Hannover
- remote-friendly jobs relevant to the target profile
- selected strategic companies
- selected source-specific search profiles
- selected role or skill clusters

### 2. Relevance Filtering

Relevance filtering decides which Bronze records are eligible for Silver normalization.

Silver should not simply normalize every raw record.

Silver should contain canonicalized jobs that are potentially relevant for downstream analysis.

Relevance can be based on:

- job title
- description content
- skill clusters
- role families
- location or remote policy
- source-specific metadata

### 3. Gold Scoring

Gold scoring will later rank and enrich relevant Silver records.

Gold may evaluate:

- fit to personal requirements
- CV match
- skill match
- seniority fit
- location or remote fit
- company or industry relevance
- duplicate candidates across sources

## Design Rules

Bronze may be broad, but must not be unbounded.

Silver must be relevant enough for downstream analysis.

Gold is responsible for ranking, scoring and recommendations.

The project should avoid treating full-fetch sources as automatically relevant sources.

A full-board fetch is a technical fetch strategy, not a business definition of relevance.

## Consequences

The pipeline can ingest heterogeneous sources without flooding Silver and Gold with irrelevant records.

Full-fetch sources such as Greenhouse can still be supported, but require explicit scope or relevance handling.

Future source onboarding must define:

- why the source is in scope
- how broad the fetch may be
- which filters are applied server-side
- which filters are applied locally
- which records are eligible for Silver

This keeps the project suitable as a production-oriented showcase instead of becoming an uncontrolled scraping archive.
