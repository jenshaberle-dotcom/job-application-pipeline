# F1 — Company -> Official Origin Jobspace Discovery — research/adoption note

Status: active research baseline for freeze package F1

Branch: `agent/f1-origin-jobspace-discovery`

## Goal

Given a company identity, resolve the official company domain and official careers/jobspace, fingerprint the ATS/portal when possible, and hand the resulting candidate into the existing generic Employer-Origin proof layer.

The production path must remain local, deterministic, inspectable and replaceable. No hosted service becomes source-validity or runtime authority.

## Existing JAP capability — do not rebuild

`src/search_intelligence/origin_source_discovery_agent.py` already provides most of the selection machinery:

- deterministic company-token domain candidates;
- bounded common career/job paths;
- job/career subdomain candidates;
- search-result candidates with context evidence;
- market-evidence candidates;
- redirect-aware HTTP probe results;
- company identity scoring;
- career-signal scoring;
- known ATS/provider host recognition;
- fail-closed aggregator rejection;
- automatic selection / manual-review / reject decisions.

Therefore F1 should extend evidence generation/fingerprinting around this agent rather than introduce a second discovery engine.

Current generic weakness: several historical `CORPORATE_IDENTITY_ALIASES` exist for individual companies. They are useful compatibility evidence but must not become the scaling mechanism. F1 should make new companies work without adding entries to that table.

## External/open research findings

### 1. Wikidata official website data

Wikidata property `P856` is `official website` and Wikidata structured data is CC0. This is potentially useful as an optional company-name -> official-site evidence provider or as material for a locally derived/cacheable dataset.

Important limitation: Wikidata can contain multiple, former or language-specific official URLs. A P856 result is evidence, not automatic Employer-Origin authority. JAP still needs company-identity validation and normal source proof.

Potential adoption:

- optional evidence provider;
- cache/download can be local and replaceable;
- never make live Wikidata availability a required runtime dependency.

### 2. `ats-jobs`

Open-source Node library `shunsukefuruyama/ats-jobs` supports public feeds for twelve ATS families including Greenhouse, Workday, Ashby, Lever, SmartRecruiters, Rippling, Workable, Recruitee, BambooHR, Breezy, Teamtailor and Personio. Its domain mode probes ATS providers and returns the detected provider/slug/jobs. The project advertises no runtime dependencies beyond Node itself.

Potential adoption:

- reference implementation for ATS host/endpoint fingerprint rules;
- source of test vectors and endpoint shapes;
- do not add Node/library runtime dependency merely to call it; port small deterministic fingerprints into JAP unless direct library adoption has a clear maintenance advantage.

### 3. CareerScout

`Ramcharan747/careerscout` uses a concept close to JAP F1: probe bounded common careers paths, inspect `href`/`src`/`action` attributes for ATS indicators, then use schema-driven ATS parsing. It covers more ATS families and documents Workday discovery techniques.

Potential adoption:

- reuse the architectural idea of attribute-bound ATS fingerprinting instead of matching arbitrary page text;
- extend JAP `OriginDiscoveryProbeResult` with bounded discovered links/provider fingerprints;
- avoid wholesale dependency/adoption unless necessary.

### 4. Public ATS endpoint references

`ConorsCode/ats-api-reference` documents and recently re-verifies public unauthenticated job-board endpoints for Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Workable, Recruitee, Personio and BambooHR. Other open references cover similar endpoint shapes.

Potential adoption:

- deterministic endpoint registry after an ATS/slug/tenant is evidenced;
- useful structured path before generic HTML scraping;
- endpoints must still be verified against real companies and fail closed on redirects/marketing pages/empty false positives.

## F1 implementation direction

### Layer A — company-domain evidence

Produce bounded `official_domain_candidate` evidence from, in priority order where available:

1. already persisted exact company website/domain evidence in JAP;
2. optional open-data evidence such as Wikidata P856;
3. bounded search-result evidence already supported by JAP;
4. deterministic token/domain generation fallback.

Every candidate remains subject to JAP company-identity scoring. Open-data/search evidence never bypasses proof.

### Layer B — careers/jobspace discovery

For a validated company domain:

- probe bounded common career paths and job/career subdomains;
- inspect redirects;
- inspect only URL-bearing HTML attributes (`href`, `src`, `action`) plus structured metadata for ATS/jobspace links;
- preserve final URL and canonical-link evidence when present;
- reject known aggregators as Origin authority.

### Layer C — ATS/portal fingerprint

Introduce a data-driven fingerprint registry, initially covering families already known in JAP plus high-value missing families supported by public feeds.

A fingerprint records evidence such as:

- provider family;
- host suffix/pattern;
- optional path signature;
- board/tenant/slug extraction rule;
- public job-feed endpoint template where safely available;
- evidence source and confidence.

Provider fingerprinting is evidence for how to interrogate a proved Origin; it is not source-validity authority by itself.

### Layer D — proof handoff

The selected official jobspace candidate continues into the existing generic source proof. F1 must not create a second admission authority.

## Carried residual CR-F0-001

Real evidence:

- `https://www.f-i.de/karriere/offene-stellen/frankfurt/data-platform-engineer-m-w-d`
- `https://www.f-i.de/de/karriere/offene-stellen/frankfurt/data-platform-engineer-m-w-d`

Both represent the same FI vacancy but current exact-URL canonicalization treats them as different.

Do not globally strip locale path segments and do not fuzzy-match title/company.

Resolve generically while implementing F1 canonical/jobspace evidence:

1. capture HTML canonical-link/final-redirect identity where available;
2. retain schema.org `JobPosting.identifier` when available;
3. add bounded provider-neutral extraction of explicitly labelled vacancy identifiers only when needed (`Job ID`, `Requisition ID`, `Reference`, `Kennziffer`, `Stellen-ID` etc.); never mine arbitrary numbers;
4. define identity namespace from authoritative Origin host/provider context;
5. review projection may collapse aliases only when this evidence proves one vacancy.

The FI case is a regression fixture, not a new FI parser rule.

## Failure taxonomy for the F1 funnel

At minimum classify:

- `company_identity_insufficient`
- `official_domain_not_found`
- `domain_unreachable`
- `company_domain_found_no_career_surface`
- `career_surface_reachable_identity_weak`
- `aggregator_only`
- `ats_fingerprint_unknown`
- `ats_candidate_unverified`
- `source_proof_failed`
- `source_proof_pass`

Do not collapse these into generic `not_found`; funnel counts must expose the bottleneck.

## First implementation slice

1. Add a generic external/official-domain evidence input to the existing discovery candidate model rather than another resolver.
2. Add attribute-bound ATS link fingerprinting to the existing HTTP probe result.
3. Add data-driven ATS fingerprint definitions and focused tests.
4. Preserve canonical/final identity evidence so CR-F0-001 can use stronger identity than path equality.
5. Run fresh companies through the resulting chain before expanding provider breadth.

No VERSION bump until this slice plus a useful real cohort is ready for the combined 1.0.21 release/operator test.
