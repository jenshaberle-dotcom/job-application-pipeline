# DETAIL-004B Location Evidence Strictness

Status: implemented as DETAIL-004A follow-up hardening
Safety zone: SZ2 evidence and gates

## Purpose

DETAIL-004A made Tavily/detail-provider evidence usable and removed the biggest cross-domain and duplication issues. Runtime smoke still showed one subtle false-positive risk: employer brands whose name contains the target location can make unrelated jobs look location-relevant.

Example: `Hannover Rück` / `Hannover Re` pages for London or Orlando can contain the token `Hannover` because of the employer brand, not because the job is located in Hannover.

## Rule added

When the candidate company name already contains the target location term, DETAIL-004B no longer accepts generic phrases such as `in Hannover` as sufficient location evidence. The location term must appear in one of the stronger signals:

- the concrete job detail URL path, for example `/job/Hannover-...`
- a labeled location context such as `Standort Hannover`, `Arbeitsort Hannover`, `Location Hannover`, `Office Hannover`, or `Hannover (NDS)`

This keeps valid Hannover detail pages passable while preventing employer-brand-only pages from passing the `detail_evidence_gate`.

## Boundary

DETAIL-004B does not expand permissions:

- no candidate URL writes
- no connector registration
- no source activation
- no Bronze/Silver writes
- no scheduler changes
- no raw HTML persistence

It only changes evidence validation strictness before gate decisions.

## Expected effect

- E.ON Grid Solutions should remain passable when concrete detail pages contain profile and target/remote evidence.
- Hannover Rück pages with true Hannover job-location signals remain passable.
- Hannover Rück pages for London/Orlando should no longer pass solely because the employer brand contains `Hannover`.
