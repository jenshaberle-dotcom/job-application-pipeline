# Employer-Origin Connector Validation Agent

## Status

Implemented as S3D candidate workflow.

## Purpose

The connector validation agent validates a generated connector candidate before final approval.

It checks expected connector files, module import, compileall and optionally pytest. It records `connector_validation_gate`.

## Boundary

The validation agent does not register connectors, activate sources, write Bronze rows, enable recurring ingestion or use CSV/Excel/export artifacts as inputs.
