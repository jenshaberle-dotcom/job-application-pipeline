# Deterministic Connector Builder — evidence-driven layer model

Status: active implementation under #676
Date: 2026-08-28
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

## Current audit boundary

`scripts/run_deterministic_connector_builder_layer_audit.py` runs the layer model against every current distinct Employer-Origin candidate.

The initial audit is diagnostic and read-only:

- DB reads allowed;
- DB writes forbidden;
- provider/LLM/Tavily requests forbidden;
- public network method GET only;
- candidate URL writes forbidden;
- connector materialization/registration forbidden;
- source activation forbidden;
- Bronze/Silver/Product/application writes forbidden.

The audit deliberately reports a `diagnostic_recipe_ready` count. This does not supersede the canonical accumulated strict coverage metric until all historical Runtime deterministic capability classes are integrated into the builder.

## Build transition

After the layer audit identifies the actual population bottlenecks, automatic materialization may be enabled only for candidates whose complete recipe is evidence-backed. Materialization must compile generic capability references and evidence bindings, not create company-name success branches.

The intended steady state is:

`candidate -> layer evaluation -> generic capability composition -> strict proof -> recipe -> connector materialization`

not:

`candidate -> handwritten employer connector -> patch until green`.
