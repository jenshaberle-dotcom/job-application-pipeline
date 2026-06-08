# REPAIR-001 Stop Review and Repair Candidate Audit

Status: reference contract
Scope: read-only review of stopped employer-origin candidates after STOP-002

## Purpose

REPAIR-001 turns the STOP-002 taxonomy into an operational audit surface. It does
not repair candidates by itself. It reads current candidate and gate-stop state,
classifies stop signals through the shared taxonomy, orders repair candidates,
and emits dry-run/apply command suggestions for the next bounded repair step.

The current implementation extends `scripts/run_pipeline_stop_reassessment_agent.py`.
That agent existed before STOP-002, so REPAIR-001 deliberately strengthens it
instead of creating a second stop-audit tool.

## Boundary

REPAIR-001 Stage 1 is read-only:

- no candidate status write,
- no candidate URL write,
- no gate review write,
- no evidence write,
- no connector artifact write,
- no connector registration,
- no source activation,
- no scheduler change.

The report may include Stage 2 commands, but those commands are plans. Running
or applying them remains outside the REPAIR-001 audit boundary and must respect
the called agent's own dry-run/apply contract.

## Report contract

Each assessment contains:

- original stop signals,
- dominant STOP-002 stop category,
- dominant lifecycle class,
- dominant repair strategy,
- safety zone,
- false-negative risk,
- confidence reason,
- recommended action,
- optional Stage 2 dry-run/apply plan.

The report summary also contains counts by lifecycle class, stop category, repair
strategy and safety zone. The `repair_audit_order` field sorts candidates so
false-negative-risk stops appear before generic manual-review or terminal buckets.

## Ordering principle

The audit order is intentionally not a business-priority score. It is a repair
triage order:

1. `false_negative_risk_stop`,
2. `repairable_stop`,
3. `review_stop`,
4. `taxonomy_gap_stop`,
5. `good_stop`,
6. `not_stop`.

Within those buckets, higher false-negative risk is shown first. This avoids the
old failure mode where a generic `manual_review_required` or `abort_documented`
state could hide a concrete repairable URL/detail-evidence gap.

## Usage

Portfolio audit:

    python -m scripts.run_pipeline_stop_reassessment_agent \
      --target-location hannover \
      --reviewed-by jens \
      --write-report \
      --print-stage2-command \
      --benchmark-label repair001_portfolio

Single candidate audit:

    python -m scripts.run_pipeline_stop_reassessment_agent \
      --company-key <company_key> \
      --target-location hannover \
      --reviewed-by jens \
      --write-report \
      --print-stage2-command \
      --benchmark-label repair001_<company_key>

Reports are written under `exports/pipeline_stop_reassessment/` by default.
`exports/` is ignored and is the right place for generated review artifacts.

## Relationship to STOP-002

STOP-002 defines categories and repair strategies. REPAIR-001 consumes them.

If a stop cannot be explained precisely enough by STOP-002, REPAIR-001 must not
invent an optimistic repair path. It should keep the candidate in a taxonomy gap
or review bucket and make the missing classification visible.
