# ORIGIN-PROVIDER-001A Tool Checklist

Use this checklist only after the implementation pull request is accepted and
merged. It performs no automatic installation or secret creation.

## Local machine

- [ ] GitHub CLI installed and `gh auth status` succeeds.
- [ ] Pipeline virtual environment refreshed from `requirements-dev.txt`.
- [ ] Tailscale installed in the same WSL2/Linux network namespace as PostgreSQL.
- [ ] PostgreSQL is reachable locally and the `psql` client is installed.
- [ ] Database host remains online during remote benchmark execution.

## Private GitHub runtime repository

- [ ] Private repository created.
- [ ] Runtime caller copied from the Pipeline template.
- [ ] Reusable workflow pinned to the accepted Pipeline merge SHA.
- [ ] `repository_dispatch` workflow present on the private default branch.
- [ ] Required Actions secrets created.

## Tailscale

- [ ] Personal tailnet created.
- [ ] GitHub ephemeral runner tag configured.
- [ ] Database host tag configured.
- [ ] ACL/grant permits only runner tag to DB host TCP 5432.
- [ ] Federated identity Client ID and Audience created for GitHub OIDC.
- [ ] MagicDNS hostname or stable tailnet IP recorded.

## PostgreSQL

- [ ] `origin_benchmark_reader` created from repository-owned SQL.
- [ ] Password stored only as private runtime secret.
- [ ] `default_transaction_read_only=on` verified.
- [ ] User can select required tables and cannot insert, update or delete.
- [ ] PostgreSQL listens on the Tailscale interface.
- [ ] `pg_hba.conf` permits the dedicated user only from the intended tailnet range.

## Private repository secrets

- [ ] `TS_OAUTH_CLIENT_ID`
- [ ] `TS_AUDIENCE`
- [ ] `TAVILY_API_KEY`
- [ ] `POSTGRES_HOST`
- [ ] `POSTGRES_PORT`
- [ ] `POSTGRES_DB`
- [ ] `POSTGRES_USER`
- [ ] `POSTGRES_PASSWORD`

## Activation

- [ ] `ORIGIN_RUNTIME_REPOSITORY` set only in local `.env`.
- [ ] Provider-free dispatcher preview reviewed.
- [ ] First event path executed with bounded defaults.
- [ ] Private artifact inspected and confirmed as review-only.
- [ ] Dispatcher appended only after the canonical local data-refresh command succeeds.
