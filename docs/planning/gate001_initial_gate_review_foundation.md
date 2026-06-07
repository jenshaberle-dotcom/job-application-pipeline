# GATE-001 Initial Gate Review Foundation

Status: Planned implementation baseline
Safety zone: SZ2_EVIDENCE_AND_GATES

## Purpose

GATE-001 closes the next measured maturity gap after CAND-001. CAND-001 can persist validated origin URLs into `candidate_url`; EO-002E then reports `initial_gate_review` as the next missing step. GATE-001 turns that missing step into a dry-run-first initial gate review flow.

## Scope

GATE-001 evaluates and optionally writes only early employer-origin gate reviews:

- `source_discovery`
- `technical_reachability_gate`
- `risk_gate`

It does not perform detail evidence discovery, connector registration, source activation, scheduler changes, Bronze/Silver writes or Türsteher changes.

## Boundaries

- Dry-run first.
- Explicit `--apply` is required for gate-review writes.
- HTTP probing is bounded.
- Private, local and reserved hosts are blocked before probing.
- Candidate URLs must already be persisted by CAND-001 or equivalent reviewed state.
- Downstream detail evidence discovery remains a separate follow-up.

## Expected next state

When the persisted origin URL is reachable, career-like and no strong risk marker is found, GATE-001 should pass the initial gates and recommend `run_detail_evidence_discovery_plan`.
