# Deterministic Connector Builder — evidence-driven layer model

Status: active implementation under #676
Date: 2026-08-29
Primary population target: strict functioning deterministic acquisition >= 90% of all current distinct Employer-Origin candidates.

## Purpose

The deterministic product is not a collection of employer-specific connector implementations. A new Employer-Origin candidate must pass through the same bounded evidence pipeline. Successful generic capabilities compose into a connector recipe; missing capabilities are reported at the earliest evidence-required layer.

The historical 40-case cohort remains a non-regression control. It is not the primary coverage denominator.

## Ordered layers

1. `identity`
   - stable employer key and normalized employer identity.
2. `origin`
   - authorized deterministic employer/career origin, either already persisted or selected by provider-free deterministic origin discovery.
3. `origin_reachability`
   - bounded public GET reaches the selected origin surface.
4. `delegation`
   - only required when observed evidence shows that the job surface crosses an authority/host boundary.
   - supported anchor delegation may pass.
   - explicit but currently unsupported carriers such as ATS iframes or cross-host HTTP redirects fail here when no alternative observed path makes them unnecessary.
5. `provider`
   - only required when an observed ATS/provider family is needed to continue.
   - generic server-rendered or same-origin navigation may make this layer unnecessary.
6. `inventory`
   - a deterministic job inventory or concrete job-navigation path is observed.
   - skipped when the authorized origin is already a concrete strict job detail.
7. `detail`
   - a concrete job detail is reached.
8. `proof`
   - unchanged strict genuine-job proof passes.
9. `recipe`
   - all evidence-required layers are satisfied and a generic connector recipe is compile-ready.

## Layer states

Every layer records both `state` and `required`.

- `PASS`, `required=true`: the layer was required by evidence and succeeded.
- `PASS`, `required=false`: the capability was observed and succeeded, but an already-observed alternate path means it was not necessary for success.
- `SKIPPED`, `required=false`: observed evidence proves the layer is not necessary for this candidate.
- `FAIL`, `required=true`: the earliest evidence-required layer could not be satisfied by the current deterministic stack.
- `NOT_REACHED`, `required=null`: an upstream required failure prevented enough evidence from being gathered to decide whether this later layer would have been required.

A missing or unused optional layer is never counted as a failure. Necessity itself must be evidence-backed; the builder must not invent required layers merely because they exist in the abstract architecture.

## Residual adapter contract

The layer engine and acquisition capabilities are deliberately separate.

The base builder evaluates the generic stack and records the earliest required failure. A reusable deterministic capability may then act as a **residual adapter** only when the current first-failure matches the class it was designed to resolve.

Examples:

- Workday CXS is an `inventory` residual adapter. A successful Workday route also supplies stronger `provider` evidence, so it rewrites the suffix starting at `provider`.
- Evidence-bounded employer -> portal handoff is an `inventory` residual adapter. Because the successful route proves that cross-surface delegation is required, it rewrites the suffix starting at `delegation`.

The shared builder function `rewrite_residual_suffix()` enforces the generic contract:

1. the adapter declares the exact `expected_first_failure` it may handle;
2. the adapter declares the earliest `rewrite_from_layer` whose evidence genuinely changes;
3. every earlier layer is preserved exactly;
4. the adapter must replace the complete canonical suffix in layer order;
5. the rewritten result may become `recipe` READY or may move the failure later;
6. it may **never introduce a first failure earlier than the residual it was asked to resolve**.

This makes monotonicity a builder invariant instead of an adapter convention.

An adapter therefore cannot rescue an `origin` failure by running a downstream provider route, cannot turn a `detail` failure into a newly invented `delegation` failure, and cannot silently overwrite already-qualified upstream identity/origin evidence.

## Ordered composition

Residual adapters are composed in an explicit order. An adapter receives the result of the previous stage and is attempted only when its own declared residual still exists.

Current diagnostic sequence:

```text
V3 base
  -> Workday CXS residual adapter (only if first_failure == inventory)
  -> bounded portal-delegation residual adapter (only if first_failure still == inventory)
  -> remaining residual cohort
```

If Workday promotes a candidate to READY, the portal adapter is not attempted for that candidate. If Workday does not apply or does not prove the job, the assessment remains unchanged and the next compatible residual adapter may inspect it.

The diagnostic request budgets of separate overlays remain explicit and independent. That is measurement instrumentation, not permission for an eventual materialized connector to probe every adapter blindly. Stable recipe materialization must compile only the evidence-backed capabilities needed by that candidate.

## Audit evolution

The audit versions are evidence checkpoints, not separate product architectures:

- V1: initial evidence-driven layer assessment.
- V2: balanced Origin planner A/B.
- V3: existing provider-inventory route composition.
- V4: V3 + strict Workday CXS residual composition.
- V5: V4 + evidence-bounded portal-delegation residual composition under the shared monotonic rewrite contract.

Each version preserves the same candidate population and reports comparable first-failure distributions. Historical results remain immutable comparison evidence; later versions do not rewrite earlier observed cohorts.

## Current audit boundary

The builder audits run the layer model against every current distinct Employer-Origin candidate.

The diagnostic boundary remains read-only:

- DB reads allowed;
- DB writes forbidden;
- provider/LLM/Tavily requests forbidden;
- bounded public network requests only as explicitly declared by the audited capability;
- candidate URL writes forbidden;
- connector materialization/registration forbidden;
- source activation forbidden;
- Bronze/Silver/Product/application writes forbidden.

The audit deliberately reports a `diagnostic_recipe_ready` count. This does not supersede the canonical accumulated strict coverage metric until a connector is materialized and unchanged strict E2E proof establishes product admission.

## Build transition

After the layer audit identifies and qualifies the actual population bottlenecks, automatic materialization may be enabled only for candidates whose complete recipe is evidence-backed. Materialization must compile generic capability references and evidence bindings, not create company-name success branches.

The intended steady state is:

`candidate -> layer evaluation -> residual capability composition -> strict proof -> recipe -> connector materialization`

not:

`candidate -> handwritten employer connector -> patch until green`.
