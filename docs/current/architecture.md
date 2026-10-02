# Current system architecture

Status: implemented Classic boundaries and approved Cloud transition direction.

## Components

| Component | Responsibility | Source |
|---|---|---|
| React Control Center | Operator presentation and API calls | `frontend/control-center/` |
| Python product runtime | API, assessment, ranking, drafting and tracking orchestration | `scripts/run_product_v1_control_center.py`, `src/search_intelligence/` |
| PostgreSQL | Persisted product state, evidence and read models | `db/migrations/` |
| Acquisition modules | Bounded sensors, origin/detail evidence, reusable connectors | `src/ingestion/`, `src/search_intelligence/` |
| Windows host | WebView2, product-local update staging, consent and rollback | `windows/JAP.ControlCenter.Desktop/` |
| WSL bridge | Run immutable product code with local private environment | `scripts/run_jap_windows_control_center.sh` |
| RCC | General Pool admission, toolchain materialization, assignment and cleanup | `.rcc/workload-demands.json` declares JAP demand only |

Jinja2 is an earlier presentation decision, superseded for the current React product surface.
Python/database boundaries retain business authority; templates and UI components do not.

## Evidence and acquisition

Market sensors discover candidates; a signal is not an active source or verified job.
Origin/detail evidence, validation, approval and activation are separate stages.
Bronze retains raw acquisition and lineage; Silver canonicalizes jobs; Gold/read models
support decisions and observability. Reports are output, never hidden input authority.

Connector registration, controlled first ingestion and recurring admission are distinct.
The fleet design in `config/connector_fleet_policy.json` defines health/yield separation,
cadence and bounded execution. Its presence does not prove live fleet closure; proposed
fleet-health changes must be distinguished from merged implementation.

## Product decision boundary

Approved Candidate Facts support Candidate Fit. Affinity remains a separate projection.
Hard filters and ranking own eligibility and Top 5. Drafting uses template authority and
fact provenance. Tracking/mailbox evidence does not send applications.

## Installed runtime and releases

The desktop and runtime archives bind exact source identities. The installed updater stages
and verifies before consent, then applies a frozen target with transactional rollback.
Product runtime execution is local; CI and release packaging use RCC-assigned General Pool
members. No JAP-owned pool, physical member selection or hosted fallback is supported.
See [execution contract](ci-max-execution.md) and [Windows guide](../guides/jap_control_center_windows_app.md).

## Cloud succession

One accepted product contract must survive migration. The approved target is Cloud parity,
verified transfer/reuse of real data, then Cloud as the sole normal product path. Classic's
local implementation is maintained for continuity and migration, not a parallel feature track.
No live mirroring or duplicated ranking/gate authority is introduced by this documentation.

Cloud runtime topology belongs to the Cloud repository. Do not copy old Azure PostgreSQL,
React or fallback assumptions into Classic as Cloud implementation facts. Cloud parity,
deployment and migration require current Cloud evidence and operator acceptance.

See [ADR-034](../decisions/adr/034_define_shared_jap_product_and_runtime_coexistence.md).
