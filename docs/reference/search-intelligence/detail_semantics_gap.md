# LLM-BOOST-001 — Detail Semantics deterministic gap boundary

Status: Slice 8D live-adapter validation contract
Authority: Issue #522

## Purpose

Detail Semantics starts only after existing deterministic detail validation has established supported concrete-detail truth. Known structured fields and deterministic term logic stay first. Semantic model stages may later propose bounded hypotheses for:

- role;
- seniority;
- skills;
- location;
- remote semantics.

Every semantic hypothesis must retain bounded evidence references. Existing deterministic product profile and geography contracts remain independent product-support authority; they do **not** define whether semantic extraction itself is complete.

That distinction matters because a DETAIL-001 page can already be supported for profile/geography while seniority, skills or remote semantics are still missing or ambiguous.

## Requested semantic scope

Each Detail Semantics run supplies a bounded non-empty subset of the canonical fields above as `requested_semantic_fields`. Semantic completeness is evaluated only against that requested set.

This makes cost control explicit: a caller that needs only `role` and `location` does not unlock model work merely because `skills` or `seniority` are absent. The requested field set is part of the evidence fingerprint.

## Gap classification

`detail_semantics_gap.py` consumes already-normalized deterministic observations only. It does not fetch or infer source truth.

The contract distinguishes:

- `detail_semantics_d0_required`: deterministic Detail Semantics has not run; no external stage is eligible;
- `detail_semantics_requires_supported_detail`: concrete detail truth is not already supported; no semantic booster may bypass Detail Discovery authority;
- `detail_semantics_resolved`: every requested semantic field is already deterministically present; Tavily and all model stages are skipped, regardless of independent product profile/geography status;
- `detail_semantics_ambiguity_gap`: supported detail truth exists but one or more requested semantic fields are still missing; Tavily is skipped and the bounded model cascade may produce hypotheses only;
- `detail_semantics_gap_unchanged`: the normalized semantic evidence fingerprint is unchanged; all provider/model stages are skipped until evidence changes.

Ordinary semantic ambiguity is not an external-information acquisition gap. Therefore Tavily must not be enabled merely because structured/term parsing cannot fully resolve role, seniority, skills, location or remote meaning.

## Execution resolution

The authority-neutral executor resolves only when all requested semantic fields are present after deterministic validation of model hypotheses. Green profile/geography product contracts cannot fake semantic completion.

A deterministic validator may accept only canonical fields that were actually present in the model hypothesis and may retain only evidence references already supplied by that hypothesis. It may narrow or reject a hypothesis, but it may not broaden fields or evidence. Product authority remains false.

## Live span-verification contract

`detail_semantics_hypothesis_provider.py` and `scripts/run_detail_semantics_booster.py` form the first live semantic adapter.

The runner:

1. accepts exactly one public HTTPS detail URL;
2. reuses the existing DETAIL-001 bounded fetch and plain-text extractor;
3. rejects a cross-base-domain redirect;
4. bounds provider-visible text to 16,000 characters and never persists raw HTML;
5. calculates existing profile/geography support independently from the bounded detail text;
6. runs provider-free deterministic term extraction for the requested semantic fields;
7. invokes only the still-missing requested fields through the canonical Luna → Terra → Sol → Luna-max sequence;
8. never invokes Tavily for ordinary Detail Semantics ambiguity.

The OpenAI provider uses the existing Responses API boundary with `store=false`, a strict JSON schema and the canonical per-stage price/ceiling configuration. Each returned claim contains `field`, `value`, `evidence`, `span_start` and `span_end`.

Before a provider result can reach the executor, the adapter requires all of the following:

- the field belongs to the explicit requested scope;
- the evidence span is inside the exact bounded detail text;
- `detail_text[span_start:span_end] == evidence`;
- the returned value occurs inside that evidence;
- role, seniority, location and remote occur at most once per response; skills may produce multiple grounded values;
- every evidence reference is forced to the one fetched final detail URL.

The runner repeats the same-detail span and value checks before deterministic validation accepts the evidence. This second check protects against mutation or adapter drift between provider parsing and execution.

A span-grounded semantic result is still evidence/hypothesis output only. `semantic_authority=false` and `product_authority=false` remain invariant. No database, gate, lifecycle, ranking, application or product write path exists in the live runner.

## Evidence fingerprint

The semantic fingerprint binds:

- candidate ID;
- company key;
- supported detail URL;
- whether deterministic semantics ran;
- existing detail support truth;
- independent profile/geography contract outcomes;
- requested semantic field set;
- normalized role/seniority/skills/location/remote fields;
- bounded evidence references and spans;
- Detail Semantics gap-contract version.

A changed requested scope, field, evidence reference/span, contract outcome or contract version changes the fingerprint. An unchanged fingerprint is provider/model-ineligible.

## Authority boundary

This contract grants none of the following:

- semantic authority from a provider/model;
- concrete-detail authority;
- profile/geography authority;
- gate pass;
- lifecycle or ranking authority;
- source/connector activation;
- application action;
- database/product write.

The shared LLM-BOOST-001 plan remains a side-effect-free eligibility description with zero provider, LLM, database and product-write requests.

## Promotion boundary

Slice 8D must pass exact-head Pipeline CI and re-entry before a private Runtime Detail Semantics shadow is created. Runtime acceptance must preserve the same immutable repo/head checks, bounded provider budget, read-only data access and zero-write/product-authority invariants already proven by the Detail Discovery shadow transport.
