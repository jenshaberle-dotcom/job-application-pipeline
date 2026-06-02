# S7J Candidate Promotion Gate

## Purpose

The Candidate Promotion Gate turns market-observed company evidence from S7I into a controlled employer-origin candidate creation workflow.

It closes the gap between:

```text
candidate_expansion_review_items
→ reviewable promotion decision
→ optional discovery-state employer_origin_source_candidates row
→ Origin Source Discovery Gate
```

## Boundary

The gate does not browse the web, build connectors, register connectors, activate sources, write Bronze data, mutate search profiles or change scheduler state.

Candidate creation is explicit. A dry run only explains what would be promoted. Persisting a promotion review and creating candidates require separate flags.

## Why candidate_url becomes nullable

Market observations can identify a company that should enter the employer-origin lifecycle before the project knows the safe origin career URL.

Using a StepStone, LinkedIn or other aggregator URL as `candidate_url` would poison the origin-source evidence. Therefore S7J allows discovery-state candidates with `candidate_url = NULL`. The Origin Source Discovery Gate must later select or reject a concrete HTTPS origin URL.

A partial unique index prevents repeated pending candidates for the same company while still allowing future explicit URL-backed candidates when needed.

## Decisions

| Source decision | Promotion decision | Effect |
|---|---|---|
| `create_candidate_recommended` | `promotion_recommended` | Candidate can be created with explicit approval. |
| `manual_review_required` | `promotion_manual_review_required` | Review source role before candidate creation. |
| `insufficient_evidence` | `promotion_deferred` | Wait for more market evidence. |
| `suppress_as_noise` | `promotion_rejected_noise` | Do not create a candidate. |
| `already_known` / `active_candidate_monitoring` | `promotion_skipped_existing` | Route evidence to the existing candidate. |

## Example commands

Dry run across the latest expansion review:

```bash
python -m scripts.run_candidate_promotion_gate_agent \
  --review-id latest \
  --reviewed-by jens
```

Persist a review without creating candidates:

```bash
python -m scripts.run_candidate_promotion_gate_agent \
  --review-id latest \
  --reviewed-by jens \
  --write-review
```

Create one reviewed discovery candidate:

```bash
python -m scripts.run_candidate_promotion_gate_agent \
  --review-id latest \
  --company-key ratiodata \
  --reviewed-by jens \
  --write-review \
  --create-candidates
```

Batch creation is intentionally explicit and bounded:

```bash
python -m scripts.run_candidate_promotion_gate_agent \
  --review-id latest \
  --reviewed-by jens \
  --write-review \
  --create-candidates \
  --allow-batch-create \
  --max-create 5
```

## Follow-up

After candidate creation, the next step is to run the Origin Source Discovery Gate over the expanded candidate portfolio. Candidates with no safe origin URL remain in discovery/manual-review states and must not proceed to connector build approval.
