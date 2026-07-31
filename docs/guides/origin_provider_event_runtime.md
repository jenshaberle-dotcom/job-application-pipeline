# Event-driven Origin Provider Runtime

Status: implementation foundation for a private runtime caller

## Purpose

The local Pipeline database remains the system of record. After a successful
local data refresh, a change detector reads a bounded employer-origin projection,
calculates a SHA-256 fingerprint and triggers a private GitHub runtime only when
that projection changed.

The GitHub event contains metadata only. It does not contain candidate names,
URLs, job text or database rows.

```text
successful local data refresh
        -> read-only DB projection
        -> SHA-256 change detection
        -> repository_dispatch to private runtime repository
        -> ephemeral GitHub-hosted runner joins Tailscale
        -> fingerprint re-check against live DB
        -> bounded Tavily calls
        -> private three-day review artifact
```

## Repository separation

The public `job-application-pipeline` repository owns the projection and
fingerprint contracts, provider budget enforcement, dispatcher, benchmark
runner, reusable workflow, tests and documentation.

A private runtime repository owns only the event caller, Tailscale/Tavily/
PostgreSQL secrets, private run history and private review artifacts.

Copy
`docs/reference/security/private_origin_runtime_caller.example.yml` to
`.github/workflows/origin-provider-runtime.yml` in the private repository. After
this Pipeline PR is merged, pin the reusable workflow reference to the accepted
merge SHA instead of leaving `@main` in place.

## Hard boundaries

- no candidate URL write,
- no connector registration,
- no source activation,
- no Bronze/Silver write,
- no scheduler mutation,
- no database rows in the GitHub dispatch payload,
- no provider call when the DB fingerprint changed after dispatch,
- no provider call above the global request ceiling,
- artifacts are review output only and never pipeline input.

The dedicated PostgreSQL role uses `default_transaction_read_only=on` and direct
`SELECT` access only to `employer_origin_source_candidates` and
`market_evidence`.

## Default request envelope

| Control | Default |
|---|---:|
| Maximum candidates | 6 |
| Queries per candidate | 2 |
| Results per query | 5 |
| Global Tavily request ceiling | 12 |
| Generated URL candidates per company | 20 |
| Market-evidence URLs per company | 10 |
| Review artifact retention | 3 days |
| Unchanged-event recovery window | 12 hours |

The effective candidate count is reduced automatically if the candidate/query
combination would exceed the global provider request ceiling.

## Required system tools

1. Git and the existing Pipeline checkout.
2. GitHub CLI (`gh`) authenticated as the repository owner.
3. Tailscale in the same Linux/WSL2 network namespace as PostgreSQL.
4. PostgreSQL server and the `psql` client.
5. A private GitHub repository, for example `job-pipeline-runtime`.

No new Python package is required. The repository already includes `psycopg`,
`requests` and `python-dotenv`.

Refresh the virtual environment:

```bash
cd ~/projects/job-application-pipeline
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip check
```

## Install Tailscale on Ubuntu/WSL2

Install Tailscale in the environment that can directly reach PostgreSQL. If
PostgreSQL runs inside WSL2, install Tailscale in that WSL2 distribution.

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale status
tailscale ip -4
```

The database host must remain online while the remote benchmark runs.

## One-time Tailscale configuration

1. Create a personal tailnet.
2. Add `tag:github-origin-benchmark` for ephemeral GitHub runners.
3. Tag the PostgreSQL host separately, for example `tag:pipeline-db`.
4. Permit only the benchmark tag to reach the DB host on TCP 5432.
5. Create a federated identity with the `auth_keys` capability and benchmark tag.
6. Store its Client ID and Audience as private GitHub secrets.
7. Keep MagicDNS enabled or record the stable tailnet hostname/IP.

The reusable workflow uses `tailscale/github-action@v4`, GitHub OIDC and an
ephemeral tagged node. It does not require a reusable Tailscale auth key.

## One-time PostgreSQL reader setup

Run the repository-owned SQL through an administrative PostgreSQL account:

```bash
cd ~/projects/job-application-pipeline
psql \
  --host "$POSTGRES_HOST" \
  --port "${POSTGRES_PORT:-5432}" \
  --dbname "$POSTGRES_DB" \
  --username "$POSTGRES_USER" \
  --set "database_name=$POSTGRES_DB" \
  --file db/ops/create_origin_benchmark_reader.sql
