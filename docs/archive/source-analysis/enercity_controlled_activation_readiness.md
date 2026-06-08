# S7U Employer-Origin Activation Readiness — enercity

## Boundary

This is a generic employer-origin activation readiness review.
It does not create or activate search profiles, register connectors, write Bronze records or change scheduler configuration.

Boundary flags:

- `database_writes`: `false`
- `search_profile_created`: `false`
- `source_activation_allowed`: `false`
- `bronze_persistence_allowed`: `false`
- `recurring_ingestion_allowed`: `false`
- `scheduler_change_allowed`: `false`
- `csv_or_export_inputs_used`: `false`

## Candidate

- company key: `enercity`
- company name: `enercity AG`
- source name: `enercity:discovery`
- source type: `employer_origin_career_site`
- status: `discovery`

## Inputs

- connector preview requested URL: https://www.enercity.de/karriere/jobsuche
- database evidence rows considered: 277
- active search profiles for this source: 0
- non-job preview records: 0

## Overall Readiness

- `activation_readiness_supported`

## Readiness Counts

- activation_readiness_supported: 2

## Uniqueness Counts

- incrementally_unique_candidate: 2

## Candidate Results

- `activation_readiness_supported` — Cloud Infrastructure & DevOps Engineer (f/m/d) – Azure Focus
  - uniqueness decision: incrementally_unique_candidate
  - url: https://www.enercity.de/karriere/jobsuche/cloud-infrastructure-devops-engineer-f-m-d-azure-focus-J2026011
  - external job id: cloud-infrastructure-devops-engineer-f-m-d-azure-focus-J2026011:2fabb8ff5e85
  - profile terms: data; daten; analytics; analyst; business analyst; bi; sql; python; ki; ai; software; entwickler; javascript; ui; product owner
  - location terms: hannover; remote; deutschland; hybrid
  - best match: raw_jobs 9958 stepstone
  - best match title: Cloud/DevOps Engineer (m/w/d)
  - best match source url: https://www.stepstone.de/stellenangebote--Cloud-DevOps-Engineer-m-w-d-Hamburg-Hannover-Berlin-Muenchen-Stuttgart-Frankfurt-Koeln-Duesseldorf-Computer-Futures--13994942-inline.html
  - title similarity: 0.5
  - evidence similarity: 0.069
  - reason: No sufficiently similar existing evidence was found. Readiness interpretation: Candidate appears to add incremental source value compared with current raw/Silver evidence.
- `activation_readiness_supported` — Manager:in Trinkwasserschutz und Entschädigungsmanagement
  - uniqueness decision: incrementally_unique_candidate
  - url: https://www.enercity.de/karriere/jobsuche/manager-in-trinkwasserschutz-und-entschaedigungsmanagement-J2026258
  - external job id: manager-in-trinkwasserschutz-und-entschaedigungsmanagement-J2026258:2ef065075ae5
  - profile terms: data; daten; bi; ki; ai; javascript; ui
  - location terms: hannover; remote; deutschland
  - best match: silver_jobs 186 finanz_informatik:hannover
  - best match title: Software-Entwickler (m/w/d)
  - best match source url: https://www.f-i.de/de/karriere/offene-stellen/hannover/software-entwickler-m-w-d
  - title similarity: 0.0
  - evidence similarity: 0.261
  - reason: No sufficiently similar existing evidence was found. Readiness interpretation: Candidate appears to add incremental source value compared with current raw/Silver evidence.

## Next Step

A separate controlled activation migration may be prepared only if this readiness review is accepted.
That later migration must explicitly create or activate a bounded search profile and remain separate from this review artifact.
