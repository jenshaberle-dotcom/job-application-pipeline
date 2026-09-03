# DEMO-001 live readiness checkpoint — 2026-09-03

Operator-local proof on branch `agent/demo-001-application-readiness-window` at `5a296230f98ee596ff590ceb580db3c86c85aeef` established:

- frontend build: PASS
- Product V1 live preflight: PASS
- schema frontier: READY
- current active jobs: 31
- rankable jobs: 1
- authoritative Top-5 jobs: 1
- selected job: Silver 434 — Heartbeat AI GmbH — `(Junior) Data Engineer - Data Platform (m/f/d)`
- Application Workspace probe: PASS
- deterministic draft handoff probe: PASS
- job detail HTTP GETs: exactly one maximum in the workspace probe
- draft handoff HTTP GETs: 0
- provider requests during readiness proof: 0
- database writes during readiness proof: 0
- submission writes: 0
- send actions: 0
- terminal outcome: `PRODUCT_V1_LIVE_DEMO=READY`

The proof required the canonical private-document root to be explicitly supplied as:

`PRODUCT_V1_PRIVATE_DOCUMENT_ROOT=<repo>/private_application_sources`

The approved local CV and base application letter were both present and matched their database-recorded SHA-256 values exactly. This exposed one remaining launcher wiring inconsistency: the demo server configures the default private-document root automatically, while the readiness launcher did not yet export the same root before the workspace probe. The next bounded hardening change is to wire that existing canonical root into the launcher; no product, ranking, database, provider, submission, or send authority change is required.
