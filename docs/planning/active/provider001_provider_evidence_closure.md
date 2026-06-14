
# PROVIDER-001 Provider Evidence Closure

Status: active planning anchor
Boundary: generics proof before V1

## Purpose

The current generics-first sequence keeps Product V1 behind a clean provider and
origin evidence proof. PROVIDER-001 closes the known `provider_backed_origin_coverage`
gap without opening candidate creation or connector activation prematurely.

## Sequence

1. PROVIDER-001B Read-only Provider Evidence Discovery
   - scan existing evidence only
   - no external probes by default
   - no DB writes
   - no candidate/gate/connector mutation
2. PROVIDER-001C Provider Coverage Decision Bundle
   - decide whether the provider-backed origin coverage gap is closed
   - identify remaining provider/source families that need a bounded probe
   - produce a decision artifact before GENERIC final recheck
3. GENERIC final recheck
   - re-run the positive proof / generic evidence chain after provider coverage
   - keep outputs review-only
4. APPLY-001 only after the evidence gap is closed or explicitly accepted as open

## System-impact boundary

Provider evidence is a proof input, not an activation decision. It may improve
confidence that origin evidence can be found generically across provider-backed
career portals, but it must not directly move a candidate through gates or create
source targets.


## DB-backed evidence run hardening

For the actual provider-backed evidence decision, run the report with `--include-db --require-db`.
The script resolves the local DB DSN from supported env aliases, local env files, or a Docker Compose Postgres configuration. If no read-only DB scan can complete, the report is intentionally not sufficient evidence for PROVIDER-001C/APPLY-001.
