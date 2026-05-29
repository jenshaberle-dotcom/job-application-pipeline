# Employer-Origin Detail Evidence Repair Agent

## Status

Implemented as S2W candidate workflow.

## Purpose

The detail-evidence repair agent is a bounded self-correction step for employer-origin source candidates.

It is used when earlier gate evidence contains weak or invalid detail URLs such as career overview pages, legal pages or generic job-board roots. Instead of immediately asking for manual work, the agent performs a limited repair attempt:

1. read the current employer-origin source candidate from PostgreSQL
2. read the current gate state from PostgreSQL
3. fetch only bounded seed pages from the same host
4. extract same-domain links
5. reject overview, legal and non-job URLs
6. validate a small number of concrete job-detail pages
7. update the `detail_evidence_gate` in PostgreSQL if concrete evidence is found

## Boundary

The repair agent does not:

- write Bronze rows
- activate a source profile
- register a connector
- enable recurring ingestion
- use browser automation
- persist raw HTML
- use CSV/Excel/export artifacts as inputs

The PostgreSQL gate state remains the source of truth.

## Example

```bash
python -m scripts.run_employer_origin_detail_evidence_repair_agent \
  --company-key hdi \
  --target-location hannover \
  --profile-term "product owner" \
  --profile-term data \
  --profile-term analytics \
  --reviewed-by jens
```

After a successful repair, rerun the connector-candidate agent so `connector_candidate_gate` is recomputed from repaired DB evidence.

```bash
python -m scripts.run_employer_origin_connector_candidate_agent \
  --company-key hdi \
  --reviewed-by jens
```

## Interpretation

S2W makes the agent more useful without weakening gates. It may repair weak evidence, but if it cannot find concrete job-detail URLs with profile and target/remote signals, it stops with `manual_review_required`.
