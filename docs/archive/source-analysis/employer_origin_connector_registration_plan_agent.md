# Employer-Origin Connector Registration Plan Agent

## Status

Implemented as S3C candidate workflow.

## Purpose

The connector registration plan agent creates a reviewable registration plan from DB-backed gate evidence.

It does not register the connector. It documents what would be needed after connector generation and which manual approval token is required.

## Manual Approval Token

The required token is:

```text
approve_connector_registration
```

Without that explicit approval, connector registration must not happen.

## Boundary

The registration plan agent does not:

- register connectors
- activate sources
- write Bronze rows
- create source activation migrations
- enable recurring ingestion
- use CSV/Excel/export artifacts as inputs

The generated Markdown plan is a review artifact only.
