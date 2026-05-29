# Employer-Origin Final Approval Gate Agent

## Status

Implemented as S4C human approval workflow.

## Purpose

The final approval gate records explicit human approval before connector registration may proceed.

The required approval token is:

```text
approve_connector_registration
```

## Boundary

This gate may allow connector registration planning, but it does not activate sources, write Bronze rows or enable recurring ingestion.
