# S7N Connector Feasibility + Sample Job Probe

## Purpose

S7N validates whether selected employer-origin candidates are ready for connector build planning. It sits after Origin Source Discovery and before the approval-gated connector build path.

The goal is not to build a connector. The goal is to answer whether the selected origin URL appears technically and semantically useful enough to justify connector build work.

## Boundary

The probe is intentionally bounded:

- no connector build
- no connector registration
- no source activation
- no Bronze writes
- no scheduler changes
- bounded HTTP read only
- no pagination
- no deep crawling

## Inputs

The probe reads employer-origin candidates from `employer_origin_source_candidates`.

Default scope:

- candidates with `candidate_url IS NOT NULL`

Optional scope:

- one `--company-key`
- `--include-missing-url` for portfolio completeness

## Outputs

The probe can persist review results to:

- `connector_feasibility_reviews`
- `connector_feasibility_review_items`

Important item fields:

- origin URL
- HTTP status
- reachability
- inferred page type
- sample job URL count
- feasibility status
- decision
- blocker code
- recommended next action

## Decisions

The probe emits one of the following statuses:

- `likely_feasible`
- `manual_review_required`
- `blocked`
- `missing_origin_url`

`likely_feasible` does not approve registration or activation. It only allows the next build-planning step to create a connector artifact candidate.

## Demo Relevance

This block shows the product chain moving from market evidence to actionable connector work:

```text
Market observation
→ candidate promotion
→ origin URL selection
→ sample job probe
→ connector build planning candidate
→ explicit human approval before registration/activation
```
