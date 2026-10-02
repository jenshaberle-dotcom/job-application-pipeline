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

## Automatic admission and runtime contract

Automatic PR admission is declared only for `pr-validation.yml` / `linux-base`:
`pull_request`, exact `pull_request_head_sha`, base `main`, `auto_dispatch: true`,
`effect_semantics: validation-only`. RCC's `.rcc/demand-v2-ci-consumers.json` must
contain the matching `jap` repository ID, workflow and demand profile. Pool access
alone does not enroll a consumer in automatic CI.

The controller dispatches its trusted workflow from JAP `main` and checks out the
admitted candidate SHA. The exact-source workflow must therefore be merged before
the controller can use it; a branch-only workflow edit cannot bootstrap its own CI.
Do not bypass that boundary with a fake assignment or hosted fallback.

The Linux runtime projection supplies `RepositoryId`, `Repository`, `RunnerName`,
`Platform`, `Status`, `PrimaryFailure`, `Interpreter`, `ProfileId`, `ProfileHash`
and `SourceSha`. JAP verifies identity and exact source before using that interpreter;
it does not require a persistent checkout or own the content-addressed runtime.
The PR workflow checks Python 3.12.14, uses RCC's installed pytest/Ruff, and deletes
its per-run source checkout even after failure. RCC removes its runtime projection,
assignment and reservation after completion.

Product assessment is not auto-admitted and still requires existing Product approval
and an operator-configured absolute `JAP_DATA_ENV_FILE` on the execution host. This
is a data/secret configuration file, not a checkout or interpreter authority; missing
configuration stops before plan/apply. Windows proof and publication remain separately
authorized Windows workloads. The Linux controller does not automatically dispatch them.

Broker API/policy compatibility is checked by RCC; a documentation-only RCC commit
does not require a broker reinstall. Exact RCC executor authority and exact JAP
candidate source remain independently enforced.

## Acceptance

Workflow/config presence proves repository integration only. Live acceptance requires run/job
identity, assigned General Pool member, correct runtime, result and cleanup evidence. Retire
physical legacy runners through RCC only after replacement proof; never infer retirement from
absence of an old label in JAP.

## Source activation and first live proof

The consumer hardcut is merged in JAP PR #1162
(`19e8a84011ab34983ff95abdc63fb4bdb26d5b42`). RCC PR #734
(`efd8b49210f5855d30c0946c4de14d2d1e24f97e`) adds the matching CI catalog entry.
These merges establish source integration, not live host acceptance.

The first proof candidate changes this activation record only and preserves the
merged demand, workflow and runtime contract. Run it through the existing RCC
controller using its exact repository/PR filters after adopting current RCC source.
Preserve request state and consumed authority markers. Do not reinstall the broker
for this catalog-only change, manually choose a physical member or fabricate labels.

Acceptance requires the linked GitHub run, exact candidate SHA, RCC-assigned
facade/runtime, passing full validation and the executor's terminal cleanup evidence.
Until those are recorded, the first live JAP Linux proof remains pending.
