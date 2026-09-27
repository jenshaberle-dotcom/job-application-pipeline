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
4. The default market-sensor state may be no provider at all. A missing/unavailable optional backend is a valid local outcome and never authorizes another provider automatically.
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

Current market-sensor provider authority:

- default: `none` — zero external requests and zero provider dependency;
- admitted residual adapter: `tavily` — explicit operator selection only; never automatic and never required by unrelated JAP paths.

The two zero-key experiments are **qualification history, not active backends**:

- `duckduckgo_html`: real run `36316182144` made six bounded requests and yielded zero accepted observations; current automated-client challenge/block behavior is not worked around with impersonation, proxy rotation or CAPTCHA/evasion mechanics;
- `bing_rss`: aggregate diagnostics proved the transport itself was reachable but unsuitable for strict LinkedIn job-detail discovery. Run `36325970818` returned 30 direct off-domain results; after a declarative quoted URL hint, run `36326241225` returned 30 direct LinkedIn-domain results but all 30 failed the required job-detail path.

These failed experiments are removed from the active market-sensor adapter set rather than retained as misleading fallback authority.

No automatic provider fallback exists. Future library/self-hosted/open alternatives require a separate evidence and legal/anti-evasion review before admission. The `ddgs` family is not admitted merely because it is a library: its browser-impersonation/proxy-oriented compatibility mechanisms conflict with the conservative GREEN boundary. A self-hosted service such as SearXNG is likewise not introduced until its operational value justifies another runtime dependency.

LinkedIn therefore does not have a Tavily implementation. It has a platform specification consumed by generic search intent/result-validation machinery. Tavily is only one optional transport adapter around that generic contract.

## Reliability boundary

"Zero-cost-first" does not mean pretending that a free public surface is guaranteed.

Each backend may report:

- success with results;
- zero yield;
- provider unavailable;
- transport error.

The market sensor treats these as local discovery outcomes. They do not block JAP ingestion, Product V1, application tracking or drafting.

When a zero-cost/self-controlled candidate is evaluated:

1. measure the failure mode;
2. reject it rather than add evasion if reliability depends on anti-bot adaptation;
3. evaluate another library/self-hosted/open alternative only when its operational and legal boundary is clear;
4. keep any external API optional unless evidence proves that it is worth the explicit dependency.

Failure to find a sufficiently reliable free backend does not make a paid provider part of Product truth; it may simply leave the optional sensor dormant.

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

- the conservative sensor may be dormant when no explicitly selected provider is available;
- JAP owns a small generic adapter boundary without pretending an unreliable free transport is production-ready;
- external-provider quality and cost remain explicit operator choices.

## Validation

A market-sensor backend change is acceptable only when:

- the default path performs zero external provider requests and requires no credentials/account;
- the paid provider is not called implicitly;
- platform-specific sensor code contains no direct provider transport;
- real proof records backend identity, request count and outcome;
- downstream S0.6 can consume the same minimised artifact independent of backend.
