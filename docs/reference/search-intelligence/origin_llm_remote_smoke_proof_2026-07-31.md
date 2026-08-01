# Origin LLM Remote Smoke Proof — 2026-07-31

Status: completed proof and completed bounded four-case follow-up  
Evidence dates: 2026-07-31 and 2026-08-01  
Pipeline revision: `b98ac259ac683423b9d63be0fcb3f4e331d2512a`  
Runtime revisions: `ab2d433c4b4afa76bce8794260ab8cb4973a376d`, `6934460e71e6bd6b7f8602c0273d26f94d04e9aa`

## Purpose

This record preserves the successful remote end-to-end proof for the candidate-bound origin LLM review contract and the bounded review of the four remaining ambiguous companies. It is an evidence record, not activation authority and not pipeline input.

The combined proof demonstrates:

1. GitHub-hosted dispatch through the temporary WARP/FRITZ wake path.
2. Recovery of the local WSL/Tailscale/PostgreSQL runtime.
3. A fingerprint-bound immutable origin-evidence run.
4. One successful `gpt-5.4-mini` review request for the strong E.ON case.
5. Four successful `gpt-5.4-mini` review requests for the remaining ambiguous cases.
6. Candidate references restricted to IDs present in each evidence packet.
7. Review-only output with no candidate, connector, source, Bronze/Silver or scheduler mutation.
8. Provider restraint when the supplied evidence cannot justify a deterministic winner.

## Run identity

| Evidence | Value |
|---|---|
| Dispatcher run | `30645889180`, successful rerun |
| Origin and E.ON runtime run | `30663046360` |
| Four-case review run | `30685640392` |
| Projection fingerprint | `0d1f162b070a71a59b5986d092f46546b84483ae0d6f0e02a2d122acfc4b6125` |
| Origin runtime contract SHA-256 | `554e4b3a697806c7ef8620fca5ff38a6f45cb741f56cf8f1007eda1bf87292c6` |
| Origin artifact ID | `8805953697` |
| Origin artifact SHA-256 | `6669dac68266e8479236a70f29888ab40664668b195ec71e39574995896cc03e` |
| Origin evidence payload SHA-256 | `38378a56a7ac6b9f9a5253ee0977ed3ad74e0f0ebefd85564c564cff3019336d` |
| E.ON model artifact ID | `8805964899` |
| E.ON model artifact SHA-256 | `d68e0c115344480fc0eb4483d8f6d70e2d7ec18edf95f281ae6dc2aec45d6afc` |
| Four-case artifact ID | `8813795551` |
| Four-case artifact SHA-256 | `ca342bac30f6037de8453d1ffd2fbff3641ada563e56858d483b6e978404b03f` |

The private workflow artifacts have finite retention. Their hashes remain the durable evidence references after expiry.

## Remote runtime result

The dispatcher and runtime path completed successfully:

- WARP IPv6 transport ready.
- Restricted FRITZ WireGuard path ready.
- Local Tailscale node reachable.
- PostgreSQL port reachable.
- Exact Pipeline revision checked out.
- PostgreSQL advisory runtime lease acquired.
- Eight lease heartbeats observed.
- Lease released after the origin benchmark.
- Temporary runner Tailscale session logged out and cleaned up.

The origin run processed six companies with these bounded operations:

| Metric | Result |
|---|---:|
| Companies | 6 |
| Tavily request attempts | 12 |
| Bounded HTTP request attempts | 20 |
| Deterministic selections after source grading | 2 |
| Manual-review decisions | 4 |
| LLM calls in source-grading stage | 0 |
| Database reads after verified snapshot | 0 |

## One-call E.ON proof

The diagnostic model campaign used this hard envelope:

| Contract | Result |
|---|---|
| Cases | 1 |
| Requested model | `gpt-5.4-mini` |
| Provider request attempts | 1 |
| Completed | 1 |
| Failed | 0 |
| Application retry | 0 |
| Escalation request | 0 |
| Reasoning effort | `low` |
| Maximum output tokens | 1,200 |
| Estimated cost | `$0.00135375` |

Observed provider telemetry:

- returned model: `gpt-5.4-mini-2026-03-17`
- latency: `2219 ms`
- input tokens: `1103`
- output tokens: `117`
- reasoning tokens: `12`
- total tokens: `1220`

### E.ON result

Company: `E.ON Grid Solutions GmbH`  
Case: `eon_grid_solutions_strong_origin`

The provider returned:

- decision: `confirm_deterministic`
- entity relationship: `exact_legal_entity`
- origin assessment: `verified_job_listing`
- recommended candidate ID: `C3`
- evidence references: `C3`
- manual review required: `false`
- effective URL: `https://jobs.eon.com/de/eon-gridsolutions`
- quality score: `1.0`

This closes the previously observed candidate-reference defect: the provider used only a candidate ID included in the immutable evidence packet.

