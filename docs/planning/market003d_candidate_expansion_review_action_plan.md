# MARKET-003D Candidate Expansion Review Action Plan

Status: planned implementation block  
Scope: Search Intelligence / candidate expansion review usability

## Purpose

MARKET-003D turns the MARKET-003C candidate expansion review export into a practical human review action plan.

It does not promote candidates. It only makes review work easier to execute by grouping items into buckets, assigning review priority, and listing allowed human review actions.

## Boundary

This block is review-only and export-only.

It must not:

- create employer-origin candidates
- write promotion decisions
- write gate decisions
- activate connectors
- mutate Bronze, Silver or Gold
- change scheduler state
- treat the action plan as an apply command

The action plan is not a pipeline input. It is an operator-facing review artifact.

## Review Buckets

The action plan may classify review items into:

- `candidate_expansion_human_review_queue`
- `known_candidate_context_queue`
- `identity_gap_queue`
- `insufficient_evidence_context_queue`

These are work queues for a human reviewer, not state transitions.

## Allowed Review Actions

Allowed actions are deliberately non-mutating, for example:

- `inspect_company_identity`
- `collect_origin_url_evidence`
- `collect_detail_page_evidence`
- `confirm_known_candidate_context`
- `park_as_insufficient_evidence`
- `request_assumption_review`

Disallowed actions are explicitly recorded on every item:

- `create_candidate`
- `write_gate_decision`
- `activate_connector`
- `mutate_bronze_silver_gold`
- `change_scheduler`

## Command

    python scripts/run_market003d_candidate_expansion_review_action_plan.py

Default input:

    exports/market003c_candidate_expansion_review/market003c_candidate_expansion_review.json

Default output:

    exports/market003d_candidate_expansion_review_action_plan/

Expected outputs:

- `market003d_candidate_expansion_review_action_plan.json`
- `market003d_candidate_expansion_review_action_plan_items.csv`
- `market003d_candidate_expansion_review_action_plan.md`

## Next Step

A future explicit workflow may add a human-confirmed promotion proposal or approval UI. That future workflow must be separate, auditable, dry-run-first, and still must not silently create candidates.
