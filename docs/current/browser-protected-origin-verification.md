# Browser-Protected Origin Verification Boundary

## Status

Architecture contract for issue #329. This slice defines data and state semantics only. It does not install a browser runtime, change origin selection, activate a source, create a connector, or bypass an access-control response.

## Problem

The existing origin-discovery contract treats HTTP-client reachability as mandatory for selection. That is correct for collector readiness, but it is not identical to origin ownership truth. A public corporate page can be a valid employer career origin while rejecting the current non-browser collector with HTTP 403.

The architecture therefore separates two independent facts:

1. **Origin truth** — the exact URL is an official, reusable career origin for the exact employer entity.
2. **Collection readiness** — an approved collector can retrieve the exact URL without evading access controls.

Neither fact silently implies the other.

## Safety and legal boundary

The project does not attempt to defeat or circumvent a website's access controls. This is a project-policy prohibition regardless of whether a particular technique might be lawful in a particular jurisdiction.

The following techniques are prohibited for origin verification:

- CAPTCHA-solving services or automated challenge interaction;
- stealth plugins, WebDriver-evasion, or fingerprint spoofing;
- importing browser cookies or reusing challenge tokens;
- proxy rotation or rate-limit evasion;
- session hijacking or copied authenticated sessions;
- scraping or interpreting challenge-page content as employer evidence.

A future standard browser verifier may perform ordinary navigation to a public URL. When it encounters a challenge, CAPTCHA, login requirement, consent barrier that blocks the target content, or another access-control boundary, it must stop and emit blocked evidence. It must not interact with the challenge to continue.

Operator attestation is a separate provenance class. It records a human-reviewed exact URL-to-company relationship; it does not make the automated collector fetchable and it does not authorize automation to pass a challenge.

## Evidence classes

### Origin-truth evidence

An immutable `OriginTruthEvidence` record contains:

- schema version and evidence ID;
- exact company key and normalized URL;
- source: `browser_observation` or `operator_attestation`;
- observation and expiry timestamps;
- verifier identity and version;
- requested, final, and optional canonical URL;
- page title, full distinctive employer-entity tokens, and career signals;
- content and optional screenshot SHA-256 digests;
- operator approval token when operator-attested;
- explicit challenge and automation-technique declarations.

Origin evidence is rejected when it is expired, has incomplete provenance, describes only the parent brand, points to a different path, uses a prohibited technique, or reports that automation encountered or interacted with a challenge.

### Collector-capability evidence

An immutable `CollectorCapabilityEvidence` record contains:

- exact URL and evidence provenance;
- observation and expiry timestamps;
- collector identity and version;
- final URL, status, reachability, and challenge classification;
- side-effect, provider-request, and pipeline-mutation declarations.

Collector evidence can establish `ready`, `blocked_by_access_control`, `blocked_unreachable`, or `unknown`. HTTP 403 remains blocked evidence and is never promoted to success.

## Deterministic state model

| Origin truth | Collection state | Decision | Meaning |
|---|---|---|---|
| unverified | any | `operator_review_required` | Exact employer-origin relationship is not proven. |
| verified | unknown | `origin_verified_collection_unknown` | Origin is proven; collector feasibility is not. |
| verified | ready | `origin_verified_collection_ready` | Origin and collector feasibility are proven, but activation is still a separate gate. |
| verified | blocked | `origin_verified_collection_blocked` | Origin is proven; automated collection must remain disabled. |

The architecture never emits `selected_deterministic_operator_url` for browser-protected evidence. It also always returns `source_activation_allowed=false`; this slice has no activation authority.

## E.ON interpretation

Under this model, valid operator-attested evidence for the exact E.ON Digital Technology career URL plus the existing 403 collector evidence produces:

```text
origin_truth_state=verified
collection_state=blocked_by_access_control
decision=origin_verified_collection_blocked
source_activation_allowed=false
```

This is an honest completion of origin verification, not a claim that collection works.

## Replay and auditability

The evaluator is a pure function. It performs no HTTP request, provider call, database write, source mutation, connector registration, Bronze/Silver write, ranking change, or scheduler change. Stored evidence can therefore be replayed deterministically in CI and review tooling.

## Next implementation slices

1. Add a read-only operator-attestation artifact writer with exact URL/company binding and expiry.
2. Add UI presentation for verified-but-blocked origins without showing them as active.
3. Optionally design a standard, non-stealth browser observer that stops on challenge detection.
4. Keep collection-feasibility and source-activation work in separately approved slices.

## Explicitly out of scope

- changing the existing requests probe;
- retrying PRs #326, #327, or #328;
- introducing a URL or company allowlist;
- bypassing HTTP 403 or anti-bot controls;
- source activation, connector construction, or scheduled collection;
- Tavily or LLM provider execution.
