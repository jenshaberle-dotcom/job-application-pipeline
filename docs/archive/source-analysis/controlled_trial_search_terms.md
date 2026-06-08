# Controlled Trial Search Terms

S5F turns guardrailed search-strategy recommendations into bounded trial terms.

## Purpose

The project prioritizes reducing false negatives over avoiding every bounded false positive, but avoids creating new historical burden. Trial terms are therefore scoped, expiring, measurable and rollbackable.

## Boundary

Controlled trial terms are not permanent search-profile mutations.

They do not:
- activate sources
- register connectors
- change schedulers
- write Bronze rows by themselves
- use CSV/Excel/export files as inputs

## Workflow

1. `search_strategy_recommendations` identifies a bounded trial candidate.
2. `run_controlled_trial_search_term_agent` previews and optionally applies the trial.
3. `search_strategy_trial_terms` stores active bounded trials.
4. `record_trial_search_term_outcome` records observed outcomes.
5. Later promotion/rollback logic may use those outcomes.

## Autonomy stance

The system may become more autonomous over time, but only inside guardrails:
- expiry date
- max result volume
- max noise rate
- explicit evidence
- rollback path
- audit trail

Current default: manual approval token for pending recommendations. Auto-eligible recommendations can be applied only with explicit `--allow-auto-eligible`.
