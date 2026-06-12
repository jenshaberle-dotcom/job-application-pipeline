# Active Roadmap

Status: active planning
Last rebaseline: DOC-001M

This file is intentionally short. Historical checklists and build notes live in
`../archive/planning/` and Git history.

## Current freeze path

| Order | Block | Status | Purpose |
|---|---|---|---|
| 1 | GOV-001 Agent Governance Foundation | done | Reviewable agent behavior. |
| 2 | DOC-001A-M Documentation Rebaseline | done/current | Current truth, archive split and lean active docs. |
| 3 | STOP-002 Stop Taxonomy | done/expand | Stops and repair paths explicit. |
| 4 | GENERIC/EXPAND Candidate Creation | current | Prove generic evidence before any apply-capable path. |
| 5 | V1 Job Review Path | next | Make a controlled Top-5/job-review workflow usable, including GUI. |
| 6 | REFACTOR-001 | planned gate | Refactor before cloud, outbox, Kafka, Spark or productionization. |
| 7 | FREEZE-002 Pipeline Maturity to V1 | planned campaign | Raise remaining pipeline areas toward >=90% without derailing V1. |

## Current product priorities

| Area | Current focus |
|---|---|
| GENERIC/EXPAND | Close stop-control and evidence blockers before apply design. |
| Search Intelligence | Improve discovery closure and source/origin evidence generically. |
| GUI | Build approval-safe review actions and a usable Review Queue. |
| Operations | Keep scheduler/run/defect states visible before cloud migration. |
| Documentation | Keep current truth lean; archive historical build traces. |

## Architecture freeze rule

<!-- ARCH-001-SAFETY-SECURITY-STATE:START -->
ARCH-001 remains active. New changes must preserve safety, security, data
integrity and explicit state transitions. Opportunistic scope expansion should go
to the backlog unless it materially improves safety, diagnosis, generics or
product maturity.
<!-- ARCH-001-SAFETY-SECURITY-STATE:END -->

## Contract anchors

### DOC-001 Governance Foundation Gate
DOC-001 protects the documentation/governance freeze path while Search
Intelligence continues to evolve.

### DOC-002 Documentation Drift Baseline
DOC-002 prevents silent documentation drift and keeps docs tied to executable
architecture, governance and implementation reality.

### EO-002B Candidate Reprocessing & URL Finder Validation
EO-002B keeps candidate reset/reprocess and URL-recovery safety visible while
detailed history stays archived.

### EO-002D-ROADMAP
EO-002D anchors bounded origin-source discovery and URL-finder repair boundaries.

<!-- PLAN-001-ROADMAP-START -->
## PLAN-001 Future Readiness and Assumption Governance

Active planning anchor for future readiness without expanding current scope:
event-capable-not-event-driven, CLOUD-001, EVENT-001, STREAM-001, SPARK-001,
MARKET-003 Manual Market Observation Foundation, ASSUMPTION-001 Simplification Validation Register and WHALE-001 White-Whale Backlog Triage.

Details: `docs/planning/active/future_readiness_and_assumption_governance.md`.
<!-- PLAN-001-ROADMAP-END -->

<!-- REFACTOR-001-ROADMAP-START -->
## REFACTOR-001 Architecture & Runtime Refactor Campaign

Planned gate after GENERIC/EXPAND blocker closure and a minimal controlled V1
job-review path; before cloud migration, DB-backed outbox, Kafka/event backbone,
Spark analytics/replay or serious productionization.

Details: `docs/planning/active/refactor001_architecture_runtime_refactor_campaign.md`.
<!-- REFACTOR-001-ROADMAP-END -->

<!-- FREEZE-002-ROADMAP-START -->
## FREEZE-002 Pipeline Maturity to V1 Campaign

Second freeze campaign: raise remaining pipeline parts toward >=90% while
preserving the current route to a usable V1 with GUI. It should improve weak
areas in parallel where independent, but must not move the core order: generic
evidence -> controlled V1 review path -> REFACTOR-001 -> cloud/event expansion.

Details: `docs/planning/active/freeze002_pipeline_maturity_to_v1_campaign.md`.
<!-- FREEZE-002-ROADMAP-END -->
