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

## StepStone / Aggregator Interaction

This workspace does not change StepStone acquisition behavior.
StepStone remains a bounded aggregator-discovery signal with feed-forward suppression of known employer-origin
candidates before Bronze persistence.

The workspace may show candidates that were discovered through aggregator signals, but it does not read StepStone,
change StepStone filters, or write discovery snapshots by itself.


## 05A Clean & Balanced Design Alignment

The workspace follows the project's **Sweet Spot — Balanced Intelligence** direction, specifically the cleaner 05A dashboard variant rather than the more cinematic 05B variant.

Design rules for this approval surface:

- use a deep-ocean/navy background with restrained cyan accents
- prefer compact scan-first cards over large raw developer output blocks
- expose human-readable labels such as `Review required`, `Monitoring` and `Ready to build` before raw machine state
- show gate progress as a progress bar and chips instead of only `passed/manual/blocked/total` counters
- keep raw gate evidence collapsed until the user actively reviews a candidate
- preserve a boring, robust local HTML implementation without a frontend framework until the approval workflow justifies one

The UI is intentionally close to the intended dashboard language so product feel can be judged early while the backend gates are still evolving.
