# JAP Classic documentation

Start with the current system, then the task-specific guide. This documentation describes
Classic's implemented local product and the transition to Cloud; open PRs are proposals.

## Read first

| Need | Entry point |
|---|---|
| Product scope and private-data boundaries | [Product](current/product.md) |
| Components and Cloud transition | [Architecture](current/architecture.md) |
| Acquisition and decision flow | [Pipeline](current/pipeline.md) |
| Engineering values | [Principles](current/engineering_principles.md) |
| Architecture diagrams | [Diagrams](current/system-diagrams.md) |
| Install/update the Windows app | [Windows guide](guides/jap_control_center_windows_app.md) |
| Operate or recover | [Runbook](guides/operator-runbook.md) |
| Change code and validate | [Workflow](guides/development-workflow.md), [testing](guides/testing.md) |
| Runner and release execution | [RCC contract](current/ci-max-execution.md), [release management](../.github/RELEASE_MANAGEMENT.md) |
| Continue engineering | [Re-entry](current/REENTRY.md), [roadmap](planning/active/roadmap.md) |
| Exact product intent | [Product contracts](reference/product-contract/README.md) |

## Structure and authority

The documentation architecture applies to files, not only folders.

- `current/`: maintained implementation facts and effect boundaries.
- `guides/`: executable task instructions, with prerequisites and failure handling.
- `reference/`: stable contracts and models; implementation evidence remains code and tests.
- `decisions/`: why a decision was taken; consult the [status table](decisions/adr_status_table.md).
- `planning/`: current roadmap, explicitly future proposals and generated source-candidate reviews.
- `archive/`: historical evidence only. Its old commands, priorities and counts are not current instructions.

Approved operator decisions govern desired behavior. Code/configuration and exact-source
validation establish implementation. Fresh runtime evidence establishes deployment and live
results. Unknown runtime state remains unknown. Old snapshots, chat and exports cannot override
these boundaries.

Completed implementation notes and conflicting restart narratives are removed rather than
maintained as a second backlog. Their original text remains in Git history. Accepted product
contracts remain available as reference. See [hardcut disposition](reference/documentation/hardcut-20261002.md).

## Checks

```bash
python scripts/check_documentation_references.py --json
python scripts/check_documentation_architecture.py --json
python scripts/check_adr_rebaseline.py --json
python scripts/check_classic_documentation_truth.py
```

Database reference: [schema](reference/database/schema_overview.md),
[relationships](reference/database/schema_relationships.md).
