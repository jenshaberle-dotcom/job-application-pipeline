# Event-driven Origin Provider Runtime

Status: implementation foundation for a private runtime caller

## Purpose

The local pipeline database remains the system of record. After a successful
local data refresh, a change detector reads a bounded origin-candidate
projection, calculates a SHA-256 fingerprint and triggers a private GitHub
runtime only when that projection changed.

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

The public `job-application-pipeline` repository owns:

- projection and fingerprint contracts,
- provider budget enforcement,
- the local dispatcher,
- the benchmark runner,
- the reusable GitHub workflow,
- tests and documentation.

A private runtime repository owns only:

- the `repository_dispatch` caller workflow,
- Tailscale, Tavily and PostgreSQL secrets,
- private run history and review artifacts.

Copy `docs/runtime/private_origin_runtime_caller.example.yml` to
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
- no provider call when the database fingerprint changed after dispatch,
- no provider call above the global request ceiling,
- artifacts are review output only and never pipeline input.

The dedicated PostgreSQL role has `default_transaction_read_only=on` and direct
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

The effective candidate count is reduced automatically when the configured
candidate/query combination would exceed the global provider request ceiling.

## Tool shopping list

### Required system tools

1. Git and the existing Pipeline checkout.
2. GitHub CLI (`gh`) authenticated as the repository owner.
3. Tailscale on the same machine/network namespace that hosts PostgreSQL.
4. PostgreSQL server and `psql` client for the one-time read-only role setup.
5. A private GitHub repository, for example `job-pipeline-runtime`.

### Existing Python dependencies

No new Python package is required. The repository already provides:

- `psycopg`,
- `requests`,
- `python-dotenv`.

Prepare or refresh the virtual environment with the normal project command:

```bash
cd ~/projects/job-application-pipeline
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip check
```

### Tailscale on Ubuntu/WSL2

Install Tailscale inside the environment that can directly reach PostgreSQL. If
PostgreSQL runs inside WSL2, install Tailscale in that WSL2 distribution rather
than relying on a separate Windows network namespace.

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale status
tailscale ip -4
```

The database host must stay online while the remote benchmark runs.

## One-time Tailscale configuration

1. Create a personal Tailscale tailnet.
2. Add a tag such as `tag:github-origin-benchmark` for ephemeral GitHub runners.
3. Tag the PostgreSQL host separately, for example `tag:pipeline-db`.
4. Permit only the GitHub benchmark tag to reach the database host on TCP 5432.
5. Create a Tailscale federated identity with the `auth_keys` capability and the
   GitHub benchmark tag.
6. Record its Client ID and Audience as private GitHub secrets.
7. Keep MagicDNS enabled or record the host's stable Tailscale DNS name.

The reusable workflow uses `tailscale/github-action@v4`, GitHub OIDC and an
ephemeral tagged node. It does not require a reusable Tailscale auth key.

## One-time PostgreSQL role setup

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
that password in the private runtime repository, not in `.env` committed files.

PostgreSQL must listen on the Tailscale interface and `pg_hba.conf` must permit
the dedicated user from the Tailscale address range. Keep all public Internet
access closed.

## Private runtime repository

Create a private repository, for example:

```bash
gh repo create jenshaberle-dotcom/job-pipeline-runtime --private
```

Copy and commit the caller workflow:

```bash
mkdir -p /tmp/job-pipeline-runtime/.github/workflows
cp docs/runtime/private_origin_runtime_caller.example.yml \
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
POSTGRES_USER=origin_benchmark_reader
POSTGRES_PASSWORD
```

`POSTGRES_HOST` should be the Tailscale MagicDNS hostname or stable Tailscale IP
of the database host.

## Local dispatch setup

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

Run the first provider-free dispatch preview:

```bash
python -m scripts.dispatch_origin_provider_benchmark_if_changed
```

After the private caller and secrets exist, test the event path:

```bash
python -m scripts.dispatch_origin_provider_benchmark_if_changed --dispatch
```

The dispatcher writes its last successful event state under
`.runtime/origin-provider-dispatch-state.json`. This path is ignored by Git.
An unchanged projection exits without sending an event or consuming Tavily
requests.

## Automatic integration after successful data refresh

Append the dispatcher only after the canonical local data command succeeds:

```bash
python -m <canonical-local-data-refresh-command> \
  && python -m scripts.dispatch_origin_provider_benchmark_if_changed --dispatch
```

For an existing shell script, use the same fail-closed pattern:

```bash
set -euo pipefail
python -m <canonical-local-data-refresh-command>
python -m scripts.dispatch_origin_provider_benchmark_if_changed --dispatch
```

A failed local pipeline command therefore cannot trigger the remote provider
runtime. A successful run with unchanged relevant data also triggers nothing.

## Operational behavior

### Changed data

1. GitHub validates the metadata-only event.
2. The runner checks out the exact committed Pipeline SHA.
3. The runner joins the tailnet as an ephemeral tagged node.
4. The runner re-reads the bounded database projection.
5. A fingerprint mismatch stops before Tavily.
6. A matching fingerprint permits the bounded Tavily benchmark.
7. A private report is retained for three days.

### Unchanged data

The local dispatcher exits successfully without contacting GitHub or Tavily.

### Database host offline

The GitHub job fails at the Tailscale ping or PostgreSQL connectivity check. No
fallback public database access is attempted.

### Data changes between dispatch and execution

The remote runner emits `stale_dispatch_fingerprint` and performs no provider
call. The next successful local refresh can dispatch the new fingerprint.

## Installation boundary

This slice prepares the Pipeline implementation and reusable workflow. It does
not:

- create the private runtime repository,
- create or modify Tailscale policy,
- create GitHub secrets,
- change PostgreSQL network configuration,
- execute Tavily,
- update the production database schema,
- activate a scheduler or source.