## Four-case follow-up

Runtime run `30685640392` consumed the exact immutable origin-evidence payload from run `30663046360`. It did not repeat database access, Tavily discovery or HTTP probing.

### Execution result

| Contract | Result |
|---|---|
| Eligible companies | 4 |
| Processed companies | 4 |
| Requested model | `gpt-5.4-mini` |
| Primary request attempts | 4 |
| Completed provider results | 4 |
| Failed provider results | 0 |
| Application retries | 0 |
| Escalation requests | 0 |
| Database access | 0 |
| Tavily requests | 0 |
| Estimated total cost | `$0.00835200` |
| Pessimistic reservation | `$0.03660000` |
| Hard cost ceiling | `$0.04000000` |
| Output boundary | `review_output_only_not_pipeline_input` |

All four calls returned `gpt-5.4-mini-2026-03-17`. No call recommended a candidate outside its supplied evidence references.

### Hannover Rück SE

Provider result:

- decision: `manual_review_required`
- entity relationship: `ambiguous`
- origin assessment: `career_landing_only`
- recommended candidate ID: `null`
- evidence references: `C1`, `C2`, `C3`
- manual review required: `true`
- cost: `$0.00191100`
- latency: `3802 ms`

Interpretation:

- `C1` has the strongest exact-entity fidelity.
- none of the candidates proves concrete job inventory.
- `C2` and `C3` are parent-group matches rather than exact-entity matches.
- the blocker is missing source evidence, not missing model reasoning.

### msg systems ag

Provider result:

- decision: `manual_review_required`
- entity relationship: `exact_legal_entity`
- origin assessment: `insufficient_evidence`
- recommended candidate ID: `null`
- evidence references: `C3`
- manual review required: `true`
- cost: `$0.00203700`
- latency: `2384 ms`

Interpretation:

- `C3` has the strongest entity fidelity and ATS/listing signals.
- no concrete job record was extracted and the observed job count is zero.
- the blocker is an inventory-proof or extraction gap.

### Materna Information & Communications SE

Provider result:

- decision: `manual_review_required`
- entity relationship: `exact_legal_entity`
- origin assessment: `verified_job_listing`
- recommended candidate ID: `null`
- evidence references: `C1`, `C3`, `C2`
- manual review required: `true`
- cost: `$0.00217650`
- latency: `2746 ms`

Interpretation:

- concrete exact-entity job-listing evidence exists.
- `C1` and `C3` are tied on all supplied winner signals.
- the blocker is duplicate/equivalent candidate identity or absent tie-break evidence, not lack of source-grade evidence.

### x1F GmbH

Provider result:

- decision: `manual_review_required`
- entity relationship: `exact_legal_entity`
- origin assessment: `verified_job_listing`
- recommended candidate ID: `null`
- evidence references: `C2`, `C3`
- manual review required: `true`
- cost: `$0.00222750`
- latency: `2586 ms`

Interpretation:

- `C2` and `C3` both carry exact-entity and job-bearing evidence.
- both candidates are tied and the selection margin is zero.
- the official `x1f.one/jobs` candidate did not prove inventory in the source payload.
- the blocker is a combination of candidate tie resolution and explicit official-versus-third-party origin policy.

## Evidence conclusion

The four-case follow-up did not convert any ambiguous case into a deterministic selection. This is not a provider execution failure:

- all four provider calls completed;
- all candidate references were schema-valid and evidence-bound;
- the provider correctly retained manual review when the supplied evidence did not justify a winner;
- no escalation was attempted;
- no mutation boundary was crossed.

The evidence separates the remaining work into finite technical classes:

1. `inventory_evidence_gap`
   - Hannover Rück: prove concrete job inventory or retain a known career-only origin.
   - msg systems: extract or verify at least one concrete job record from the exact-entity ATS candidate.
2. `candidate_equivalence_or_dedup_gap`
   - Materna: establish whether `C1` and `C3` are duplicate, redirect-equivalent or operationally distinct origins.
3. `origin_policy_and_tie_gap`
   - x1F: define whether tied third-party job pages may ever become origin truth when the official page lacks proven inventory.

## Next decision boundary

A stronger model should not be called merely to break these ties. The current evidence indicates that the limiting factor is source data, canonicalization or policy, not obvious reasoning quality.

The next bounded implementation slice should therefore produce deterministic enrichment for the four blocker classes before any escalation-model campaign:

- concrete inventory proof for Hannover Rück and msg systems;
- URL/candidate canonicalization and equivalence evidence for Materna;
- explicit official-source versus third-party origin policy plus tie handling for x1F.

Any future provider run must remain review-only and may be re-entered only after the relevant evidence payload has materially changed.

## Mutation boundary

Neither proof run may be interpreted as permission to:

- write a candidate URL;
- register a connector;
- activate a source;
- write Bronze or Silver data;
- change a scheduler;
- convert provider output into selection truth.
