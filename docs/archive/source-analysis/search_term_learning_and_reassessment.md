# S5B Search Term Learning and Reassessment Queue

## Purpose

S5B turns false-negative risk from S5A into an actionable review workflow.

S5A answers:

> Where does market evidence contradict our employer-origin evaluation?

S5B answers:

> What should we reassess, and which search terms should be reviewed first?

The HDI case remains the reference example: external market evidence shows relevant Data/Analytics jobs while the employer-origin candidate is unresolved. The system should not immediately build a connector, but it also must not forget the signal.

## New Review State

### `search_term_suggestions`

Stores suggested terms from false-negative evidence, for example:

- `analytics`
- `business intelligence`
- `data management`

These suggestions are review artifacts only. They do not mutate active search profiles automatically.

### `candidate_reassessment_queue`

Stores open reassessment work items for candidates where false-negative risk should trigger another bounded source/profile review.

The queue is intended for the Approval Workspace and future agents. It is not a connector activation queue.

## Agent

`scripts/run_search_term_learning_agent.py`

Default mode is preview-only:

```bash
python -m scripts.run_search_term_learning_agent --limit 25
```

Write mode persists suggestions and reassessment work items:

```bash
python -m scripts.run_search_term_learning_agent --limit 25 --write --reviewed-by jens
```

## Workspace Integration

The Approval Workspace receives:

- a `Reassessment` tab
- a compact `Reassessment Queue` section
- counts for open reassessment items

This keeps false-negative findings actionable without turning the candidate list into another noisy dashboard.

## Boundaries

S5B does not:

- activate sources
- register connectors
- change schedulers
- mutate active search profiles automatically
- use CSV/Excel/export files as pipeline inputs
- write Bronze jobs

S5B writes only DB-backed review state: proposed search-term suggestions and reassessment work items.
