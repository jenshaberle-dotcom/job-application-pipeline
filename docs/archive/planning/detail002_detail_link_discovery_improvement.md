# DETAIL-002 Detail Link Discovery Improvement

Status: implemented as bounded DETAIL-001 discovery improvement
Safety zone: SZ2 evidence and gates
Scope: detail-link discovery only

## Why this exists

DETAIL-001 made the detail-evidence stop auditable, but the first runtime result for `hannover_ruck` and `e_on_grid_solutions` showed that the current detail-link discovery still missed concrete job-detail pages.

The most important diagnosis was not a gate-threshold problem. The system had valid origin URLs and passed early gates, but the discovery stage still spent limited search budget on generated synthetic hosts such as `job.e_on_grid_solutions.group` instead of prioritizing the persisted candidate hosts such as `jobs.eon.com` or `jobs.hannover-re.com`.

DETAIL-002 improves the discovery layer without weakening evidence gates.

## Implemented changes

### 1. Persisted-host search query priority

Search discovery now accepts the persisted `candidate_url` and derives high-value search hosts from it.

For example, a candidate URL like:

    https://jobs.hannover-re.com/

now produces early search queries such as:

    site:jobs.hannover-re.com/job data hannover
    site:jobs.hannover-re.com data hannover

before falling back to generic company-name or synthetic company-key queries.

This directly addresses the DETAIL-001 dry-run weakness where generated pseudo-host queries consumed the bounded query budget.

### 2. Embedded detail URL extraction

Many employer-origin portals render job cards dynamically. Static HTML can still include concrete detail URLs inside JSON blobs, inline scripts, or escaped state payloads.

DETAIL-002 adds bounded embedded detail URL extraction for detail-shaped URLs found outside normal anchor tags. The extractor:

- decodes common HTML and JSON escaping
- accepts only URLs that already look like concrete job detail paths
- keeps extraction bounded
- does not persist raw HTML
- still requires the detail validation stage to fetch and validate profile plus target-location or remote evidence

### 3. Evidence observability

Discovery evidence now marks:

    detail_link_discovery_version = DETAIL-002
    embedded_detail_url_extraction_enabled = true

This makes later reports and audits distinguish old DETAIL-001 behavior from improved DETAIL-002 link discovery.

## Explicit non-goals

DETAIL-002 does not:

- weaken `detail_evidence_gate`
- register connectors
- activate sources
- write Bronze/Silver data
- change scheduler or Wave behavior
- persist raw HTML
- treat search-result URLs as sufficient evidence without detail-page validation

## Runtime expectation

After applying this patch, rerun DETAIL-001 in dry-run mode for the same candidates. Expected improvement is not guaranteed for every portal, but the report should show better discovery attempts:

- planned search queries should prioritize real persisted hosts
- rejected/checked URLs should contain fewer synthetic company-key hosts inside the bounded budget
- if embedded or search-discovered detail URLs are found, `detail_candidates_considered` should increase
- if profile plus location/remote evidence validates, `detail_evidence_gate` can pass
- otherwise the manual-review stop remains correct and auditable
