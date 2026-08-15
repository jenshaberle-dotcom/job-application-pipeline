# Recurring connector shadow execution envelope

Status: LLM-BOOST-001 provider-free execution hardening / Issue #544  
Parent authority: Issue #522

## Purpose

The recurring connector surface now has three separate deterministic gates before any external stage may even be attempted:

1. execution-aware observation truth establishes a real cross-execution delta;
2. `recurring_shadow_selection.py` binds that delta to the exact current evidence hash/identity and applies the recurring economics policy;
3. `recurring_shadow_execution.py` bounds any later shadow-only external execution.

The execution envelope is deliberately product-neutral. It can measure whether a provider/model hypothesis was useful, how much it cost and how long it took, but provider output does not become product truth.

## Input authority

`execute_recurring_shadow()` accepts an already-built `RecurringShadowSelection` plus its exact current `RecurringEvidenceRecord`.

If the selection is not shadow-sample eligible, no stage callback or validation callback is invoked. This preserves all prior gates: baseline, unchanged, contract boundary, missing execution/evidence and other fail-closed states cannot escape through the execution layer.

The envelope also verifies that the economics fingerprint still equals the current evidence fingerprint, the plan surface is `recurring_connector`, and no upstream object claims product authority.

## Canonical stage order

The envelope reuses the existing `BoosterPlan` stage order. It does not define a second cascade.

- `deterministic`: already completed before shadow execution; recorded with zero external requests;
- `tavily`: invoked only when the canonical plan marks it eligible;
- `luna_medium`;
- `terra_medium`;
- `sol_medium`;
- `luna_max`;
- `deep_evidence`: residual-evidence marker only in this envelope; no provider callback.

Ineligible planned stages remain explicitly skipped.

## Provider output is a hypothesis

An injected stage callback returns `RecurringShadowHypothesisObservation`:

- whether a request was actually attempted;
- provider/model status;
- a JSON-compatible hypothesis payload;
- observed estimated cost and latency;
- optional provider/model/response metadata;
- `product_authority=false`.

Only a SHA-256 fingerprint and top-level field names from the hypothesis are retained in stage evidence. The envelope does not promote the hypothesis into lifecycle, ranking, application or product state.

An eligible stage that returns `request_attempted=false` fails closed even if it reports no other effects. A non-attempted stage that reports a payload, latency or spend also fails closed.

## Independent deterministic validation

Provider output cannot self-declare success. A separate injected deterministic validator receives the planned stage, the hypothesis and the exact current evidence record.

It returns only:

- `validated_rescue`;
- `progressed`;
- a deterministic reason code;
- `product_authority=false`.

A product-authority claim by either callback is rejected. `validated_rescue=true` without `progressed=true` is also rejected. A validated rescue stops all later external stages.

## Spend and duplicate controls

The existing `RecurringOpportunityCostLedger` is shared across executions. Before an eligible callback is invoked, the envelope checks whether the same current fingerprint + stage already has economics evidence. If so, the stage is suppressed before another request can occur and the remaining cascade stops pending genuinely new evidence.

Each eligible provider/model stage can therefore make at most one callback request per fingerprint/stage through this envelope.

Observed nonnegative spend is retained even when an attempted provider stage later fails closed, because incurred cost remains real economics evidence.

Model-stage cost must not exceed the canonical `hard_cost_ceiling_usd` from `llm_booster_policy.py`. Over-ceiling spend fails closed before deterministic validation and stops the remaining cascade.

## Fail-closed boundaries

The envelope stops the remaining cascade when it observes, among other cases:

- provider or validator product-authority claims;
- negative cost or latency;
- an eligible stage that reports no attempted request;
- effects reported for a non-attempted request;
- attempted provider status other than `completed`;
- invalid/non-JSON hypothesis payload;
- model hard-cost ceiling violation;
- invalid deterministic validation state;
- a duplicate-economics race after callback execution.

No fallback loosens these conditions.

## Product-neutral output

`RecurringShadowExecution` and all stage evidence remain economics/validation evidence only:

```text
product_writes = 0
product_authority = false
```

The module contains no built-in provider client, network call, database access, scheduler action, connector/source activation, lifecycle transition, ranking, application mutation or product write. External callbacks must be supplied by a separately governed Runtime transport.

## Live promotion boundary

Issue #544 proves only the bounded envelope through synthetic callbacks. It does **not** authorize a live recurring shadow.

Current Runtime truth still has no genuine execution-correlated cross-execution pair distribution. A live shadow remains blocked until ordinary future ingestion produces truthful changed candidates and a separate Runtime authority explicitly binds provider credentials, budget and evidence transport to this envelope.

Do not force a Daily, synthesize correlation history, replay E.ON or invoke a provider merely to exercise this code path.
