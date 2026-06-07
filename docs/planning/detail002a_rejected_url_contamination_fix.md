# DETAIL-002A Rejected URL Contamination Fix

## Purpose

DETAIL-002 improved detail-link discovery by prioritizing real candidate hosts and embedded job-detail URLs. The first runtime dry-run exposed a follow-up defect: human-readable rejected URL audit entries such as:

    https://jobs.example.com/ :: not_concrete_job_detail_url

were reused as seed URLs in later repair attempts. This produced malformed requests such as:

    https://jobs.example.com/%20::%20not_concrete_job_detail_url

DETAIL-002A treats rejected URL entries as audit evidence, not URL source of truth.

## Boundary

This is a parsing/cleanliness repair inside the detail-evidence discovery path. It does not change gate thresholds and does not write candidate URLs, connectors, sources, Bronze/Silver data, scheduler state or raw HTML.

## Behavior

- Strip audit suffixes after ` :: ` before reusing persisted evidence URLs.
- Keep only valid `http://` or `https://` URLs with a host.
- Drop JavaScript, relative, empty and non-URL audit text.
- Keep DETAIL-002 host prioritization and embedded URL extraction intact.
- Mark generated evidence with `detail_link_discovery_version = DETAIL-002A`.

## Expected Runtime Signal

After this fix, reports must not contain newly requested URLs with encoded audit suffixes such as `%20::%20not_concrete_job_detail_url`. If no detail candidates are found, the correct outcome remains an auditable `detail_evidence_gate / manual_review_required` stop.
