# Computacenter AG & Co. oHG Connector Candidate Implementation

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

- company key: `computacenter`
- source name: `computacenter:discovery`
- source family: `computacenter`
- source target: `hannover`
- source type: `employer_origin_career_site`
- listing URL: `https://jobs.computacenter.com/search/?searchby=location&q=&locationsearch=&geolocation=&optionsFacetsDD_country=&optionsFacetsDD_city=`

## Generated Files

- module: `src/connectors/computacenter.py`
- tests: `tests/test_computacenter_connector.py`
- class: `ComputacenterConnector`

## Detail Evidence Carried Forward

Concrete job-detail evidence carried into the connector candidate:
- https://jobs.computacenter.com/job/Hatfield-Director-of-Internal-Audit-AL10-9TW/1402547933/
- https://jobs.computacenter.com/job/Berlin-IT-Security-Consultant-wmd-Privilege-Access-Management-12099/1402370533/
- https://jobs.computacenter.com/job/Budapest-Financial-Analyst-Intercompany-1095/1412917333/
- https://jobs.computacenter.com/job/Hatfield-GIS-BISO-AL10-9TW/1402282333/
- https://jobs.computacenter.com/job/Nottingham-Application-Packager-%28SC-Cleared%29-NG8-6AT/1412877833/

## Next Gate

A separate controlled activation gate must decide whether this connector candidate may be registered in the ingestion runner and activated through a search profile migration.
