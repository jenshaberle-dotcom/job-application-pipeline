# Product Authority

Status: active authority surface  
Project character: **A — Intent Locked**  
Active product track: **PRODUCT-RECOVERY-001 / issue #783**

## Purpose

This directory defines what the Job Application Pipeline must do from the operator's perspective.

It is deliberately separate from architecture, implementation planning and historical build traces. Technical implementation may adapt; product meaning may not drift through implementation convenience, demo pressure, agent inference or stale planning.

## Files

1. `PRD.md` — approved and pending product requirements.
2. `PRODUCT_DECISION_REGISTER.md` — approved/open product decisions.
3. `ACCEPTANCE_SCENARIOS.md` — representative operator outcomes and fixtures.
4. `TRACEABILITY.md` — rules connecting product intent to backlog, implementation, E2E proof and release history.

## Current approved product core

The product is now explicitly defined as a Search Intelligence **and application-preparation** system.

Approved minimum journey:

```text
market discovery
-> Employer-Origin resolution
-> current exact vacancy
-> Bronze / Silver
-> assessment
-> capability fit
-> hard filters
-> deterministic ranking
-> bounded recommendation queue
-> Application Workspace
-> review-ready CV/letter package
```

Key approved semantics include:

- aggregators discover; Employer-Origin confirms authoritative recommendation/application action;
- Top 5 is at most five;
- current minimum overall recommendation quality is 70/100;
- required evidence/hard filters block rather than silently default;
- no automatic application submission/send;
- application provider calls occur only through explicit operator Generate;
- generated documents remain `draft_for_review`;
- current Product Recovery target is one normal cold-to-application flow, not a demo repair sequence.

See the decision/scenario files for exact IDs and remaining open behavior.

## Product authority

Jens owns product behavior and prioritization.

Engineering/agents may:

- discover contradictions;
- propose better product options;
- explain consequences/trade-offs;
- suggest requirement changes;
- choose technical implementation inside approved requirements.

They may not:

- infer an unresolved preference and mark it approved;
- change Top-5/ranking/target-profile/geography/review/application semantics without an operator decision;
- lower evidence/ranking gates to satisfy a demo or quota;
- treat current code/database behavior as proof it is desired;
- promote provider output into candidate/job/product authority;
- treat a green technical suite as operator acceptance.

## Status model

Every product requirement/decision uses one of:

- `approved` — explicit operator decision and active product truth;
- `recorded_repo_truth_pending_confirmation` — supported by repository material but awaiting operator ratification;
- `open_operator_decision` — product meaning intentionally unresolved;
- `proposed` — engineering/agent proposal only;
- `rejected` — explicitly outside active product;
- `superseded` — replaced by newer approved intent.

Only `approved` requirements may define new product behavior.

## Product Recovery rule

While PRODUCT-RECOVERY-001 is active, primary-path work should improve the approved cold-to-application journey rather than add new unrelated machinery.

A Product Recovery change must preserve current approved boundaries and map to approved PRD/PD/PA anchors. If the current implementation cannot satisfy the product contract, implementation is the recovery target — the product contract is not rewritten merely to make the implementation look complete.

The canonical active plan is `docs/planning/active/product_recovery_001.md`.

## Current acceptance layers

1. **Technical correctness** — code/tests/migrations/build.
2. **Product contract conformance** — approved PRD/PD/PA behavior.
3. **Runtime evidence** — local DB/live employer/provider proof when relevant.
4. **Operator acceptance** — the visible result is genuinely useful.

DEMO-001 demonstrated that layer 1 alone is insufficient.

## Release history

GitHub Releases provide product-facing change history. They do not redefine the product contract.

Release notes should document visible features, bug fixes, known limitations and operator proof. Commit history remains engineering detail.

Current first checkpoint: `v0.1.0-demo.1`.
