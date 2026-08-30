# ACQ-GENERALIZATION-90 — deterministic full-population coverage target

Status: active  
Date: 2026-08-30  
Owner issue: `#676`  
Active re-entry: `docs/planning/active/acq_generalization_90_reentry.md`

## Primary metric

Strict functioning deterministic product coverage across all current distinct
Employer-Origin candidates remains the only primary product metric.

Current denominator:

- distinct candidates: `65`;
- historical connector-present cohort: `40/65`;
- strict functioning deterministic product coverage: `36/65 = 55.4%`;
- minimum passing numerator at N=65: `59` (`59/65 = 90.8%`).

The denominator must not be reduced by suppressing or reclassifying valid candidates.
Diagnostic READY/`recipe_ready`, provider recognition or audit evidence never counts as
product coverage by itself.

## Product success contract

A candidate enters the numerator only after a materialized deterministic connector path
passes unchanged strict genuine-job acquisition proof under existing employer/source
authority and side-effect boundaries.

No deterministic hardening slice may:

- add company-specific success branches when a generic class is possible;
- guess tenant/site/job IDs, routes, query values or POST bodies;
- weaken proof or employer/source authority;
- convert diagnostic evidence directly into product coverage;
- require LLM/Tavily/provider search for the deterministic target path.

## Qualified deterministic progress

Retained generic capabilities:

- balanced Origin V2;
- provider/inventory V3;
- Workday CXS deterministic acquisition;
- evidence-bounded portal delegation;
- Builder V5 monotonic residual rewrite/composition.

V5 live replay remains:

- READY `22/65` diagnostic;
- Workday promotions `1` (`clarios_germany`);
- portal promotions `0`;
- residuals: Origin `8`, Origin reachability `1`, Inventory `15`, Detail `16`, Proof `3`;
- product coverage unchanged `36/65`.

## Inventory residual conclusion

The strongest SuccessFactors inventory pair (`adesso`, `hannover_ruck`) was measured and
did not prove one common route. Hannover Re exposes an explicit GET `/search/`; adesso
does not. A universal SuccessFactors `/search/` rule is therefore rejected.

## Detail residual evidence

The 16 Detail residuals completed a bounded live audit with:

- `45` GETs total;
- `0` replay errors;
- `0` provider requests;
- `0` DB writes;
- `0` query values persisted.

Raw diagnostic classes were `8 unknown-query-ID / 5 unclassified-jobish / 3 form-driven`.
A zero-network semantic identifier reclassification then removed broad `id` substring
noise and produced the qualified split:

- `10` unclassified-jobish;
- `5` form-driven;
- `1` semantic unknown query-ID: IPH `weobjectid x12`.

The single IPH case is real but is not prioritized above a reusable population class.
The 10-case jobish cohort is numerically larger but not yet structurally bounded enough
to justify global vocabulary widening.

## Current deterministic frontier

The next measurement gate is the `5` form-driven Detail residuals.

PR `#693` merged a zero-network form carrier audit at
`e8aa41179e6618fa96b33e82ec57dd51edd1a0f5` after Pipeline CI `#906` and Re-entry
`#1507` succeeded.

The audit examines only already-recorded structure:

- HTTP method;
- action host/path/query-key shape;
- field names;
- provider hints.

It performs:

- network requests `0`;
- form submissions `0`;
- form/query value reads `0`;
- DB/provider/LLM/Tavily requests/writes `0`;
- connector materialization `0`.

GET search/filter forms remain separate from semantic-ID detail carriers. POST forms are
never executable authority from this measurement alone.

Canonical next command:

```bash
.venv/bin/python -m scripts.run_deterministic_detail_form_carrier_audit \
  --reclassification /tmp/deterministic_detail_identifier_reclassification_v1.json \
  --output /tmp/deterministic_detail_form_carrier_audit_v1.json
```

## Decision order

1. Run the zero-network form carrier audit and require exactly `5` input cases.
2. Prefer a cross-employer carrier only if method/action/field semantics repeat under one
   bounded fail-closed contract.
3. If form structures split, do not force a form adapter; move to a focused bounded audit
   of the 10 unclassified-jobish cases.
4. Do not prioritize IPH `weobjectid` unless broader evidence makes it a reusable class.
5. Continue deterministic hardening until no reasonable generic bounded class remains.
6. Materialize only stable evidence-backed recipes and update `36/65` only after unchanged
   strict E2E product proof.
7. Only exhausted residuals may enter the later booster path.
