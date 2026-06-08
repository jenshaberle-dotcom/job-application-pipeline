# S5C/D Search Intelligence Learning Loop

## Purpose

S5C/D closes the first reviewable learning loop for false-negative search quality.
S5A made blind spots visible, and S5B converted those blind spots into search-term suggestions and reassessment work items.
This block records whether suggested terms actually helped and derives confidence from reviewed outcomes.

## Flow

```text
Market Evidence
  -> False Negative Risk
  -> Search Term Suggestion
  -> Reassessment
  -> Validation Outcome
  -> Confidence Snapshot
```

## Boundary

This is learning and review state only.
It does not mutate active search profiles, activate sources, register connectors, schedule runs, or write Bronze jobs.

## Validation outcomes

- `pending`
- `tested_no_result`
- `tested_found_noise`
- `tested_found_relevant`
- `accepted`
- `rejected`

## HDI reference case

HDI remains the first validation case for the new loop. The system should be able to show that `analytics` was suggested from market evidence and then track whether validating this term produced relevant results.
