# ADR 028 — Minimize external tool and paid-provider dependencies

Status: ACCEPTED
Date: 2026-09-27
Scope: JAP Classic and reusable JAP acquisition/search capabilities

## Context

JAP benefits from libraries, parsers and external evidence sources, but the product
must not become operationally dependent on a commercial tool merely because that
tool is convenient during development.

A provider that becomes unavailable, changes pricing, exhausts credits, changes
terms or is intentionally no longer paid for must not stop the core pipeline.

This is especially important for market discovery. LinkedIn is intentionally not
accessed directly by JAP automation, so a current LinkedIn market sensor requires
some search-index transport. That unavoidable transport dependency must remain
replaceable and non-authoritative.

## Decision

JAP uses the following dependency order:

1. **Local deterministic capability**
   - standard library and normal project dependencies;
   - parsers, classifiers, URL rules, structured-data readers and local fixtures;
   - no network/provider account required.

2. **First-party / source-near transport**
   - employer/ATS/public source endpoints;
   - documented official APIs where access is legitimately available;
   - bounded public HTTP where project policy admits it.

3. **Keyless or self-controlled generic transport**
   - reusable transport that is not specific to one employer/platform;
   - no paid account required;
   - failure is an explicit `unavailable`/`zero_yield` outcome, never a reason to
     escalate automatically to a paid service.

4. **Commercial external provider**
   - permitted only as an explicit, optional residual/fallback path;
   - must be operator-selectable and disabled by default whenever a sufficiently
     useful lower-tier path exists;
   - may not become Product/source truth;
   - may not be an automatic fallback that silently spends money.

## Hard rules

- **No automatic paid fallback.**
- No core Product/DB/application path may require Tavily, Brave, an LLM provider,
  a hosted scraping product, or another paid search/data service merely to remain
  operational.
- Provider secrets are optional capability secrets, not product boot
  prerequisites.
- Provider-unavailable is a valid bounded outcome for discovery/sensor paths.
- Tests and deterministic qualification must run without commercial providers.
- Provider-specific response handling belongs behind a generic capability
  boundary. Platform-specific policy remains declarative where practical.
- Persisted truth must remain reconstructable without a commercial provider.
- Paid-provider request counts and costs must be explicit whenever such a provider
  is deliberately used.
- Adding a new commercial dependency requires a reviewed repository change that
  states why lower dependency tiers are insufficient.

## Freeze-II LinkedIn application

The LinkedIn sensor is split into two independent concerns:

1. **Sensor policy/specification**
   - site/domain/path expectation;
   - accepted minimal evidence;
   - company-signal extraction;
   - persistence minimisation;
   - no direct LinkedIn HTTP/login/browser/unofficial API.

2. **Generic public-search transport**
   - current zero-cost/default candidate: bounded DuckDuckGo non-JavaScript HTML
     search already used elsewhere in JAP;
   - `provider=none` remains valid for planning/offline qualification;
   - Tavily remains available only by explicit operator selection;
   - there is no automatic DuckDuckGo -> Tavily escalation.

If the keyless backend is blocked or its markup changes, the sensor reports
provider-unavailable. JAP continues operating.

## Considered alternatives

### Tavily as default

Rejected as architecture authority. It works well and can remain useful for
measurement or residual recovery, but it introduces account/credit/pricing
dependency.

### Brave Search API as default

Not selected. It is another commercial API with usage pricing and therefore does
not solve the dependency objective.

### Bing Search API

Not available as a durable option; Microsoft retired the Bing Search APIs in 2025.

### Self-hosted SearXNG

Potential future adapter, but not a current default. It is open source and can be
self-hosted, yet it adds another operated service and still depends on upstream
search engines. Add it only if measured reliability justifies that complexity.

### Direct LinkedIn acquisition

Rejected for the defensive sensor. It materially increases contractual,
anti-automation and operational risk and would create platform-specific transport
logic.

## Consequences

- Some free/keyless searches may produce lower recall or become temporarily
  unavailable.
- That loss of convenience is accepted in exchange for lower lock-in and a
  pipeline that does not stop when a commercial search budget disappears.
- Commercial providers can still be used deliberately where they prove unique
  value, but only as replaceable adapters.