```

The script prompts once for the new `origin_benchmark_reader` password. Store
that password only in the private runtime repository. PostgreSQL must listen on
the Tailscale interface and `pg_hba.conf` must permit the dedicated user from
the intended tailnet range. Public Internet access remains closed.

## Credential classes

Keep the following credential classes separate:

1. **Application credentials** belong to the normal local Pipeline runtime. They
   follow the existing application configuration contract and must not be copied
   into the private GitHub runtime merely because they use familiar generic
   environment-variable names.
2. **Administrative credentials** are reserved for explicit operator-controlled
   setup, migration and role-management commands. They must never be stored in
   the private runtime repository or exposed to the reusable provider workflow.
3. **Remote runtime credentials** identify only the restricted
   `origin_benchmark_reader`. They are stored in the private runtime repository
   under `ORIGIN_BENCHMARK_DB_USER` and `ORIGIN_BENCHMARK_DB_PASSWORD`.

Do not reuse passwords between these classes. Host, port and database-name
secrets may be shared as connection metadata; user and password secrets may not
silently cross privilege boundaries.

## Create the private runtime repository

```bash
gh repo create jenshaberle-dotcom/job-pipeline-runtime --private
```

Copy and commit the caller workflow:

```bash
mkdir -p /tmp/job-pipeline-runtime/.github/workflows
cp docs/reference/security/private_origin_runtime_caller.example.yml \
  /tmp/job-pipeline-runtime/.github/workflows/origin-provider-runtime.yml
```

The `repository_dispatch` workflow must exist on the private repository's
default branch before an external event can trigger it.

Add these Actions secrets to the private repository:

```text
TS_OAUTH_CLIENT_ID
TS_AUDIENCE
TAVILY_API_KEY
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_DB
ORIGIN_BENCHMARK_DB_USER=origin_benchmark_reader
ORIGIN_BENCHMARK_DB_PASSWORD
```

The privilege-specific reader names are part of the caller contract. Do not
store the restricted reader under generic `POSTGRES_USER` or
`POSTGRES_PASSWORD` secret names. `POSTGRES_HOST` should be the Tailscale
MagicDNS hostname or stable tailnet IP of the database host.

## Local dispatcher setup

Set the private runtime target locally:

```bash
printf '\nORIGIN_RUNTIME_REPOSITORY=jenshaberle-dotcom/job-pipeline-runtime\n' >> .env
```

Confirm prerequisites:

```bash
gh auth status
tailscale status
python -m scripts.dispatch_origin_provider_benchmark_if_changed --help
```

Run the provider-free preview:

```bash
python -m scripts.dispatch_origin_provider_benchmark_if_changed
```

After the private caller and secrets exist, dispatch the first bounded event:

```bash
python -m scripts.dispatch_origin_provider_benchmark_if_changed --dispatch
```

The dispatcher writes its last event state to
`.runtime/origin-provider-dispatch-state.json`, which is ignored by Git.
Unchanged data inside the 12-hour recovery window sends no event. After the
window, a recovery event may be resent. The private runtime stores a successful
revision/fingerprint marker, so an already completed Tavily benchmark is not
repeated.

## Automatic integration after a successful data refresh

Append the dispatcher only after the canonical local data command succeeds:

```bash
python -m <canonical-local-data-refresh-command> \
  && python -m scripts.dispatch_origin_provider_benchmark_if_changed --dispatch
```

For an existing shell script:

```bash
set -euo pipefail
python -m <canonical-local-data-refresh-command>
python -m scripts.dispatch_origin_provider_benchmark_if_changed --dispatch
```

A failed local Pipeline command cannot trigger the provider runtime. A successful
run with unchanged relevant data sends nothing inside the recovery window.

## Operational behavior

### Changed data

1. GitHub validates the metadata-only event.
2. The runner checks out the exact committed Pipeline SHA.
3. The runner joins the tailnet as an ephemeral tagged node.
4. The runner re-reads the bounded database projection.
5. A fingerprint mismatch stops before Tavily.
6. A matching fingerprint permits the bounded Tavily benchmark.
7. A private report is retained for three days.

### Unchanged data and recovery

Inside the recovery window, no event is sent. After the window, a recovery event
is allowed. A successful cache marker stops before Python setup, Tailscale,
PostgreSQL and Tavily. A failed previous run has no marker and is retried.

### Database host offline

The job fails at the Tailscale ping or PostgreSQL connectivity check. No public
fallback connection is attempted.

### Data changed between dispatch and execution

The remote runner emits `stale_dispatch_fingerprint` and performs no provider
call. A later successful local refresh can dispatch the new fingerprint.

## Installation boundary

This implementation does not create the private runtime repository, alter
Tailscale policy, create GitHub secrets, change PostgreSQL networking, execute
Tavily, update the production schema or activate a scheduler/source.
