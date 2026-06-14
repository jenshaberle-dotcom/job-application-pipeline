# Work Item Naming and Domain Prefixes

This project uses short domain prefixes for implementation blocks, branches, PRs and retired restart notes. The goal is to keep names understandable in the repository and reusable for future projects, while avoiding historically grown labels such as `A2H2` as the primary identifier.

This document is a lightweight development convention, not an ADR. Add new domains only when an existing domain would make the work item misleading.

## Format

Use this shape for new work items:

```text
<DOMAIN>-<NNN> <short readable title>
```

Examples:

```text
SI-014 Candidate Duplicate Preflight Guard
EO-008 Employer-Origin Connector Validation
CC-004 Review Queue Action Dialogs
DB-003 Migration Tracking Repair
DOC-006 Documentation Consistency Review
```

Recommended branch and PR naming:

```text
feature/si-014-candidate-duplicate-preflight
[SI-014] Add candidate duplicate preflight guard
```

The numeric part is a work-item sequence, not a migration number and not a sprint number. It does not need to be globally perfect; clarity is more important than historical archaeology.

## Core domains

Use as few domains as possible. Prefer these until a new domain is clearly needed.

| Prefix | Domain | Use for |
| --- | --- | --- |
| `SI` | Search Intelligence | Discovery logic, observation, learning loops, pattern promotion, source/candidate intelligence, false-negative reduction, reprocess benchmarks. |
| `EO` | Employer Origin | Employer-origin source candidates, gates, connector readiness, connector build/validation, source activation boundaries. |
| `CC` | Control Center | Server-rendered UI, review queue, operations actions, dialogs, dashboard/control-center presentation. |
| `DB` | Database & Migrations | Schema changes, migration tracking, idempotent repair migrations, database constraints/views. |
| `DOC` | Documentation & Governance | ADRs, architecture docs, naming conventions, roadmap alignment, design rules, retired restarts. |
| `OPS` | Operations & Automation | Scheduler, local/CI operations, watchdogs, runbooks, cleanup workflows, operational safety. |

## Optional future domains

Only introduce these when the work becomes large enough that the core domains stop being clear.

| Prefix | Domain | Use for |
| --- | --- | --- |
| `SRC` | Source Acquisition | New source-family strategy, aggregator/source discovery, source lifecycle scoring. Prefer `SI` or `EO` first when the work is clearly part of those domains. |
| `APP` | Application Materials | Future CV, cover-letter, application tracking and job-to-application scaffolding. |
| `SEC` | Security & Compliance | Secret handling, legal-stop/remove workflows, compliance-specific controls. Prefer `OPS` or `DB` if the work is mainly operational or schema-level. |

## Boundary rules

- Do not rename old branches, commits or documents only to retrofit this convention.
- When referencing historic labels, include a mapping once, for example: `A2H2 / SI-014 Candidate Duplicate Preflight Guard`.
- Use readable titles. The prefix is not a substitute for a meaningful name.
- Avoid creating a new domain for every feature area. Start with `SI`, `EO`, `CC`, `DB`, `DOC`, and `OPS`.
- If a work item crosses domains, choose the domain where the main decision or system boundary lives.
- For migrations, keep migration numbers independent from work-item IDs.

## Current mapping for recent historical labels

| Historical label | Preferred name |
| --- | --- |
| `A2E` | `SI-010 Observation Seed Pool Expansion` |
| `A2G` | `SI-012 Reprocess Benchmark Apply Fix` |
| `A2H` | `SI-013 Candidate Identity / Missing URL Guard` |
| `A2H2` | `SI-014 Candidate Duplicate Preflight Guard` |
