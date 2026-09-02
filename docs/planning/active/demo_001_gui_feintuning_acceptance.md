# DEMO-001 GUI feintuning acceptance

Status: ACTIVE

## Operator evidence captured 2026-09-02

The live Control Center is technically usable but overloaded. Operator feedback sets the next usability target:

- primary navigation belongs on the **left**, not in a top tab strip;
- separate workflow surfaces are required for **Overall**, **All Jobs**, **Top 5**, **Application**, **Sources**, **Approvals**, and **Operations**;
- Overall summarizes current truth and next action without duplicating the full job corpus;
- All Jobs is a focused review surface with search/filter, explicit operator relevance labels, and a bounded detail panel;
- Top 5 is its own application-oriented shortlist;
- operator relevance feedback (`interesting`, `not_relevant`, `unsure`) remains prominent and does not directly mutate ranking/Product authority;
- application preparation remains review-only and never implies auto-submit/send;
- remote Germany remains intentionally valuable discovery scope because the current Personio pilot already surfaces credible jobs the operator would probably not find manually;
- local employer connector expansion is deferred until this GUI/backend feintuning closes.

## Data-quality findings carried into backend hardening

- Personio tenant/employer brand identity and legal/subcompany identity must not be conflated. `personio:1komma5grad` is authority-bound to 1KOMMA5° while the feed may expose `Heartbeat AI GmbH` as a legal/subcompany value; UI should present the authoritative employer brand and preserve legal-entity evidence separately.
- `Vollzeit` / `Full-time` is useful schedule evidence even when no numeric weekly-hours value is published. Product truth must not invent `37.5-40h`, but UI/evidence should say `Full-time; numeric hours not published` instead of reducing the entire field to `unknown`.
- an explicitly Berlin-only job with no Germany-remote/acceptable-commute evidence is outside the Hannover/remote-Germany target and must not remain in the active review list merely because geography is unresolved.

No acceptance item changes hard-filter, ranking, Top-5, application, or submission authority by presentation alone.
