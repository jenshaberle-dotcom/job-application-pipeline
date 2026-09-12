# F3 — Bronze -> Silver -> Gold Truth/Lifecycle Hardening

Status: ACTIVE — implementation/product proof complete; final exact-head qualification pending
Target desktop release: 1.0.24
Branch: `agent/f3-truth-lifecycle-hardening`
Base: `main@fb06e1191ae044d0c0547e9136c7860b097bdf5b`

## Purpose

Make downstream vacancy truth resistant to stale, dead and duplicate vacancies regardless of upstream source family. Product and Control Center consume upstream lifecycle/identity truth instead of relying on presentation-only repair.

## Entry gate

F2 is operator-accepted on installed Desktop v1.0.23. The operator verified the two VALUNY vacancies in `All jobs`, VALUNY `ACTIVE · LAST RUN 2 JOBS`, and `Open original` resolving to the real VALUNY posting. `CR-F2-001` is CLOSED.

## Residual ledger at current F3 checkpoint

### CR-F0-001 — FI Origin alias identity duplication — CLOSED technically / operator confirmation pending with F3

Migration `109_create_canonical_vacancy_identity_truth.sql` moves safe vacancy identity into Gold truth without deleting or rewriting Bronze/Silver history. `gold_vacancy_identity` retains every member and selects one representative through the generic hierarchy:

1. strong same-Origin-host + labelled/schema vacancy identifier;
2. exact page-declared canonical Origin URL;
3. bounded same-run detail equivalence for generic Origin aliases only when structured detail evidence is exactly equal, observed URLs differ, locale-neutral paths agree, and strong identifiers do not conflict;
4. exact observed Origin URL;
5. isolated Silver identity.

No employer allowlist, global `/de/` stripping, title/company fuzzy match, Levenshtein or Soundex authority exists.

Real persisted acceptance run `34711951430` on exact head `3bbdba2bf7f0ca8e729a772132030ce13be77eeb` PASS:

- migration 109 tracked, checksum-clean, pending migrations `0`;
- FI identity members: `58`;
- FI canonical duplicate groups: `5`;
- strong identifier groups: `2` (`E362/B`, `420/B`);
- bounded same-run detail-equivalence groups: `3`;
- each group exposes exactly one representative while all members remain auditable;
- Product-visible FI rows: `19` with no remaining `/de/`/non-`/de/` alias residual in current review.

The durable F3 acceptance now additionally requires presentation-layer duplicate repair to remain `0`, proving that Product/Control Center receives canonical upstream identity rather than relying on UI cleanup.

### CR-F1-001 — fresh company -> F1 discovery -> CAND-001 persistence — OPEN / carried

The downstream persisted-source path is proven, but a fresh-company identity has not yet been product-proven end-to-end through F1 discovery, CAND-001 persistence, proof and activation. F3 does not change company discovery/persistence, so this residual remains visible and does not force unrelated F3 work.

Close opportunistically only if later work naturally touches that path; otherwise carry to its next named checkpoint / campaign-end decision.

### CR-F2-001 — positive delivery/Product closure — CLOSED

Closed by exact-head F2 real acceptance, merge/release v1.0.23, automatic local deployment, and installed operator acceptance. It is not carried into F3.

## Implemented F3 truth boundary

Migration 109 introduces canonical upstream identity and makes both `gold_current_job_opportunities` and `gold_product_v1_job_readiness` consume only the representative vacancy while preserving all historical/alias Silver members for audit.

Lifecycle truth remains evidence-driven through `gold_job_lifecycle_health`. Real F3 acceptance proves the product database currently contains:

- `431` `stale_needs_refresh` audit rows;
- `5` `inactive_confirmed` audit rows;
- `16` lifecycle source families;
- at least `1` multi-location Silver job;
- `0` non-current rows leaking into `gold_current_job_opportunities`;
- `0` sensor-only or non-current rows leaking into normal Product review.

The last green pre-cleanup real Product payload contained `65` current review jobs. Final exact-head acceptance must re-prove these invariants after workflow/docs cleanup; counts may legitimately move with new real observations, but the invariants may not weaken.

## Frozen F3 scope / acceptance

- current vacancies remain visible;
- stale/inactive vacancies stay out of current review while history remains auditable;
- market sensors remain discovery/freshness evidence only;
- known safe aliases collapse generically upstream;
- multi-location does not create a second vacancy identity;
- presentation receives already-canonical Product rows and performs no duplicate repair;
- `CR-F0-001` remains closed by exact-head regression evidence;
- `CR-F1-001` remains visible until separately closed/reclassified.

## Remaining F3 sequence

1. Run durable `F3 truth/lifecycle acceptance` on the final branch head.
2. Require exact-head Pipeline CI, Ruff/Full Suite/React, Windows Control Center contract and re-entry identity PASS.
3. Keep PR #864 Draft until all exact-head qualification is green.
4. Merge the exact qualified head, allow automatic v1.0.24 release, and require automatic local deployment.
5. Perform installed operator acceptance before F4 starts.

## Installed F3 operator acceptance

- About reports v1.0.24 and the expected source revision;
- current vacancies remain visible;
- the known Finanz Informatik aliases are no longer duplicated in `All jobs`;
- stale/inactive rows are absent from current review while history/audit remains available;
- market-sensor-only rows stay out of normal review;
- multi-location representation remains one vacancy;
- no regression of the previously accepted VALUNY F2 path.
