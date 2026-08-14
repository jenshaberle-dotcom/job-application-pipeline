# Detail Semantics Slice 8A boundary

This file records the implementation boundary for Issue #522 while Slice 8A is under validation.

- Base: `main@fb09bff63efeda993858349af84464becf300f81`
- Branch: `agent/522-detail-semantics-d0-slice8`
- Surface: `LLM-BOOST-001 / detail_semantics`
- Scope: pure deterministic semantic-gap classification, evidence fingerprinting and focused tests.
- Existing deterministic concrete-detail, profile and geography contracts retain authority.
- Ordinary semantic ambiguity is not an external-information gap; Tavily remains ineligible.
- Any future model output is hypothesis/evidence only and must retain bounded evidence references.
- No provider/model execution, database write, gate/lifecycle/ranking/application mutation, source/connector activation or product authority belongs to Slice 8A.

This is a recovery/validation marker, not a stop condition. Repository truth and exact-head CI supersede this marker when the branch advances.
