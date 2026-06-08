# Origin Source Discovery Agent v1

## Purpose

The Origin Source Discovery Agent v1 is a read-only foundation for finding plausible employer-origin career/job URLs for newly promoted employer-origin candidates.

It exists because the older URL recovery helper could accept any reachable career-like URL. In validation, that behavior would have selected `https://jobs.hannover.de/` for `Hannover Rück SE`, which is likely a city/region job portal rather than the employer origin source.

## Design decision

The new agent treats reachability as necessary but not sufficient.

A URL can only be selected when it is:

- HTTPS and public
- not a known aggregator domain
- career/job-like
- plausibly matched to the company identity
- scored above the automatic selection threshold

If the URL is reachable but the company identity match is weak, the agent must reject it or require manual review.

## Boundary

The v1 agent is read-only:

- no candidate URL write
- no connector registration
- no source activation
- no Bronze/Silver write
- no scheduler change
- no automatic connector build

## Provider model

The initial implementation uses generated company-domain candidates and existing market-evidence context. It is intentionally prepared for later search-backed providers, but the first version does not require external API keys, paid services, or new secrets.

Potential future providers:

- official search API provider
- manually curated URL candidate provider
- market-evidence URL provider
- known ATS/provider pattern provider

## Validation targets

The first benchmark set should include the nine EO-002A3 candidates promoted from market evidence:

- Technische Informationsbibliothek (TIB)
- ivv GmbH
- WERTGARANTIE Group
- Genoverband e.V.
- x1F GmbH
- Materna Information & Communications SE
- msg systems ag
- Hannover Rück SE
- E.ON Grid Solutions GmbH

Success does not require selecting a URL for every candidate. A correct `manual_review_required` or `not_found` is better than a false positive candidate URL.
