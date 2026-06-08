# DETAIL-005 Detail Reporting Contract Cleanup

## Why

DETAIL-002 through DETAIL-004B improved bounded detail-link discovery and evidence strictness. The resulting JSON now contains more useful audit data, but reviewers can still confuse two different evidence layers:

- preliminary `candidate_links` / search-discovered detail candidates
- authoritative `detail_assessments` and `supported_details`

This cleanup makes the report contract explicit before the EO-/Connector-Candidate chain continues.

## Change

- Keep legacy keys for compatibility: `candidate_links`, `detail_assessments`, `details`, `supported_details`.
- Add explicit report-contract keys:
  - `preliminary_detail_candidates`
  - `authoritative_detail_assessments`
  - `supported_detail_evidence`
  - `report_contract`
- Surface separated counts in DETAIL report JSON:
  - `preliminary_detail_candidate_count`
  - `authoritative_detail_assessment_count`
- Keep gate semantics unchanged: only `supported_details` / `supported_detail_evidence` can support a passed `detail_evidence_gate`.

## Boundaries

- No database migration.
- No candidate URL writes.
- No connector registration or activation.
- No Bronze/Silver writes.
- No Tavily/provider behavior change.
- No new market-sensor expansion.

## Impact check

- Discovery: unchanged; candidate collection still happens before validation.
- Evidence: improved report-level separation between preliminary candidates and authoritative validation records.
- Candidate/Gate: unchanged gate decisions; clearer manual-review evidence.
- Connector: no direct connector changes; downstream chain gets clearer JSON for review/debugging.
- Bronze/Silver: unchanged.
- UI/Observability: prepares Operations/STATE views to show Tavily/detail evidence without overclaiming preliminary links as supported jobs.
