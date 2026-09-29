# Demo learning source reconciliation — 2026-09-29

## Current Product truth

- Silver job 577, “AI Engineer / KI-Entwickler (m/w/d)”, is sourced from
  `generic_origin:finanz_informatik`, not `finanz_informatik:hannover`.
- Both FI search profiles are currently inactive and have recurring ingestion
  disabled. The job remains in current Product truth as `active_confirmed`.
- Its exact employer vacancy URL returned active job detail, Hannover geography,
  and three approved Candidate Fact matches in the read-only scout.
- The demo-only source boundary now reads current employer-origin Product rows
  independently of recurring profile activation. Canonical ingestion and refill
  continue to use the recurring-profile gate.
- A live scout of 68 current employer-origin rows found 30 eligible jobs from
  nine employers. The ten-job, seven-employer sample included FI job 577.

## ivv source qualification

- The official ivv careers page links to `https://www.jobs.ivv.de/`. The
  candidate `company_key=ivv` previously had no origin URL and no active
  `generic_origin:ivv` profile. The only existing Silver ivv row came from a
  market sensor, not Employer-Origin.
- The discovery gate now recognizes a dedicated root jobs host when its
  employer label exactly matches the company key. The verified URL was saved
  on candidate 30 as a source-discovery fact; this did not activate ingestion.
- The existing generic connector layer reached a live job detail on that host
  and returned `proof=PASS` through identity, origin, reachability, inventory,
  detail, and strict job proof.
- The previously indexed ivv “KI-Entwickler” detail currently returns HTTP 410
  and is absent from the live portal. It cannot be used as a current sample job.

## Demo connector boundary

ivv is intentionally separated from the ten-job ranking sample. The sample still
requires the real Finanz Informatik vacancy, while ivv demonstrates the reusable
Employer-Origin connector path.

`scripts/run_generic_origin_demo_profile.py` prepares an exact, non-recurring
`generic_origin:ivv` execution profile only after the materialized ivv origin URL
exists. Apply mode requires an explicit approval token and keeps
`recurring_ingestion_enabled = FALSE`. It does not change candidate status,
write the canonical generic active-source projection, change scheduling, rank a
job, or touch applications.

The bounded follow-up remains the normal shared pipeline:

```text
python -m scripts.run_generic_origin_demo_profile --company-key ivv --apply --approval-token DEMO-GENERIC-ORIGIN-PROFILE-001
python -m src.ingest_jobs --profile demo_generic_origin__ivv
python -m src.run_silver_jobs --source generic_origin:ivv --limit 1
```

A current ivv job may enter Product and later the learning sample only if normal
Silver, lifecycle, Candidate Fit, hard-filter and Affinity authorities accept it.
No job row or score is manufactured merely to make the demo look complete.
