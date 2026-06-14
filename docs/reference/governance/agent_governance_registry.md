# GOV-001B Agent Governance Registry Foundation

Status: foundation draft, generated from GOV-001A read-only intake.

## Purpose

This registry is the current governance anchor for pipeline agents. It separates agent responsibilities, write posture, safety boundaries, and capability-audit needs before further pipeline expansion.

## Intake baseline

- Intake campaign: `GOV-001A Agent Governance Inventory & Capability Audit Intake`
- Generated at: `2026-06-07T22:12:17.637415+00:00`
- Git baseline: `a545f04 (HEAD -> main, origin/main) Add EO candidate readiness and stopper reassessment planning (#184)`
- Agent-like scripts discovered: `49`
- Agent-like source files discovered: `8`
- Agent-like tests discovered: `52`
- Governance-relevant docs discovered: `155`
- Planning docs discovered: `17`

## Governance rule

No new product agent should be added without either:

1. registering it here, or
2. updating this registry in the same PR.

Every registered agent must have one primary responsibility. Mixed responsibilities require either an explicit decomposition plan or a documented exception.

## Canonical agent roles

| Role | Responsibility | Must not do |
|---|---|---|
| Router / planner | Order candidates, route to next safe action, produce commands/reports | Perform evidence repair or make gate decisions itself |
| Stop-audit / planner | Reassess stop validity and false-negative risk, propose Stage-2 plan | Silently unblock candidates or bypass safety stops |
| Repair / recovery | Run bounded recovery for URLs, detail evidence, or stale signals | Approve connector registration or source activation |
| Gate / approval | Evaluate/pass/fail a specific gate with evidence | Discover new sources or repair unrelated pipeline state |
| Connector build / validation | Generate/validate connector artifacts under gates | Activate sources without approval |
| Discovery / evidence | Gather bounded evidence from permitted sources/providers | Promote candidates without gates |
| Orchestrator / loop | Sequence known safe steps and surface attention items | Hide failures or override gate outcomes |
| Learning / analysis | Produce vocabulary, source value, capability, novelty, or false-negative insights | Mutate operational state unless explicitly gated |

## Provisional agent inventory

This table is provisional. It intentionally classifies by observed script names, CLI flags, and safety marker strings. GOV-001C should validate each entry against implementation behavior and runtime evidence.

