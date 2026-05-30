# Employer-Origin Approval Workspace

## Purpose

The Employer-Origin Approval Workspace is a local browser UI for the DB-backed employer-origin agent factory.
It is meant to reduce console overload once candidate discovery, gate review, connector artifact generation,
validation and registration-readiness become too difficult to inspect from command output alone.

The workspace is intentionally small and local-first. It is not a production web application. It is a review and
approval surface for one human user.

## Boundary

The workspace may display and, when explicitly started in write mode, trigger only bounded approval actions.

Allowed UI-triggered write actions:

- approve connector implementation by running the S4A artifact generator with `--write-connector`
- approve connector registration gate by passing the existing `approve_connector_registration` token through the chain
- write a registration execution plan document after final approval

Forbidden actions:

- source activation
- Bronze persistence
- scheduler changes
- connector registration as an implicit side effect
- CSV/Excel/export-as-input workflows
- silent approval inference from successful validation

## Tokens

The workspace uses explicit typed approval tokens:

- `approve_connector_implementation` for writing generated connector candidate artifacts
- `approve_connector_registration` for the final approval gate
- `approve_registration_plan_write` for writing the registration execution plan document

The registration approval token remains unchanged from the S4C final approval gate.

## Usage

Read-only mode:

```bash
python -m scripts.run_employer_origin_approval_workspace
```

Write-enabled approval mode:

```bash
python -m scripts.run_employer_origin_approval_workspace --allow-write-actions
```

Then open:

```text
http://127.0.0.1:8765/
```

## Design Notes

The workspace reuses the existing queue and chain decision logic instead of inventing a second approval model.
That keeps the console workflow and browser workflow aligned:

- the queue still decides the next bounded action
- gates still decide whether a connector may be built
- the user only approves implementation/registration boundary crossings
- controlled activation remains a later, separate step

## Candidate Scaling UX

S4H adds first scaling controls for a larger employer-origin candidate set. The workspace keeps compact cards as
the default representation and adds browser-side navigation backed by the same DB queue state:

- view tabs for all candidates, review-required candidates, approval-required candidates, ready/next-step candidates and active sources
- text search across company name, company key, source candidate, status, next action and current reason
- visible result counts so the user can see how much of the queue is currently filtered
- empty-state messaging instead of a blank candidate list

This is intentionally still server-rendered HTML. There is no frontend build step and no JavaScript dependency.
That keeps the local approval surface easy to run, test and review while moving it closer to the intended product
experience for 40+ employer-origin candidates.

## StepStone / Aggregator Interaction

This workspace does not change StepStone acquisition behavior.
StepStone remains a bounded aggregator-discovery signal with feed-forward suppression of known employer-origin
candidates before Bronze persistence.

The workspace may show candidates that were discovered through aggregator signals, but it does not read StepStone,
change StepStone filters, or write discovery snapshots by itself.

## Visual Design Alignment

The workspace follows the project dashboard direction **05A Sweet Spot — Balanced Intelligence**:

- deep-ocean / navy background with restrained cyan accents
- compact metric cards instead of large raw debug blocks
- human-readable approval language in the primary UI
- machine-state names only in details or tooltips
- progress bars and lifecycle phases instead of raw gate ratios as the primary signal
- no cinematic hero treatment or gaming-style visual overload

The UI should stay close enough to the intended dashboard product that it can be used for early product-feel review,
while still remaining a small local approval surface and not a production frontend.
