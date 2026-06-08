# A1 Multi-Origin Evidence Discovery with Explainable Confidence

## Problem

HDI exposed a propagated upstream defect: the system can stop at the detail-evidence gate even when relevant job evidence exists on a different plausible origin/detail host. The known example is `job.hdi.group`, while the persisted candidate URL may point at `careers.hdi.group`.

The correct conclusion is not necessarily "no evidence exists". The correct conclusion may be one of:

- concrete evidence accepted
- all plausible paths rejected with reasons
- manual review required
- implementation gap because a plausible source/detail pattern was found but the current extractor cannot validate it

## Rule

The system must discover and evaluate multiple plausible origin/detail URL candidates per employer-origin company before it rejects or blocks the detail-evidence gate.

Manual evidence entry is only a debug/regression/override path. It must not be the normal workflow.

## Research and practice principles

This design follows established ideas from focused crawling, vertical search and web data extraction:

- relevant pages can be reached through hub/listing pages and through adjacent hosts
- search queries are valid discovery signals when they are bounded and then validated by probing/extraction
- heterogeneous career sites require page-type and URL-pattern classification
- unsupported extraction must be treated as a capability gap, not as proof that no evidence exists
- positive and negative decisions both require provenance, checked paths, rejection reasons and confidence

## A1 behavior

The detail-evidence repair agent now considers:

- persisted candidate URL
- previous gate evidence URLs
- plausible sibling origin hosts derived from the candidate base domain
- external search-engine discovery queries, bounded by query and result limits
- SuccessFactors-like detail URL patterns such as `/job/<slug>/<id>-<locale>/`

The evidence payload records:

- `decision_taxonomy`
- `confidence_score`
- `confidence_reason`
- `checked_origin_candidates`
- `planned_search_queries`
- `requested_search_queries`
- `detail_assessments`
- `rejected_urls`

## Decision taxonomy

- `accepted`: concrete detail evidence with profile and target/location signals was validated
- `manual_review_required`: no sufficient evidence was validated and the failure cannot be interpreted as final rejection
- `implementation_gap`: plausible job-detail candidates were found, but the current extractor/signal logic could not validate them completely
- `rejected`: used for individual URL assessments where rejection is justified by checked evidence

## HDI regression expectation

For HDI, the system must not stop after only checking `careers.hdi.group`. It must include plausible job-detail candidates such as `job.hdi.group` and SuccessFactors-like URL patterns in the discovery/evidence process.

A known relevant class of URL is:

`https://job.hdi.group/job/Data-&-Analytics-Engineer-%28Long-Tail%29/720-en_US/`

The agent should either validate such a page as evidence or produce a precise implementation-gap/manual-review decision showing which paths were checked and why validation failed.

## Boundary

This A1 change does not register connectors, activate sources, write Bronze records, mutate scheduler configuration or persist raw HTML. External search discovery is bounded and the retrieved URLs still pass through reachability, domain plausibility, page classification and signal validation.
