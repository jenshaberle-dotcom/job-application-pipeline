# S6B Aggregator Novelty Loop Foundation

## Purpose

S6B turns bounded aggregator exploration into a measurable learning loop.

The goal is not to bypass source limits. The goal is to understand whether a
limited result window is still producing new market knowledge or mostly repeating
already-known companies and vocabulary.

## System Role

S6B sits between Market Evidence and downstream Search Intelligence agents:

Exploration Source → Market Evidence → Aggregator Novelty Loop → Candidate Review / Gate Reassessment / Search-Term Trial Review

It answers these questions:

- Which observed companies are already known employer-origin candidates?
- Which observed companies are unregistered candidate backlog?
- Which companies are newly observed compared with the previous persisted cycle?
- Which terms are already known company vocabulary?
- Which company-term pairs are newly observed compared with the previous persisted cycle?
- Is the current bounded query still useful or becoming saturated?

## Boundary

S6B is a review and learning layer only.

It does not:

- paginate StepStone or other aggregators
- increase hard source limits
- mutate search profiles
- activate sources
- write Bronze records
- register connectors
- change scheduler behavior
- use CSV/Excel/export files as pipeline input

Human-readable reports are review artifacts. PostgreSQL stores process state.

## Core Tables

- `aggregator_novelty_snapshots`
- `aggregator_novelty_items`

Snapshots store per-cycle novelty and saturation metrics. Items store the
company-, term- and candidate-reassessment-level observations that explain the
snapshot.

## Metrics

Important fields:

- `evidence_count`
- `distinct_company_count`
- `unregistered_company_count`
- `known_candidate_company_count`
- `newly_observed_company_count`
- `repeated_observed_company_count`
- `reassessment_company_count`
- `new_vocabulary_term_count`
- `known_vocabulary_term_count`
- `newly_observed_term_count`
- `repeated_observed_term_count`
- `novelty_score`
- `saturation_level`
- `recommended_action`

## Recommended Actions

S6B can recommend:

- `persist_baseline_then_rerun`
- `review_newly_observed_companies`
- `review_unregistered_company_backlog`
- `rerun_gate_reassessment_for_known_candidates`
- `try_reviewed_trial_terms`
- `pause_or_retire_current_query`
- `continue_bounded_exploration`
- `manual_review`

Recommendations are review signals, not automation approvals.

## Example Commands

Preview current StepStone novelty from existing market evidence:

```bash
python -m scripts.run_aggregator_novelty_loop_agent \
  --source-name stepstone \
  --days 14 \
  --limit 500
```

Persist the reviewed snapshot:

```bash
python -m scripts.run_aggregator_novelty_loop_agent \
  --source-name stepstone \
  --days 14 \
  --limit 500 \
  --reviewed-by jens \
  --write
```

Optionally scope to a specific search term:

```bash
python -m scripts.run_aggregator_novelty_loop_agent \
  --source-name stepstone \
  --search-term "Data Engineer" \
  --days 14 \
  --limit 500
```

## Product Interpretation

S6B intentionally separates registry state from cycle novelty. A company can be
`unregistered` because it is not yet an employer-origin candidate, while still
being a repeated observation from earlier cycles. Such a row is candidate backlog,
not fresh discovery.

If a bounded aggregator result repeatedly produces already-observed companies and
already-observed company-term pairs, the query is likely saturated. The correct
response is not broader scraping. The correct response is reviewable strategy
control: pause the query, try already-reviewed trial terms, review the
unregistered candidate backlog, or focus reassessment on known unresolved
candidates.

If newly observed companies or company-term pairs continue to appear across
cycles, the source still contributes to market coverage, vocabulary discovery or
candidate reassessment.
