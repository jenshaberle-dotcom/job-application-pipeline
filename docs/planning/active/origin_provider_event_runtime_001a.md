# ORIGIN-PROVIDER-001A Event-Driven Private Origin Benchmark Runtime

Status: implementation ready for independent review

## Outcome

A successful local Pipeline data refresh can trigger a private GitHub runtime
only when the bounded employer-origin database projection changed. The private
runtime reconnects to the live local PostgreSQL database through an ephemeral
Tailscale GitHub runner, revalidates the exact projection fingerprint and may
then execute a globally bounded Tavily benchmark.

## Scope

- metadata-only `repository_dispatch` after local DB change detection,
- exact committed Pipeline revision binding,
- read-only projection and SHA-256 fingerprint contract,
- private reusable workflow with GitHub OIDC and Tailscale,
- dedicated table-scoped PostgreSQL reader role,
- hard Tavily request ceiling,
- stale-fingerprint stop before provider execution,
- recovery redispatch after 12 hours,
- successful ref/fingerprint cache preventing duplicate provider calls,
- three-day private review artifact,
- provider-free repository tests and documentation.

## Boundaries

- no provider call in implementation or CI,
- no database mutation,
- no candidate URL persistence,
- no connector registration,
- no source activation,
- no Bronze/Silver write,
- no scheduler mutation,
- no DB rows in GitHub event payload,
- review artifacts are not pipeline inputs,
- private runtime repository, secrets, Tailscale policy and PostgreSQL network
  configuration remain separate one-time operator setup.

## Validation

- Python compile validation,
- YAML parse validation,
- focused provider-free contract suite,
- full independent Pipeline CI on the pull-request head.

## Activation after merge

The accepted reusable workflow must be pinned by merge SHA in the private runtime
caller. The local canonical data-refresh command may then append
`dispatch_origin_provider_benchmark_if_changed --dispatch` only after its own
successful completion.
