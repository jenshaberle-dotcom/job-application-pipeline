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

The runtime projection supplies `RepositoryId`, `Repository`, `RunnerName`,
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

## Accepted Linux execution and remaining Windows gate

Linux live acceptance passed on exact candidate
`8f3241662505cb4008bb7a12d16bab6487901ea1` in
[run 37115262842](https://github.com/jenshaberle-dotcom/job-application-pipeline/actions/runs/37115262842).
All 3,923 tests, repository/documentation contracts, qualified Python and Ruff passed.
RCC reported request `05d476c267c9cdcf43d90817590808268c46ff6d4ea6aa5d09af8e1b938abbe3`
as `SUCCEEDED`, runtime-context cleanup, zero active listeners and final state
`OFFLINE_DISABLED_EXACT_ONLY`. JAP PR #1163 merged as
`092c96d4241d8a4224dd4fedef00a6ad7bf1d43f`; RCC PR #736 supplies automatic
reviewed-wheel preparation. Cold seed acquisition and subsequent runtime reuse were
proved without manual `PIP_FIND_LINKS`.

Windows proof and release validate the same exact-source runtime fields, using Windows
absolute interpreter paths. Both use a per-run candidate directory and always remove
that checkout, including after failure. Release uses Ruff through the qualified Python.
These consumer guards do not implement RCC Windows execution or provision capabilities.

At the 2026-10-03 inspection, RCC's capability catalog marks `node-22` and the
PowerShell 7 qualification capability `IMPLEMENTATION_PENDING`; its Demand-v2 CI
controller and source-bound Python materializer are Linux-only. The RCC demand
materializer rejects pending capabilities. Existing Windows fleet capacity or a tool
already on PATH does not establish a qualified Windows handoff. Complete and prove
those existing RCC paths before dispatching the Windows proof; do not fabricate an
assignment, install tools in JAP's workflow or use a hosted fallback.

Run the non-publishing `rcc-general-pool-proof.yml` through RCC first. Actual release
publication remains a separate effectful admission: desktop version 1.2.6 already has
an immutable release on an earlier source, so publishing a different source under that
same tag is rejected. A new release needs its own approved version/source identity.
Windows live acceptance and physical legacy-runner retirement remain unproved.
