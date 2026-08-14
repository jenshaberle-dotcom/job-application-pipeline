# LLM-BOOST-001 — Detail Semantics deterministic gap boundary

Status: Slice 8C corrected implementation contract
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

The corrected completeness contract and executor must pass exact-head Pipeline CI and re-entry before any provider/runtime semantic smoke. A live semantic adapter must additionally verify model evidence spans against the exact bounded detail text before deterministic validation can accept any field.
