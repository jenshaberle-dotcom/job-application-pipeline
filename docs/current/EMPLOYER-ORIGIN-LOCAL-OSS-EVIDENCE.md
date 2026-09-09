# Employer-Origin local OSS evidence boundary

## Product rule

JAP owns and controls Employer-Origin source discovery, search semantics, evidence
projection, admission gates, persistence, relevance, and product decisions.
Third-party extraction services are not a product dependency or source of truth.

Reusable open-source libraries may be used as replaceable local parsing
capabilities when all of the following remain true:

- no purchase price or per-use fee is required;
- extraction runs locally inside JAP-controlled Python execution;
- the library license permits integration and redistribution under the project's
  intended use;
- no remote extraction API, hosted account, API key, or provider availability is
  required at runtime;
- JAP's own normalized evidence contract remains the boundary presented to the
  rest of the pipeline.

## Current local capabilities

### extruct 0.18.0

- Purpose: generic extraction of embedded schema.org metadata from HTML.
- Used syntaxes: JSON-LD and Microdata.
- License: BSD License.
- Product role: replaceable parser only; no admission authority.

### Trafilatura 2.2.0

- Purpose: bounded main-text fallback when structured JobPosting description
  evidence is absent.
- License: Apache-2.0.
- Product role: replaceable parser only; no admission authority.

`selectolax` was evaluated but is not added at this stage because it would be a
second generic HTML parser without adding a distinct evidence capability beyond
the current extruct + Trafilatura composition. It can be reconsidered if a
measured parser-performance or robustness residual justifies it.

## Content and access boundary

The generic layer operates only on job-detail responses already reached through
JAP's authorized public Employer-Origin acquisition/search path.

It must not:

- bypass login, paywall, CAPTCHA, robots enforcement, or other technical access
  controls;
- guess hidden authenticated endpoints;
- turn a third-party hosted extractor into a required runtime service;
- persist source HTML as the normalized evidence record.

The current normalized evidence contract stores structured facts plus at most a
bounded text excerpt for downstream processing. The source URL remains the
reference for the original posting. This reduces unnecessary copying while
preserving enough local evidence to test the existing Bronze/Silver path.

## Current sequencing boundary

This layer is intentionally generic and employer-neutral. No company key, portal
hostname, or one-off employer rule may change extraction semantics.

The current E2E sequence remains:

`query-proven search -> generic detail evidence -> existing Bronze -> existing Silver -> downstream product path`

Existing relevance thresholds are not relaxed merely because richer evidence is
now available. The stage funnel must first measure what changes and why.
