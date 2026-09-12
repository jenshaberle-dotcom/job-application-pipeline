# F3 — Bronze -> Silver -> Gold Truth/Lifecycle Hardening

Status: ACTIVE
Target desktop release: 1.0.24
Branch: `agent/f3-truth-lifecycle-hardening`
Base: `main@fb06e1191ae044d0c0547e9136c7860b097bdf5b`

## Purpose

Make downstream vacancy truth resistant to stale, dead and duplicate vacancies regardless of upstream source family. Product and Control Center must consume upstream lifecycle/identity truth instead of repairing it only in presentation code.

## Entry gate

F2 is operator-accepted on installed Desktop v1.0.23. The operator verified that the two VALUNY vacancies are present in `All jobs`, VALUNY is `ACTIVE · LAST RUN 2 JOBS`, and `Open original` resolves to the real VALUNY origin posting. Therefore `CR-F2-001` is CLOSED and F3 entry is authorized.

## Inherited residuals

### CR-F0-001 — FI Origin alias identity duplication — OPEN / F3 closure target

The same Finanz Informatik vacancy can still be represented by parallel employer-origin aliases with and without `/de/`. F3 must attempt generic closure through the vacancy identity hierarchy. Forbidden fixes remain: FI-specific branches, global `/de/` stripping, or title/company fuzzy merging.

Mandatory decision: close with regression evidence before the F3 operator checkpoint, or explicitly reclassify with concrete evidence if the generic identity contract is insufficient.

### CR-F1-001 — fresh company -> F1 discovery -> CAND-001 persistence — OPEN / carried

The downstream persisted-source path is proven, but a fresh-company identity has not yet been product-proven end-to-end through F1 discovery, CAND-001 persistence, proof and activation. F3 does not change company discovery/persistence by default, so this residual stays visible and does not force unrelated F3 work.

Close opportunistically only if F3 naturally touches that path; otherwise carry to its next named checkpoint / campaign-end decision.

### CR-F2-001 — positive delivery/Product closure — CLOSED

Closed by exact-head F2 real acceptance, merge/release v1.0.23, automatic local deployment, and installed operator acceptance. Do not carry into F3.

## Frozen F3 scope

- exact current/dead/stale determination from Origin evidence, valid-through/publication and recurring observations;
- market sensors may support discovery/freshness diagnostics but never review authority;
- vacancy identity hierarchy: explicit structured requisition/vacancy identity -> canonical/final Origin identity -> exact canonical Origin URL -> bounded evidence equivalence only when safely proven;
- never merge by title similarity alone;
- multi-location must not fork one vacancy;
- regression cohort across multiple Origin families;
- Product/Control Center consumes upstream truth rather than presentation-only repair.

## Initial implementation order

1. Inventory the current identity/lifecycle authority from Bronze through Silver and Gold and identify presentation-only corrections that must move upstream.
2. Close or explicitly classify `CR-F0-001` using only generic identity evidence.
3. Harden lifecycle truth for current / inactive / stale / unverifiable states across recurring observations and explicit closure evidence.
4. Add a multi-family regression cohort covering current, dead/stale, duplicate-alias, multi-location and sensor-only cases.
5. Prove persisted Bronze -> Silver -> Gold -> Product/Control Center behavior on exact F3 head.
6. Qualify, merge exact tested head, auto-release v1.0.24, auto-deploy, and perform the interactive F3 operator test.

## F3 operator acceptance

- current vacancies remain visible;
- deliberately dead/stale vacancies disappear from current review while history remains auditable;
- market-sensor-only rows stay out of normal review;
- known safe aliases collapse without employer-specific rules or fuzzy-title merging;
- multi-location representations do not create duplicate vacancies;
- `CR-F0-001` is closed or explicitly reclassified;
- all still-open inherited residuals remain visible in the residual ledger.
