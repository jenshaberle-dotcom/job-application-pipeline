# ADR-007 — Use SSH for GitHub Authentication

## Status

Accepted

---

## Context

Initial GitHub integration used HTTPS authentication with access tokens.

This created:
- repeated authentication prompts
- credential management friction
- reduced developer experience

The project should use:
- secure authentication
- stable Git workflows
- realistic engineering practices

---

## Decision

Use SSH-based authentication for GitHub access.

SSH keys are managed locally and GitHub access is performed using SSH remotes.

---

## Consequences

### Positive

- improved developer experience
- reduced authentication friction
- stable Git workflows
- realistic engineering setup

### Negative

- initial SSH setup complexity
- SSH key management requirements
