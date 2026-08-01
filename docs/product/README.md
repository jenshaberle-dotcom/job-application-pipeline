# Product Authority

Status: active authority surface
Project character: **A — Intent Locked**

## Purpose

This directory defines what the Job Application Pipeline must become from the operator's perspective.

It is deliberately separate from architecture, implementation planning and historical build traces. Technical work may be adaptive; product meaning may not drift through implementation convenience, agent inference or stale planning documents.

## Files

1. `PRD.md` — approved and pending product requirements.
2. `PRODUCT_DECISION_REGISTER.md` — unresolved operator decisions required for high-fidelity implementation.
3. `ACCEPTANCE_SCENARIOS.md` — representative product examples that make the target behavior testable.
4. `TRACEABILITY.md` — rules connecting product intent to backlog, implementation and acceptance.

## Product authority

Jens owns product behavior and prioritization.

DON and other agents may:

- discover contradictions;
- propose better product options;
- explain consequences and trade-offs;
- suggest changes to requirements;
- choose technical implementation details inside approved requirements.

They may not:

- infer an unresolved preference and mark it approved;
- change Top-5, ranking, target-profile, geography or review semantics without an operator decision;
- treat current implementation as proof that the implemented behavior is desired;
- close a product ambiguity with a technical default;
- promote a proposal into current truth because tests pass.

## Status model

Every product requirement or decision uses one of:

- `approved` — explicit operator decision and active product truth;
- `recorded_repo_truth_pending_confirmation` — supported by current repository material but still requires operator ratification during PRD rebaseline;
- `open_operator_decision` — product meaning is intentionally unresolved;
- `proposed` — an agent or engineering proposal only;
- `rejected` — explicitly not part of the active product;
- `superseded` — replaced by a newer approved decision.

Only `approved` requirements may define new product behavior.

## Current rebaseline rule

The repository may continue:

- safety and security work;
- bug fixing;
- documentation consistency work;
- read-only evidence recomputation;
- operational stabilization.

New product-shaping implementation must wait for the relevant product decisions and acceptance scenarios. The rebaseline is not a freeze on all engineering; it is a guard against building precise machinery around an imprecise product target.
