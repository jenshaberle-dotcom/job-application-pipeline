# ADR-008 — Use Environment-Based Configuration

## Status

Accepted

---

## Context

The project requires configurable runtime settings such as:
- database credentials
- API keys
- environment-specific configuration

Hardcoded credentials would:
- reduce security
- prevent environment portability
- create secret leakage risks

---

## Decision

Use environment-based configuration via `.env` files during local development.

Secrets are excluded from Git version control using `.gitignore`.

Future cloud deployments may migrate to:
- Azure Application Settings
- Azure Key Vault
- managed secret providers

---

## Consequences

### Positive

- improved secret separation
- better environment portability
- safer version control usage
- realistic cloud migration path

### Negative

- additional local configuration steps
- dependency on local environment management
