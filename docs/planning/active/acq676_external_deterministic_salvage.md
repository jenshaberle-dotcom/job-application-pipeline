# ACQ-676 — external deterministic salvage map

Status: active implementation reference

## Purpose

Use mature public ATS implementations as capability knowledge so the pipeline does not
rediscover provider mechanics employer-by-employer. External knowledge may define a
provider-wide capability shape, parser contract, or test hypothesis. It does **not**
grant employer, tenant, host, route-value, product, or proof authority.

## Reviewed sources

- `kalil0321/ats-scrapers` (MIT): broad reusable ATS adapters and normalized feed parsers.
- `ConorsCode/ats-api-reference` (MIT): live-verified public ATS endpoint contracts.
- `Ramcharan747/careerscout`: career/ATS discovery and schema-driven parsing architecture.
- d.vinci public Job Publication API documentation: provider-owned publication endpoint contract.
- `yuyao-wang/Jobops` (MIT): deterministic-before-AI execution architecture; retained as later application-execution reference, not ACQ discovery authority.

## Keep / adapt / reject

### Keep and adapt now

1. **Provider capability registry rather than employer-specific rescue code.**
   Fixed provider routes are reusable only after the current repository has independently
   established the employer/source host and provider family.
2. **Structured feed parsing.**
   Parse only provider-owned inventory formats and emit concrete URLs carried by the feed.
   Final acceptance remains the unchanged `genuine_job_detail_proof` after fetching a
   concrete public detail.
3. **Fail-closed schema validation.**
   A route existing in provider documentation is not enough: the fetched payload must match
   the expected provider schema before it can produce detail candidates.
4. **Bounded request accounting.**
   Public-feed acquisition gets an independent diagnostic cap and never creates a hidden
   provider/LLM/Tavily/database write path.
5. **Schema-driven parser direction.**
   Provider-specific shape differences are isolated in pure parsers instead of widening
   global jobish vocabulary.

### First capability tranche

The first tranche deliberately selects fixed paths that can be derived from an already
bound host without guessing a tenant, slug, shard, board name, opaque ID, or form value:

| provider | externally learned public inventory | project admission rule |
| --- | --- | --- |
| SuccessFactors Recruiting Marketing | root `sitemal.xml` RSS feed | only after existing `authorized_ats_provider()` says `successfactors`; feed stays on the exact already-authorized host; payload must validate as RSS/channel with concrete item links |
| Softgarden | root `jobs.feed.json` Schema.org DataFeed | only canonical `*.career.softgarden.de` host already authorized and recognized as `softgarden`; payload must validate DataFeed elements and concrete URLs |
| Recruitee | root `api/offers` JSON | only canonical `*.recruitee.com` / `*.recruitee.io` host already authorized and recognized as `recruitee`; payload must contain offer objects with concrete careers URLs |
| d.vinci | `jobPublication/list.json?fields=small` | only an already-authorized canonical `*.dvinci.de` host; an explicit `/portal/<name>` prefix is preserved when already present; payload must contain concrete `jobPublicationURL` values |

### Explicitly rejected from external projects

- company-name -> tenant/slug derivation;
- Workday shard/environment/board brute force;
- probing fallback board names;
- provider-directory membership as employer authority;
- guessed cross-host API delegation;
- guessed form values or POST bodies;
- external dataset rows as product coverage proof;
- relaxed genuine-job proof thresholds.

CareerScout's brute-force probing is therefore useful as research evidence about provider
families, but is not admissible runtime authority in this project.

## Benchmark contract

The external-salvage benchmark is an ordered **V6 residual overlay** above the unchanged V5
assessment. It may attempt only V5 `inventory` or `detail` residuals. A candidate is promoted
only when the public feed itself validates, yields a concrete same-authority detail URL, and
that fetched detail passes the unchanged genuine-job proof.

`V5 baseline -> provider public-feed overlay -> V6 diagnostic result`

The product numerator remains `36/65` until a promoted generic capability is materialized
and passes the normal strict E2E/product acceptance boundary.
