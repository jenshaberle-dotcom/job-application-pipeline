# REFACTOR-001 Architecture & Runtime Refactor Campaign

Status: planned gate, not active implementation

Scope: architecture, runtime boundaries, maintainability, cloud readiness,
compliance/governance auditability, defect management and event readiness. This
campaign does not introduce cloud infrastructure, Kafka, Spark, candidate/gate
mutation, connector activation or scheduler behavior changes by itself.

## Purpose

REFACTOR-001 is the planned refactoring gate before serious productionization,
cloud migration or event-streaming expansion.

The project has intentionally prioritized learning speed, evidence discovery,
governance and candidate-expansion proof. After many PRs, the next risk is not a
missing idea but accumulated implementation shape: scripts, reports, runtime
helpers, planning anchors and decision boundaries must be made easier to operate,
test and migrate before cloud or streaming layers are added.

The campaign should answer:

- Which runtime modules and scripts are stable enough to keep?
- Which script/report clusters should become explicit services, view models or
  reusable library functions?
- Which DB, scheduler, event and audit boundaries would block cloud migration?
- Which stop/repair/error states should become defect-management vocabulary?
- Which tests protect real behavior and which are only local implementation
  scaffolding?
- Which documentation/governance anchors are still current and which should be
  archived after implementation reality has moved on?

## Sequencing rule

Do not start REFACTOR-001 immediately while the current GENERIC/EXPAND
candidate-creation proof is midstream, unless a concrete technical blocker makes
safe progress impossible.

Preferred sequence:

1. Finish the current GENERIC-006 / EXPAND-008 block and handover.
2. Close the immediate stop-control and generic-evidence blocker.
3. Reach a minimal controlled V1 proof path for real job review, including the
   Top-5/job-review direction and approval-safe review workflow.
4. Run REFACTOR-001 as a bounded campaign.
5. Only then continue with cloud migration, DB-backed outbox, Kafka/event backbone,
   Spark analytics/replay or serious productionization.

The intent is not to stop product progress now. The intent is to prevent a later
cloud/streaming/compliance migration from being built on a runtime shape that is
hard to audit, test or operate.

## Campaign phases

### REFACTOR-001A Inventory and risk map

Create a read-only inventory of runtime surfaces:

- scripts,
- source modules,
- migrations and SQL/view contracts,
- scheduler entry points,
- report generators,
- UI/view-model boundaries,
- tests,
- documentation and governance anchors.

Classify each item by responsibility, owner surface, mutation risk, cloud risk,
audit/compliance relevance, defect visibility and test coverage.

### REFACTOR-001B Boundary and module plan

Define target module boundaries without rewriting everything at once:

- Discovery,
- Evidence,
- Candidate/Gate,
- Connector,
- Scheduler/Ops,
- Reports/Observability,
- UI view models,
- Governance/Validation,
- Defect Management.

The output should be a staged refactor map, not a broad unreviewable rewrite.

### REFACTOR-001C Defect and stop/error taxonomy alignment

Align existing stop taxonomy, repair strategies, report failures, scheduler
failures and runtime exceptions with a future defect-management vocabulary.

This does not need a full defect-management product immediately, but it should
make technical, operational, pipeline and governance defects distinguishable.

### REFACTOR-001D Cloud and event-readiness boundary pass

Prepare the existing batch-first architecture for later cloud/event evolution by
checking:

- stable IDs,
- timestamps and provenance,
- idempotent command/report behavior,
- outbox-ready event vocabulary,
- no hidden CSV/Excel/export inputs,
- no local-only assumptions that would block cloud execution,
- clear separation between read-only inspection and write/apply commands.

This phase keeps the rule: event-capable, but not event-driven yet.

### REFACTOR-001E Staged implementation PRs

Implement the refactor in small or medium staged PRs. Each PR must preserve
current behavior or explicitly document a behavior change.

Avoid one giant rewrite. Prefer:

- extract shared helpers,
- reduce duplicated SQL/template/report logic,
- clarify service boundaries,
- add architecture tests where useful,
- archive obsolete planning docs after the code reality changes,
- keep full validation green at each step.

## Non-goals

REFACTOR-001 must not be used as a hidden excuse to introduce:

- automatic candidate creation,
- gate bypasses,
- connector activation,
- new crawlers or unbounded external requests,
- Kafka or Spark before the platform sequence reaches that step,
- cloud infrastructure before core/cloud-readiness prerequisites are met,
- CSV/Excel/export artifacts as pipeline inputs.

## Decision checkpoint

REFACTOR-001 becomes the next active campaign when one of these is true:

- minimal controlled V1 job-review path is proven,
- cloud migration planning becomes more than a paper exercise,
- scheduler/operations complexity blocks safe product progress,
- defect-management needs become operational rather than theoretical,
- architecture drift starts increasing faster than validation/governance can
  explain it.

Until then, keep REFACTOR-001 visible as a planned gate and continue closing the
current GENERIC/EXPAND evidence blocker.
