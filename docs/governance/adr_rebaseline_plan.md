# ADR Rebaseline Plan

Status: DOC-001B current plan  
Scope: ADR status review and current decision anchor recovery

## Intent

ADRs have not been the dominant decision anchor during recent fast-moving
pipeline work. Many decisions moved through planning docs, governance docs,
runtime reports, PR bodies, and handover context.

DOC-001 must restore ADR usefulness without backfilling every detail into many
new ADRs.

## Inventory basis

DOC-001A found:

- 34 ADR files,
- 30 ADRs marked current/accepted by existing status parsing,
- 3 ADRs with unclassified status,
- 1 ADR file needing status review.

Existing status is not enough. Each ADR still needs DOC-001 classification:

- Current,
- Superseded,
- Historical,
- Needs rewrite.

## Rebaseline categories

### Current

Still describes an active architecture decision.

A current ADR should be referenced or compatible with the Current Truth docs.

### Superseded

Was valid, but has been replaced by a newer decision.

A superseded ADR should point to the replacement decision or Current Truth doc.

### Historical

Useful context, but not a current decision anchor.

Historical ADRs may remain for traceability but should not guide implementation.

### Needs rewrite

The decision is still important, but the document no longer reflects the actual
system or uses obsolete terminology.

## Candidate current ADR themes

Likely still current or partly current:

- PostgreSQL as primary database,
- Dockerized local development,
- environment-based configuration,
- connector-based ingestion,
- Bronze-first/raw-first approach,
- source capability model,
- source family/target/type separation,
- search-intelligence safety/security boundaries,
- Jinja2 as intermediate Control Center template layer,
- platform visual identity.

These still require review.

## Candidate missing ADRs

Only a few new ADRs should be created after GOV/DOC rebaseline confirms stable
system decisions.

Likely candidates:

1. Agent Governance and Capability Audit Model.
2. Documentation Rebaseline and Current Truth Documentation Policy.
3. Pipeline Stop Reassessment and Stage-2 Repair Planning.
4. Exports Are Reports, Not Pipeline Inputs.
5. Architecture Freeze / Maturity Campaign.

## Non-goal

Do not write one ADR per recent implementation block.

Recent planning documents remain historical build logs unless their content is
promoted into a stable architecture decision.

## DOC-001 follow-up

DOC-001C or DOC-001D should create an ADR status table with one row per ADR:

```text
ADR | Current DOC-001 status | Action | Replacement/current-truth pointer
```

Only after that table exists should we edit individual ADR files.
