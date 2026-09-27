# ADR-036 — External tool dependencies are optional residual capabilities

Status: Accepted  
Date: 2026-09-27

## Context

JAP increasingly uses discovery, parsing, classification and generation capabilities that can be obtained in several ways:

- deterministic in-repository code;
- ordinary reusable libraries;
- public/open protocols or bounded HTTP surfaces;
- locally hosted/open-source components;
- external SaaS/API tools that may require credentials, quotas or payment.

A convenient external tool can become an accidental architectural dependency. If the tool changes price, quota, terms, availability or API shape, a core JAP path can stop even though the underlying capability is technically simple.

The LinkedIn/Indeed defensive market-sensor work exposed this risk: the first real proof used Tavily because a bounded search-provider path already existed, but the sensor capability itself is only "execute a bounded public-web query and return result metadata". That capability must not become synonymous with Tavily.

## Decision

JAP follows a **self-controlled / replaceable / zero-cost-first dependency hierarchy**.

For a capability, implementation preference is:

1. deterministic repository code;
2. stable reusable library/parser;
3. bounded public/open transport that requires no paid account;
4. self-hosted/open-source service when justified by reliability or scale;
5. external free-tier API when it adds material capability;
6. paid external tool/API only for a proven residual gap.

A lower-numbered viable implementation is preferred when quality is sufficient.

## Hard rules

1. **No core pipeline path may require a paid external tool merely because it was convenient during development.**
2. Paid/external backends must sit behind a replaceable interface or adapter.
3. Failure, quota exhaustion or removal of an optional backend must not stop unrelated JAP product paths.
4. A free/default backend may return zero yield or fail closed. That does not automatically authorize a paid fallback.
5. Paid fallback requires an explicit operator/configuration choice unless a separately reviewed authority says otherwise.
6. Provider-specific response parsing belongs inside the provider adapter. Product/search intent and source/sensor logic must remain provider-independent.
7. Source/platform-specific logic should be declarative where practical: host/path acceptance, source capabilities and minimal evidence extraction. It must not own transport credentials, retry/evasion behavior or billing assumptions.
8. Credentials, quotas and billing are capabilities, never product truth.
9. External-provider output is evidence only until the normal deterministic validation/authority path accepts it.
10. Tests must cover operation with the paid provider absent.

## Market-sensor application

The conservative market sensor is split into three independent layers:

- **search intent** — role/location intent owned by JAP;
- **search backend** — replaceable public-web transport;
- **sensor specification** — declarative platform host/path acceptance and minimal company-signal extraction.

Current backend authority:

- default: `none` — zero external search requests and therefore zero vendor/billing dependency;
- proven residual: `tavily` — explicit operator-selected search-index provider only;
- diagnostic/free adapters: `duckduckgo_html` and `bing_rss` — retained for evidence/experiments but not production defaults after real qualification failed;
- future official structured APIs may be admitted behind the same adapter contract after separate review.

There is **no automatic fallback to Tavily or any other paid/external provider**. A real market-expansion run must explicitly select its backend. If no provider is configured or paid, JAP continues to operate; only incremental market discovery is unavailable.

LinkedIn therefore does not have a Tavily implementation. It has a platform specification consumed by the same general market-sensor/search-backend machinery as other discovery-only sources.

## Reliability boundary

"Zero-cost-first" does not mean pretending that a free public surface is guaranteed.

Each backend may report:

- success with results;
- zero yield;
- provider unavailable;
- transport error.

The market sensor treats these as local discovery outcomes. They do not block JAP ingestion, Product V1, application tracking or drafting.

The free/self-controlled search investigation produced the following evidence:

1. `duckduckgo_html`: real run `36316182144` produced 0 accepted observations from six queries; current external evidence shows automated-client HTTP-202/challenge behavior.
2. `bing_rss`: real runs `36316916122` and `36317114804` each returned 30 results, all rejected as unexpected hosts even after simplifying search intent to a domain-only `site:` constraint.
3. `ddgs`: library review found provider scraping, automatic backend fallback and optional proxy/Tor paths; some engines use randomized browser identities. It is not admitted into the defensive Core path.
4. self-hosted SearXNG would add an operational service while still depending on upstream search-engine acquisition; it does not create an independent index and therefore does not remove the underlying reliability/policy dependency.
5. Common Crawl is open/self-controlled but is a crawl URL/content archive rather than a current keyword/location search index, so it does not satisfy this market-sensor task.

On that evidence, a structured external search API is a justified **residual capability**, but remains explicitly selected and non-authoritative.

## Security / legal boundary

This ADR does not grant permission to scrape a target platform.

For LinkedIn specifically, `docs/planning/active/LINKEDIN-DEFENSIVE-MARKET-SENSOR.md` remains authoritative:

- JAP does not request LinkedIn pages directly;
- no account/login/cookie/browser/Voyager/guest-API/CAPTCHA/proxy/evasion path;
- raw LinkedIn URL/title/snippet metadata is not persisted;
- LinkedIn evidence is discovery-only and discarded before Employer-Origin authority.

The replaceable search backend is transport, not permission.

## Consequences

Positive:

- no mandatory Tavily spend for market sensing;
- provider outages do not stop the product;
- easier provider replacement and benchmarking;
- source logic is less coupled to vendor response formats;
- cost decisions remain operator decisions.

Trade-offs:

- free/public backends may be less stable or lower-yield;
- JAP owns a small amount of generic provider-adapter code;
- empirical quality must be measured before retiring a stronger optional provider.

## Validation

A market-sensor backend change is acceptable only when:

- the default path runs without Tavily credentials or any paid-search account;
- the paid provider is not called implicitly;
- platform-specific sensor code contains no direct provider transport;
- real proof records backend identity, request count and outcome;
- downstream S0.6 can consume the same minimised artifact independent of backend.
