# ADR Status Table

Status: current ADR rebaseline control surface
Scope: DOC-001K ADR rebaseline
Last rebaseline: DOC-001K

## Purpose

The ADR directory still contains useful decisions, but several ADRs were written
before the Search Intelligence architecture, governance layer, Control Center and
DOC-001 documentation rebaseline matured.

This table is the current DOC-001K control surface for ADR usage. It does not
rewrite every ADR. It tells readers which ADRs remain current, which are
historical, which are superseded, and which need a focused rewrite before they
are used as active architecture anchors.

## Status vocabulary

| DOC-001K status | Meaning | Reader instruction |
|---|---|---|
| Current | Still an active architecture decision. | Use together with the listed Current Truth pointer. |
| Superseded | Replaced or materially narrowed by a newer decision. | Prefer the replacement pointer. Keep the ADR as history. |
| Historical | Useful context but not an active architecture rule. | Do not use as an implementation driver. |
| Needs rewrite | Decision area is still important, but the ADR status/text no longer matches the current system well enough. | Do not build on it without a rewrite or explicit follow-up. |

## Current ADR status table

| ADR | Repository status | DOC-001K status | Action | Current Truth / replacement pointer |
|---|---|---|---|---|
| ADR-001 | Accepted | Current | Keep as foundational source-realism decision. | `docs/architecture/current_system_overview.md` |
| ADR-002 | Accepted | Current | Keep; interpret through raw-first/tolerant Bronze and later evidence gates. | `docs/architecture/current_system_overview.md`, `docs/database/schema_overview.md` |
| ADR-003 | Accepted | Current | Keep; database uniqueness remains a protection layer, not the full dedupe story. | `docs/database/schema_overview.md` |
| ADR-004 | Accepted | Current | Keep; profile-based ingestion still frames bounded search. | `docs/architecture/current_system_overview.md` |
| ADR-005 | Accepted | Current | Keep. | `docs/database/README.md` |
| ADR-006 | Accepted | Current | Keep for local reproducibility. | `README.md`, `docs/operations/runbook.md` |
| ADR-007 | Accepted | Historical | Keep as local Git/GitHub setup history, not product architecture. | `docs/operations/runbook.md` |
| ADR-008 | Accepted | Current | Keep; environment-based configuration remains the safe default. | `README.md` |
| ADR-009 | Accepted | Current | Keep; connectors remain the acquisition abstraction. | `docs/data_sources/source_capabilities.md` |
| ADR-010 | Accepted | Current | Keep with caveat that true canonical-source resolution remains deferred. | `docs/database/schema_overview.md` |
| ADR-011 | Accepted | Current | Keep; technical duplicates and cross-source matching remain separate. | `docs/database/schema_overview.md` |
| ADR-012 | Accepted | Current | Keep; observation/source-value concepts remain active. | `docs/database/schema_overview.md`, `docs/observability/source_health_and_heartbeat.md` |
| ADR-013 | Accepted | Current | Keep as product-intent ancestor; prefer Current System Overview for wording. | `docs/architecture/current_system_overview.md` |
| ADR-014 | Accepted | Current | Keep; database docs were rebaselined in DOC-001H. | `docs/database/README.md` |
| ADR-015 | Accepted | Current | Keep; capabilities remain a central source boundary. | `docs/data_sources/source_capabilities.md` |
| ADR-016 | Accepted | Current | Keep; interpret through current Search Intelligence and aggregator boundaries. | `docs/architecture/current_system_overview.md`, `docs/adr/026_define_source_acquisition_scope_and_canonical_source_strategy.md` |
| ADR-017 | Proposed | Superseded | Keep for future API/React direction only; current UI layer is Jinja2/ViewModel first. | `docs/adr/032_use_jinja2_as_control_center_template_layer.md` |
| ADR-018 | Accepted | Current | Keep; migration ordering remains protected. | `docs/operations/runbook.md`, `db/migrations` |
| ADR-019 | Proposed | Needs rewrite | Rewrite or accept/reject explicitly before dedicated heartbeat work. | `docs/observability/source_health_and_heartbeat.md` |
| ADR-020 | Proposed | Needs rewrite | Rewrite or explicitly defer before role-family implementation becomes active. | `docs/classification/role_family_classification.md` |
| ADR-021 | Accepted | Current | Keep; source capability expansion remains current. | `docs/data_sources/source_capabilities.md` |
| ADR-022 | Accepted | Current | Keep; shared terminology remains useful. | `docs/architecture/search_intelligence_terminology.md` |
| ADR-023 | Accepted | Current | Keep; search-result connector contract remains active. | `docs/data_sources/search_result_connector_contract.md` |
| ADR-024 | Accepted | Current | Keep; relevance/search-quality boundary remains active. | `docs/relevance/relevance_strategy.md` |
| ADR-025 | Accepted | Current | Keep; search-term lineage remains required for quality evaluation. | `docs/relevance/relevance_strategy.md` |
| ADR-026 | Accepted | Current | Keep as key aggregator/employer-origin/source-value boundary. | `docs/architecture/current_system_overview.md` |
| ADR-027 | Accepted | Current | Keep; source-target acquisition model remains active. | `docs/data_sources/source_capabilities.md` |
| ADR-028 | Accepted | Current | Keep; family/target/type separation remains active. | `docs/architecture/source_taxonomy_and_source_roles.md` |
| ADR-029 | Accepted | Current | Keep; historical burden strategy remains active. | `docs/archive/documentation_path_status.md` |
| ADR-030 | Accepted | Current | Keep; trend/source-coverage boundary remains active. | `docs/database/schema_overview.md` |
| ADR-031 | Accepted | Current | Keep; Deep Ocean identity remains the preferred product identity. | `docs/design/README.md` |
| ADR-032 | Accepted | Current | Keep; Jinja2 is the current Control Center presentation layer. | `docs/design/documentation_design_rules.md` |
| ADR-033 | Accepted | Current | Keep; Search Intelligence safety/security boundary remains active. | `docs/architecture/safety_security_state_architecture.md` |

## Immediate follow-up queue

The table deliberately separates safe classification from editing every ADR.
The next ADR work should be focused:

1. rewrite or formally accept/reject ADR-019 before dedicated heartbeat/source-health implementation,
2. rewrite or explicitly defer ADR-020 before role-family classification becomes an active pipeline feature,
3. add one small ADR only for stable DOC/GOV decisions if the existing Current Truth docs need an architecture-decision anchor,
4. avoid creating one ADR per implementation block.

## Maintenance rule

When a new ADR file is added or an old ADR file is renamed, update this table and
run:

```bash
python scripts/check_adr_rebaseline.py --json
```

The ADR table is a control surface. It is not a replacement for individual ADRs,
but it prevents stale ADR status from silently becoming architecture truth.
