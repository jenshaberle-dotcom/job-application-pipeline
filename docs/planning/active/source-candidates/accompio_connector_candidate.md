# accompio GmbH Connector Candidate Implementation

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

- company key: `accompio`
- source name: `accompio:discovery`
- source family: `accompio`
- source target: `None`
- source type: `employer_origin_career_site`
- listing URL: `https://karriere.accompio.com/de`

## Generated Files

- module: `src/connectors/accompio.py`
- tests: `tests/test_accompio_connector.py`
- class: `AccompioConnector`

## Detail Evidence Carried Forward

Concrete job-detail evidence carried into the connector candidate:
- https://karriere.accompio.com/de?id=51980f
- https://karriere.accompio.com/de?id=458ccb
- https://karriere.accompio.com/de?id=54663b
- https://karriere.accompio.com/de?id=84543f
- https://karriere.accompio.com/de?id=57f643

## Next Gate

A separate controlled activation gate must decide whether this connector candidate may be registered in the ingestion runner and activated through a search profile migration.
