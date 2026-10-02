# ADR-034: JAP product continuity and Cloud succession

Status: Accepted
Original decision: 2026-09-16. Direction corrected to the operator's Cloud hardcut target.

## Context

Classic implements the local PostgreSQL/Python/React product and Windows WebView2/WSL runtime.
JAP Cloud is the migration target. A bounded transition must not become permanent parallel
feature development or independent ranking, Fit, Top-5 and application semantics.

## Decision

Preserve one accepted product meaning while transferring useful code, contracts and real data.
Complete Cloud parity and verified migration, then make Cloud the sole normal product path.
Classic remains maintained during the transition for installed-product continuity and reuse;
this document does not assert that parity or physical retirement has occurred.

- Runtime adapters may differ; product gates and private-fact provenance must remain compatible.
- Classic PostgreSQL is current Classic persistence, not a prescription for Cloud storage.
- Cloud infrastructure, API/UI topology and deployment evidence belong to the Cloud repository.
- Classic's React UI and reusable services may inform parity without becoming Cloud deployment proof.
- Real migration data requires lineage, identity and integrity; fixtures cannot pass as live truth.
- Do not add live mirroring or synchronize two independently evolving operational databases.
- Do not require a new repository/package/control plane merely to start useful bounded reuse.

## Succession acceptance

Require current evidence for critical operator journeys, compatible product contracts,
real-data migration integrity, private-data boundaries, immutable release/runtime identity,
rollback/recovery and operator acceptance. A cloud demo alone is not parity acceptance.
After acceptance, retire Classic's normal operational authority deliberately and prove that
stale workflows, update paths and instructions cannot restore a second product track.

## Consequences

Maintenance and defect work preserve the current installed product. New migration/parity work
should produce reusable capabilities and one accepted outcome, rather than dual roadmaps.
Open Cloud planning or provider/worker authority does not authorize Azure or private-data effects.

See `docs/current/product.md`, `docs/current/architecture.md` and the current Cloud repository:
https://github.com/jenshaberle-dotcom/jap-cloud-based