| Script | Proposed role | Write posture | CLI flags | Safety markers | Capability audit priority |
|---|---|---|---|---|---|
| `scripts/run_connector_feasibility_probe_agent.py` | connector-build/validation | write-risk-needs-review | --company-key, --reviewed-by | source-activation, connector-registration, scheduler | high |
| `scripts/run_employer_origin_connector_build_readiness_agent.py` | connector-build/validation | write-risk-needs-review | --company-key | gate-write, source-activation | high |
| `scripts/run_employer_origin_connector_candidate_agent.py` | connector-build/validation | write-risk-needs-review | --company-key, --reviewed-by | gate-write | high |
| `scripts/run_employer_origin_connector_generation_foundation_agent.py` | connector-build/validation | write-risk-needs-review | --company-key, --reviewed-by | gate-write, source-activation, scheduler | high |
| `scripts/run_employer_origin_connector_implementation_agent.py` | connector-build/validation | unknown | - | - | medium |
| `scripts/run_employer_origin_connector_registration_plan_agent.py` | connector-build/validation | write-risk-needs-review | --company-key, --reviewed-by | gate-write, source-activation, connector-registration | high |
| `scripts/run_employer_origin_connector_validation_agent.py` | connector-build/validation | dry-run-aware | --company-key, --dry-run, --reviewed-by | gate-write, source-activation, dry-run | medium |
| `scripts/run_aggregator_discovery_suppression_agent.py` | discovery/evidence | write-risk-needs-review | --reviewed-by | gate-write, source-activation, scheduler, read-only-claim | high |
| `scripts/run_candidate_expansion_from_market_observations_agent.py` | discovery/evidence | write-risk-needs-review | --reviewed-by | gate-write, source-activation, connector-registration, scheduler | high |
| `scripts/run_employer_origin_autonomous_relevance_discovery_agent.py` | discovery/evidence | unknown | - | - | medium |
| `scripts/run_employer_origin_relevance_evidence_probe_agent.py` | discovery/evidence | write-risk-needs-review | --company-key, --reviewed-by, --target-location | gate-write, connector-registration, scheduler | high |
| `scripts/run_origin_job_structure_observation_agent.py` | discovery/evidence | write-risk-needs-review | --company-key, --reviewed-by | gate-write, scheduler | high |
| `scripts/run_origin_observation_pattern_promotion_agent.py` | discovery/evidence | dry-run-aware | --dry-run, --reviewed-by | gate-write, dry-run | medium |
| `scripts/run_origin_observation_seed_pool_agent.py` | discovery/evidence | dry-run-aware | --dry-run, --reviewed-by | dry-run | medium |
| `scripts/run_origin_source_discovery_agent.py` | discovery/evidence | write-risk-needs-review | --company-key, --reviewed-by, --target-location | source-activation, connector-registration, scheduler, read-only-claim | high |
| `scripts/record_employer_origin_gate_review.py` | gate/approval | write-risk-needs-review | --company-key, --reviewed-by | gate-write, source-activation | high |
| `scripts/review_finanz_informatik_activation_gate.py` | gate/approval | write-risk-needs-review | - | gate-write, connector-registration | high |
| `scripts/run_approval_gated_connector_build_agent.py` | gate/approval | write-risk-needs-review | --company-key, --reviewed-by | gate-write, source-activation, connector-registration, scheduler | high |
| `scripts/run_cand001_validated_origin_url_persistence_gate.py` | gate/approval | apply-gated | --apply, --benchmark-label, --company-key, --reviewed-by, --target-location | gate-write, source-activation, scheduler, dry-run, apply | high |
| `scripts/run_candidate_promotion_gate_agent.py` | gate/approval | write-risk-needs-review | --company-key, --reviewed-by | gate-write, source-activation, connector-registration, scheduler | high |
| `scripts/run_employer_origin_final_approval_gate_agent.py` | gate/approval | dry-run-aware | --company-key, --dry-run | gate-write, source-activation, connector-registration, dry-run | medium |
| `scripts/run_employer_origin_gate_agent.py` | gate/approval | write-risk-needs-review | --company-key, --reviewed-by, --target-location | gate-write, read-only-claim | high |
| `scripts/run_gate001_initial_gate_review.py` | gate/approval | apply-gated | --apply, --benchmark-label, --company-key, --reviewed-by | gate-write, dry-run, apply | high |
| `scripts/run_origin_source_discovery_gate_agent.py` | gate/approval | dry-run-aware | --company-key, --reviewed-by | gate-write, source-activation, connector-registration, scheduler, dry-run | medium |
| `scripts/run_candidate_profile_agent.py` | helper/uncategorized | write-risk-needs-review | --reviewed-by | source-activation, scheduler | triage |
| `scripts/run_controlled_trial_search_term_agent.py` | helper/uncategorized | write-risk-needs-review | --reviewed-by | source-activation, scheduler | triage |
| `scripts/run_employer_origin_agent_chain.py` | helper/uncategorized | dry-run-aware | --attempt-repair, --company-key, --dry-run, --reviewed-by, --target-location | gate-write, source-activation, connector-registration, dry-run | triage |
| `scripts/run_employer_origin_detail_uniqueness_agent.py` | helper/uncategorized | write-risk-needs-review | --company-key, --reviewed-by, --target-location | gate-write | triage |
| `scripts/run_capability_gap_agent.py` | learning/analysis | write-risk-needs-review | --reviewed-by | source-activation, scheduler | high |
| `scripts/run_company_vocabulary_agent.py` | learning/analysis | write-risk-needs-review | --reviewed-by | source-activation, scheduler | high |
| `scripts/run_false_negative_intelligence_agent.py` | learning/analysis | unknown | --reviewed-by | - | medium |
| `scripts/run_search_strategy_recommendation_agent.py` | learning/analysis | unknown | --reviewed-by | - | medium |
| `scripts/run_search_term_learning_agent.py` | learning/analysis | write-risk-needs-review | --reviewed-by | connector-registration, scheduler | high |
| `scripts/run_search_term_value_agent.py` | learning/analysis | write-risk-needs-review | --reviewed-by | source-activation, scheduler | high |
| `scripts/run_aggregator_novelty_loop_agent.py` | orchestrator/loop | write-risk-needs-review | --reviewed-by | source-activation, connector-registration, scheduler | high |
| `scripts/run_employer_origin_source_lifecycle_tracking_agent.py` | orchestrator/loop | dry-run-aware | --company-key, --dry-run, --reviewed-by | gate-write, dry-run | medium |
| `scripts/run_nightly_search_intelligence_orchestrator.py` | orchestrator/loop | write-risk-needs-review | --reviewed-by | gate-write, source-activation, connector-registration, scheduler | high |
| `scripts/run_search_intelligence_learning_loop_agent.py` | orchestrator/loop | unknown | --reviewed-by | - | medium |
| `scripts/run_stepstone_company_discovery_cycle_agent.py` | orchestrator/loop | apply-gated | --apply, --reviewed-by | source-activation, scheduler, read-only-claim, dry-run, apply | high |
| `scripts/run_employer_origin_detail_evidence_repair_agent.py` | repair/recovery | dry-run-aware | --company-key, --dry-run, --reviewed-by, --target-location | gate-write, dry-run | high |
| `scripts/run_employer_origin_source_url_recovery_agent.py` | repair/recovery | apply-gated | --apply, --company-key, --reviewed-by, --target-location | gate-write, connector-registration, scheduler, dry-run, apply | high |
| `scripts/run_origin_url_repair_application_agent.py` | repair/recovery | apply-gated | --company-key, --reviewed-by | connector-registration, scheduler, apply | high |
| `scripts/preview_connector_build_candidate_queue.py` | router/planner | write-risk-needs-review | - | connector-registration, scheduler, read-only-claim | high |
| `scripts/run_employer_origin_candidate_queue_agent.py` | router/planner | apply-gated | --attempt-repair, --benchmark-label, --company-key, --print-next-command, --print-stage2-command, --reviewed-by, --target-location, --write-report | gate-write, source-activation, scheduler, read-only-claim, apply | high |
| `retired next-action steering agent` | retired/historical | not-active | none | none | retired |
| `scripts/run_employer_origin_registration_execution_plan_agent.py` | router/planner | write-risk-needs-review | --company-key, --reviewed-by | gate-write, source-activation, connector-registration, scheduler | high |
| `scripts/run_eo002e_gate_stop_next_safe_action_analysis.py` | router/planner | write-risk-needs-review | --benchmark-label, --company-key | gate-write, read-only-claim | high |
| `scripts/run_employer_origin_gate_stop_audit.py` | stop-audit/planner | write-risk-needs-review | - | gate-write | high |
| `scripts/run_pipeline_stop_reassessment_agent.py` | stop-audit/planner | explicit-write-gated | --allow-write-actions, --apply, --attempt-repair, --benchmark-label, --company-key, --dry-run, --execute-stage2, --print-stage2-command, --reviewed-by, --target-location, --write-report | gate-write, source-activation, scheduler, read-only-claim, dry-run, apply, allow-write-actions | high |

## Immediate governance findings

- The project has enough agent-like scripts that informal naming is no longer sufficient governance.
- Several scripts mention gate writes, source activation, connector registration, or scheduler state without an obviously uniform command contract.
- The queue and stopper reassessment agents should be treated as governance-critical routing/audit agents, not ordinary helper scripts.
- The documentation surface is already large enough that DOC-001 must follow GOV-001; otherwise new readers will infer conflicting architectures.

## Required follow-up

- GOV-001C: classify real product agents vs historical helpers/stubs.
- GOV-001D: enforce the role/write-posture contract in docs and ideally with a lightweight checker.
- DOC-001A: documentation drift audit based on the finalized registry.
