# S7O — Connector Build Candidate Selection / Build Queue

## Purpose

S7O turns the latest S7N connector-feasibility evidence into a build-planning queue. The goal is to make the next action visible before generating connector artifacts:

- build candidate recommended,
- origin URL repair required,
- sample-job/detail evidence review required,
- renewed origin discovery required,
- or continuation of an existing build flow.

This prevents the project from jumping directly from "a page looks reachable" to "build a connector". The queue is a product-quality decision layer between feasibility probing and approval-gated connector generation.

## Implemented Gold Views

### `gold_connector_build_candidate_queue`

One row per candidate with latest feasibility evidence. It combines:

- latest `connector_feasibility_review_items`,
- candidate lifecycle context from `gold_candidate_lifecycle_status`,
- existing build-request state,
- URL-quality feedback,
- structural/job-detail evidence counts,
- and a derived `queue_action`.

Important actions:

| Queue action | Meaning |
| --- | --- |
| `build_candidate_recommended` | Feasibility probe found a reachable origin source and concrete job-detail evidence. Prepare build planning. |
| `origin_url_repair_required` | Feasibility probe found a likely replacement URL, for example `.jsp` → `.html`. |
| `sample_job_review_required` | Job-list structure exists, but concrete detail evidence is missing. |
| `origin_source_discovery_required` | Origin URL is missing or not reachable. Discovery/URL review must happen before build planning. |
| `continue_existing_build_flow` | A build request or artifact path already exists. Do not create a duplicate queue path. |

### `gold_connector_build_queue_summary`

One summary row for UI/dashboard and daily status checks.

## Boundary

S7O is read-only. It does not:

- build connector artifacts,
- approve connector build requests,
- register connectors,
- activate sources,
- write Bronze records,
- change scheduler configuration,
- use CSV/Excel/export files as pipeline input.

## Why This Matters

S7N made evidence quality visible. S7O makes the next build-planning decision visible. This is the missing bridge between "we found sample-job evidence" and "we are allowed to create connector artifacts under an approval gate".

For the current S7N result, the expected interpretation is approximately:

- enercity: new build candidate recommended,
- HDI: continue an existing build/artifact flow instead of creating a duplicate queue path,
- Finanz Informatik: monitor as an already active controlled source,
- adesso: origin URL repair required,
- Deutsche Bahn: renewed origin discovery required,
- Ratiodata: sample-job/detail evidence review required.

Lifecycle state intentionally overrides raw feasibility. A likely-feasible source is not always a new build candidate if it already has an active source or an existing build/artifact flow.

## Next Step

After S7O, the Control Center can load this queue directly and surface build candidates, repair candidates and detail-review candidates as separate UI groups. Connector artifact generation should still remain behind explicit approval gates.
