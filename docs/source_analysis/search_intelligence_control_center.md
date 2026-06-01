# Search Intelligence Control Center

## Purpose

The Search Intelligence Control Center is a local, DB-backed UI for the current connector lifecycle. It exists because the Search Intelligence agents now produce too much state for comfortable console review.

The UI shows the product chain in one place:

```text
Company discovered
→ Employer-origin candidate
→ Learning / false-negative pressure
→ Origin-source exploration and gate reassessment
→ Approval-gated connector build
→ Connector validation
→ Registration approval
→ Controlled active source
```

## Scope

The control center reads:

- `employer_origin_source_candidates`
- `employer_origin_candidate_gate_reviews`
- `candidate_reassessment_queue`
- `employer_origin_connector_generation_plans`
- `employer_origin_connector_build_requests`

It renders:

- active controlled connectors
- unresolved candidates and their gate/lifecycle state
- connector build approval requests
- connector registration approval opportunities after validation
- a visual lifecycle chain per candidate

## Guardrails

The UI does not create auto-PRs, does not activate sources, does not write Bronze records and does not change schedulers.

Write actions are disabled unless the server is started with `--allow-write-actions`. Even then, destructive or lifecycle-changing actions require exact approval tokens.

Current approval tokens:

- `approve_connector_build` allows S6C to write connector artifacts only.
- `approve_connector_registration` delegates to the existing final approval gate and still does not perform uncontrolled activation.

## Usage

Read-only view:

```bash
python -m scripts.run_search_intelligence_control_center
```

The header includes a **Stop UI** kill switch. It calls the local shutdown endpoint and works in read-only mode as well.

Write-enabled local approval mode:

```bash
python -m scripts.run_search_intelligence_control_center \
  --allow-write-actions \
  --reviewed-by jens
```

Then open:

```text
http://127.0.0.1:8770/
```

## Boundary

This UI is a control surface, not a hidden pipeline input. It reads DB-backed state and executes explicit, token-gated CLI actions only. It must not become a CSV/export-driven handoff.
