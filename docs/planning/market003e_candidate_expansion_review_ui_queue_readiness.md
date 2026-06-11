# MARKET-003E Candidate Expansion Review UI/Queue Readiness

Status: planned implementation block  
Scope: Search Intelligence / review UI readiness / read-only queue model

## Purpose

MARKET-003E turns the MARKET-003D candidate expansion review action plan into a read-only UI queue model.

The goal is to make the future Candidate Expansion Review UI easier to build without introducing write behavior too early.

This block produces queue cards, lanes, UI statuses, priority ranks, evidence badges, and a frontend capability contract.

## Boundary

This block is read-only and export-only.

It must not:

- create candidates
- promote candidates
- write gate decisions
- activate connectors
- mutate Bronze, Silver or Gold
- change scheduler state
- write database state
- add frontend write actions

The generated queue model is display material only. It is not a pipeline input and not an apply command.

## Queue Lanes

The queue readiness model may expose these read-only lanes:

- `needs_human_candidate_expansion_review`
- `known_candidate_context_review`
- `identity_resolution_needed`
- `parked_market_context`
- `unclassified_review_context`

These lanes are UI grouping concepts, not state transitions.

## UI Statuses

Cards may receive statuses such as:

- `review_required`
- `context_review`
- `blocked_identity_gap`
- `insufficient_evidence`
- `blocked_unclassified_input`

These statuses describe review display state only. They are not gate decisions.

## Frontend Contract

Allowed frontend capabilities:

- display queue lanes
- filter by lane, status, priority, or evidence gap
- open a read-only review dialog
- copy review context
- export queue cards

Disallowed frontend capabilities:

- candidate creation button
- candidate promotion button
- gate approval button
- connector activation button
- scheduler execution button
- database write action

A future write workflow requires a separate explicit work item and must remain dry-run-first and approval-gated.

## Command

    python scripts/run_market003e_candidate_expansion_review_queue_readiness.py

Default input:

    exports/market003d_candidate_expansion_review_action_plan/market003d_candidate_expansion_review_action_plan.json

Default output:

    exports/market003e_candidate_expansion_review_ui_queue_readiness/

Expected outputs:

- `market003e_candidate_expansion_review_ui_queue_readiness.json`
- `market003e_candidate_expansion_review_ui_queue_cards.csv`
- `market003e_candidate_expansion_review_ui_queue_readiness.md`

## Next Step

After MARKET-003E, a future UI block may render these cards in the Control Center or Review Queue.

That future UI block should still start read-only. Any write action such as creating a candidate, writing a gate decision, or activating a connector must be a separate explicitly approved workflow.
