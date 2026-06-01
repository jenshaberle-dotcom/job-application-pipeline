# S7A Gold Market Coverage & Candidate Lifecycle Foundation

## Purpose

S7A introduces the first Search Intelligence Gold read models. The goal is to stop the UI and review tools from re-interpreting raw gate, learning and connector-planning tables independently.

Gold is the dashboard-facing layer for product decisions:

- Which employer-origin candidates exist?
- Which candidates are active controlled sources?
- Which candidates are blocked, approval-ready or under high FN pressure?
- Which bounded aggregator scopes are fresh, saturating or actionable?
- Which approval decisions are waiting for Jens?

## Boundary

This foundation is read-only.

It does not crawl sources, mutate search profiles, activate sources, write Bronze records, change scheduler state or execute connector generation.

## Gold Views

### `gold_candidate_lifecycle_status`

One row per employer-origin candidate. It combines candidate metadata, gate progress, first blocking gate, latest FN pressure, latest connector-generation plan, latest connector-build request and search-term suggestion counts.

Main UI use:

- Connector & Candidate workspace
- Demo chain
- candidate detail panels
- blocker diagnostics

### `gold_market_coverage_summary`

One summary row for the dashboard. It contains counts for candidates, active controlled sources, blocked candidates, approval backlog, high FN pressure, recent vocabulary observations and latest novelty state.

Main UI use:

- Dashboard KPI cards
- market coverage summary
- morning status check

### `gold_approval_queue`

One row per approval-relevant item. It surfaces connector build approvals and gate reassessment items as user-facing decisions.

Main UI use:

- Approval workspace
- explicit Jens decision queue

### `gold_source_health_summary`

One row per candidate source. It provides a first operational health/readiness summary for origin candidates and active controlled sources.

Main UI use:

- Heartbeat & Health tab
- connector/source review

## Design Notes

False-negative risk is presented as FN pressure in dashboard contexts. This avoids confusing market-coverage pressure with technical source failure.

S7A intentionally creates views rather than materialized tables. The current data volume is small, the logic is still evolving, and read-only views keep the layer explainable and easy to refactor before cloud/productization.

## Next Step

After S7A, the Search Intelligence Control Center should read these Gold views instead of stitching together semi-aggregated agent state directly.
