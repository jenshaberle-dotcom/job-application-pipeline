# JAP execution — RCC General Pool

Status: current consumer contract.

RCC owns the only physical General Linux/Windows pool. JAP declares workload and capability
demand, exact source and permitted effects. JAP owns no runner count, registration, fixed
member, persistent facade selection or scaling authority.

## Workflow demand

Authoritative mapping: `.rcc/workload-demands.json`.

| Workflow | Demand | Purpose |
|---|---|---|
| `.github/workflows/pr-validation.yml` | `linux-base` | Exact-source repository validation |
| `.github/workflows/product-v1-assessment-cohort.yml` | `linux-base` | Bounded Product assessment |
| `.github/workflows/jap-windows-desktop-host-release.yml` | `windows-release` | Immutable desktop/runtime packaging and publication |
| `.github/workflows/rcc-general-pool-proof.yml` | `windows-release` | Windows assignment/toolchain proof |

JAP declares Python and a dependency-set identity. The Windows demand adds .NET 8 and Node 22.
RCC materializes and qualifies required capabilities; consumers do not install everything on
all members or define physical profile/pool topology.

## Handoff and verification

RCC admits demand, reserves a member, activates an exact repository facade, supplies an
ephemeral assignment label and dispatches the exact consumer source. The workflow inputs are
`source_sha`, `rcc_facade_label`, `rcc_assignment_label`, plus workload-specific inputs.
The consumer verifies checked-out source, runner/facade identity and qualified runtime context.
RCC verifies completion, cleans the assignment/facade and releases its reservation.

The consumer source SHA binds product code. It is not a requirement to chase each RCC `main`
commit. Broker compatibility changes belong to the RCC handoff contract; this documentation
does not invent unsupported broker-version inputs.

No available qualified capacity means waiting/blocked. No GitHub-hosted fallback or local
scheduler restores execution. Effect-bearing failures require terminal/audit evidence before
retry. Local product operation and developer validation remain distinct from automated CI
admission and runner authority.

## Acceptance

Workflow/config presence proves repository integration only. Live acceptance requires run/job
identity, assigned General Pool member, correct runtime, result and cleanup evidence. Retire
physical legacy runners through RCC only after replacement proof; never infer retirement from
absence of an old label in JAP.
