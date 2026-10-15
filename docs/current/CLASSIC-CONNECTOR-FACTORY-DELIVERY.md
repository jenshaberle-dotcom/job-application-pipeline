# Classic Connector Factory and job delivery

Decision: 2026-10-15, Jens Haberle. Tracking: EO-026.

JAP Classic becomes the implementation and execution target again. The existing PostgreSQL
runtime, generic layer builder, `generic_origin` registry, Bronze gate and ingestion repository
remain authoritative. The Cloud migration is parked. No Azure storage, cloud subscription,
paid discovery provider, new runner or scheduler is required by this slice.

## Execution contract

`python -m scripts.run_classic_connector_factory` orchestrates:

1. Read-only database/schema preflight and full current candidate population snapshot.
2. Canonical generic layer assessment of every candidate, without a company-count limit.
3. Fresh proof-PASS projection and additive activation inside one database transaction.
4. Normal `GenericEmployerOriginProductConnector` acquisition, query discrimination,
   detail evidence, Bronze plausibility and `JobIngestionRunner` persistence.
5. Exact ingestion-run receipts and stored observations linked to actual raw jobs.

This connects the existing product factory, rather than admitting lab recipe PASS as runtime
proof. The generic recipe/interpreter and Census laboratory remain reusable development
components; neither is a second source activation authority. Sources still need real proof.
The current database denominator is used, not an assumed historical count of 1,735.
A 1,735-candidate automated test verifies whole-population orchestration; it is synthetic,
not a live Census or a pilot. URL discovery bounds apply per company only.

Additive activation reuses the existing activation implementation with
`preserve_existing=True`. It updates the newly proved sources and their canonical profiles,
including recurring enablement, but does not retire unrelated profiles or delete older source
projections because a fresh source attempt failed. The legacy standalone activation CLI
retains its explicitly requested full-reprojection semantics.

Failed/unavailable query acquisition now raises an ingestion failure. A genuinely unconfirmed
zero result remains zero; neither is evidence of profile relevance. A positive Bronze report
requires successful ingestion rows and the matching number of persisted job observations with
non-null raw-job identities. A completed source with zero jobs cannot satisfy delivery.

## Host one-shot

Use the qualified checkout in the declared WSL worktree, the installed Python environment
with `requirements.txt`, and the existing Classic database configuration. Do not copy secrets
into the repository, report, or command line. `RUNTIME_ENV_FILE` may point to the existing
absolute host env file. A state directory must be outside the checkout and retained.

Read-only preflight (no source HTTP requests and no database writes):

```bash
python -m scripts.run_classic_connector_factory --state-dir "$HOME/jap-state/classic-factory-20261015"
```

After source qualification, the same entry point runs preflight and the complete workload:

```bash
python -m scripts.run_classic_connector_factory \
  --state-dir "$HOME/jap-state/classic-factory-20261015" \
  --execute-sha "$QUALIFIED_SHA"
```

`QUALIFIED_SHA` is the exact reviewed/qualified commit, not a moving branch name. A dirty
checkout, wrong SHA, missing host configuration/schema, or competing factory invocation
aborts. Existing migrations are prerequisites; this command does not apply migrations.
RCC owns any CI/managed workload admission. This command does not create a background process.
Coordinate the initial run with the existing recurring ingestion service; the advisory lock
serializes factory invocations, not unrelated legacy ingestion commands.

## Persistence and reconciliation

`receipt.json` binds source SHA, database identity hash, complete candidate identity digest and
execution settings. `receipt.stages/` stores one fsynced receipt per phase/company, avoiding
quadratic rewrites of the population. `proof.json` preserves the qualified population;
`acceptance.json` summarizes the completed attempt. Blocked attempts get separate timestamped
reports, so they cannot overwrite another live execution's acceptance.

Always retain and reuse the same directory when resuming this workload. Successful phases
are skipped. Read-only failed/interrupted qualifications can repeat; effectful `RUNNING` or
`HELD` phases cannot repeat. Ingest receipts contain exact run IDs when available. A crash
between DB commit and receipt persistence remains held, even if DB writes might have succeeded.
Do not delete receipts, change the binding, or choose a fresh directory to bypass that gate.

Reconcile held activation against the source projection, candidate and canonical-profile
rows; reconcile ingestion using its run IDs, `ingestion_runs`, `raw_jobs`, and
`job_observations`. If the run ID itself was not persisted, inspect matching source/profile
runs before admitting any new effect. The first slice intentionally has no automatic receipt
reset or blind replay command. Other qualified sources continue after a held source ingestion.

## Evidence and remaining acceptance

The authoring environment's actual preflight returned `HOST_DATABASE_CONFIGURATION_MISSING`
on 2026-10-15. No host database access, productive activation or real job delivery is claimed.
Local qualification on 2026-10-15: 4,032 tests passed; changed Python files pass Ruff;
`git diff --check` passed. This is not RCC exact-head or host runtime qualification.
Tests exercise complete population, durable intent, crash/timeout holds, repeat runs,
binding changes, non-destructive activation and query failure propagation.

Exit 0 means read-only preflight ready or verified Bronze delivery with no held ingestion.
Exit 2 means blocked/incomplete. `bronze_delivery_proven` is distinct from
`profile_relevance_proven`, `ranking_fitting_proven`, and `e2e_accepted`; the last three remain
false in this slice. Existing Silver/Gold/Fit/ranking must supply current evidence before
product acceptance. Old ranking rows, fixture jobs and successful HTTP requests are not that proof.

Lifecycle: existing main baseline -> new isolated slice (prior Census branch already merged)
-> local qualification -> PR exact-head RCC qualification -> host adoption/acceptance -> merge
only after the applicable gates -> verify remote and local branch absence after merge.
No merge or installed-desktop update is implied by committing this code.
