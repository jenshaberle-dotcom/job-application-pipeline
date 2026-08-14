# LLM-BOOST-001 — Detail Semantics deterministic gap boundary

Status: Slice 8A implementation contract
Authority: Issue #522

## Purpose

Detail Semantics starts only after existing deterministic detail validation has established supported concrete-detail truth. The first Slice-8 boundary remains provider-free and side-effect free.

Known structured fields and deterministic term logic stay first. Semantic model stages may later propose bounded hypotheses for:

- role;
- seniority;
- skills;
- location;
- remote semantics.

Every semantic hypothesis must retain bounded evidence references. Existing deterministic product profile and geography contracts remain the only authority for whether the evidence is sufficient.

## Gap classification

`detail_semantics_gap.py` consumes already-normalized deterministic observations only. It does not fetch or infer source truth.

The contract distinguishes:

- `detail_semantics_d0_required`: deterministic Detail Semantics has not run; no external stage is eligible;
- `detail_semantics_requires_supported_detail`: concrete detail truth is not already supported; no semantic booster may bypass Detail Discovery authority;
- `detail_semantics_resolved`: deterministic profile and geography contracts are already satisfied; Tavily and all model stages are skipped;
- `detail_semantics_ambiguity_gap`: supported detail truth exists but one or both deterministic product contracts remain unsatisfied; Tavily is skipped and the bounded model cascade may produce hypotheses only;
- `detail_semantics_gap_unchanged`: the normalized semantic evidence fingerprint is unchanged; all provider/model stages are skipped until evidence changes.

Ordinary semantic ambiguity is not an external-information acquisition gap. Therefore Tavily must not be enabled merely because structured/term parsing cannot fully resolve role, seniority, skills, location or remote meaning.

## Evidence fingerprint

The semantic fingerprint binds:

- candidate ID;
- company key;
- supported detail URL;
- whether deterministic semantics ran;
- existing detail support truth;
- existing profile/geography contract outcomes;
- normalized role/seniority/skills/location/remote fields;
- bounded evidence references and spans;
- Detail Semantics gap-contract version.

A changed field, evidence reference/span, contract outcome or contract version changes the fingerprint. An unchanged fingerprint is provider/model-ineligible.

## Authority boundary

This slice grants none of the following:

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

Slice 8A must pass exact-head Pipeline CI and re-entry before any provider/runtime semantic smoke. A later semantic execution slice must retain evidence references for every model-produced field and deterministically revalidate resulting evidence through the existing product contracts before any downstream authority can change.
