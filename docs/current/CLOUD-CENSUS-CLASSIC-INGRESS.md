# Cloud Census → Classic

Operator decision, 2026-10-20:

- Bronze retains the complete supplied employer census and source observations,
  including firms outside Hannover and observations without websites.
- Silver normalizes actual job fields; employer candidates are not jobs.
- Gold applies Jens's profile, including geography/remote relevance. Unknown
  location or remote eligibility must remain unknown, not become a positive match.
- Connector qualification, real vacancies and profile relevance are separate counts.

## Current delivery boundary

Migration 117 and `scripts/import_cloud_census.py` prepare atomic, repeatable
ingress. The Cloud exporter `scripts/export_census_for_classic.py` reads the
whole stored population and verifies the original SQL receipt before writing
the local export. A digest validates content integrity, not independent authenticity:
the import input must be the retained export from that trusted reader.

Import defaults to planning. Apply stores every raw candidate in Bronze and
creates discovery candidates only when there is no conflicting identity.
Existing candidate settings are never overwritten. Ambiguous name/key matches
remain `IDENTITY_REVIEW` in Bronze and must be included in the campaign denominator.
Supplied websites are retained as observations, not promoted to qualified career
URLs. They still need the factory origin-discovery handoff.

No connector activation, network acquisition, ingestion, profile rule change,
RCC request, scheduling change or lease release is performed by this importer.
Repeated identical imports do not create candidates again. A run with changed
content is rejected. Import and candidate projection share one transaction.

## Evidence and remaining gates

- Classic candidate input: 74 rows on 2026-10-20.
- Cloud historical population: 1,735, run
  `cloud-census:5f5c73d189ea46056db9b11aa8912afcc8df2c4f`.
- Live export blocked on 2026-10-20: SQL reports that the database cannot be
  connected to in its current state. ARM reports Online, with Free Limit
  AutoPause enabled and no current allowance metric. Cause not yet established.
- No population was exported or imported; migration 117 has not been applied.
- Eight unit tests pass for full population retention, lineage/digest/count
  rejection, identity collisions and no geographical filtering.
- PostgreSQL transaction integration, origin-discovery handoff, RCC carrier,
  GUI readback and a full Factory execution remain unqualified.

After SQL is accessible: retain the complete verified export, qualify migration
and transaction behavior on an isolated PostgreSQL database, inspect the import
plan, then apply through the reviewed RCC/installation path. Do not present
the preparatory implementation as an executed RCC job or completed data transfer.
