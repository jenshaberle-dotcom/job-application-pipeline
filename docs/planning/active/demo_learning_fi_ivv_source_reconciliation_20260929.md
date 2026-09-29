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

## Remaining effect boundary

`docs/current/FREEZE-II-CONNECTOR-ACTIVATION-AUTHORITY.md` currently says
`activation_allowed: false`. ivv therefore remains a qualified candidate,
not a productive Employer-Origin source. The demo selector now requires both
FI and ivv when `--demo-learning-sample` is used and fails visibly until a
current ivv job has passed normal ingestion and the live Candidate Fact gate.
No ivv job, profile, Bronze, Silver, Gold, or ranking state was manufactured.

The next reviewed activation step must first satisfy the Freeze-II authority
conditions, then include ivv in a current generic proof cohort and run the
normal ingestion path. A later live sample can select whichever ivv vacancy
actually passes the same exact-detail, geography, and Candidate Fact checks.
