# enercity AG Connector Candidate Implementation

## Status

Generated from DB-backed approval-gated connector evidence. For S7Q artifact reviews this may include S7O build-queue sample evidence.

## Boundary

This is a connector candidate implementation, not a controlled activation.

It does not approve:

- recurring ingestion
- Bronze persistence by itself
- broad crawling
- browser automation
- CSV/Excel/export artifacts as inputs
- raw HTML persistence

## Source Identity

- company key: `enercity`
- source name: `enercity:discovery`
- source family: `enercity`
- source target: `None`
- source type: `employer_origin_career_site`
- listing URL: `https://www.enercity.de/karriere/jobsuche`

## Generated Files

- module: `src/connectors/enercity.py`
- tests: `tests/test_enercity_connector.py`
- class: `EnercityConnector`

## Detail Evidence Carried Forward

Concrete job-detail evidence carried into the connector candidate:
- https://www.enercity.de/karriere/jobsuche/cloud-infrastructure-devops-engineer-f-m-d-azure-focus-J2026011
- https://www.enercity.de/karriere/jobsuche/manager-in-trinkwasserschutz-und-entschaedigungsmanagement-J2026258

Broader career-context URLs were present in the evidence, but are not treated as job-detail evidence:
- https://www.enercity.de/karriere/arbeiten
- https://www.enercity.de/karriere/wir

## Next Gate

A separate controlled activation gate must decide whether this connector candidate may be registered in the ingestion runner and activated through a search profile migration.
