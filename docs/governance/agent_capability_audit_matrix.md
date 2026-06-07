# GOV-001D Agent Capability Audit Matrix

Status: current governance foundation  
Scope: documentation and governance only  
Created from: GOV-001A static inventory intake, GOV-001B registry foundation, GOV-001C classification catalog  
Boundary: no pipeline logic, no DB migration, no runtime execution

## Purpose

This document turns the agent inventory and classification work into an explicit capability audit.

It answers the question:

> Can each pipeline agent actually handle the content, edge cases, stops, false-negative risks, and operational difficulty implied by its name and responsibility?

This is not a runtime health report. It is a governance-level capability map.

## Audit Levels

| Level | Meaning | Governance consequence |
|---|---|---|
| `validated_for_current_scope` | Tests and runtime evidence cover the current responsibility well enough. | May remain product-facing for that scope. |
| `partially_validated` | Some responsibility is covered, but important edge cases or runtime paths are missing. | May operate with stated limits; needs targeted follow-up before expansion. |
| `needs_capability_audit` | Name or placement suggests broader competence than the evidence proves. | Must not be expanded before audit. |
| `consolidation_candidate` | Responsibility overlaps strongly with another agent or orchestration layer. | Should be merged, renamed, or narrowed before further use. |
| `stub_or_placeholder` | File exists but does not contain product-grade behavior. | Must not be treated as a product agent. |
| `historical_or_legacy` | Useful for context/history, but not current product control flow. | Archive/deprecate or keep out of current system diagrams. |
| `governance_risk` | Agent can write or trigger sensitive transitions without a sufficiently explicit safety model. | Requires hardening, dry-run/apply boundary, or operator gate before expansion. |

## Capability Dimensions

Each agent should be audited against the following dimensions.

| Dimension | Question |
|---|---|
| Responsibility fit | Does the agent do one clear job? |
| Input coverage | Can it handle all expected input states for its stage? |
| Edge-case coverage | Are common hard cases tested or explicitly stopped? |
| False-negative risk handling | Can it detect when its own logic may be too strict or stale? |
| Repair/next-action ability | Does it route to a safe next step instead of dead-ending? |
| Write boundary | Are writes read-only/dry-run/apply/approval-gated correctly? |
| Evidence basis | Are decisions tied to concrete DB/runtime/test evidence? |
| Routing boundary | Does it route to the right downstream agent without taking over that agent's job? |
| Operator review boundary | Does it know when human review is required? |
| Documentation fit | Does documentation describe the current behavior rather than historical intent? |

## Priority Audit Matrix

This matrix intentionally focuses on product-relevant agents first. Helper scripts, historical spikes, and stubs are covered in grouped sections below.

| Agent / artifact | Governance role | Current capability assessment | Known coverage | Known gaps / risks | Required follow-up |
|---|---|---|---|---|---|
| `scripts/run_employer_origin_candidate_queue_agent.py` | Router / portfolio planner | `partially_validated` | Routes active-controlled, blocked, and repair candidates; exports read-only queue reports; now routes blocked boundaries to Stopper Reassessment. | Large script; may still mix queue, reporting, command generation, and review boundary semantics; must not become a repair agent. | Add explicit registry row; ensure all blocked/manual-review classes route to stopper/gate-specific handlers. |
| `scripts/run_pipeline_stop_reassessment_agent.py` | Stop-audit / repair planner | `partially_validated` | Validated for Ratiodata-style over-sensitive access-risk stop; creates Stage-2 dry-run/apply repair plans without default execution. | Not yet a full stop taxonomy; missing strategy registry for all expected stop classes. | STOP-002 Stop Taxonomy & Repair Strategy Registry. |
| `scripts/run_employer_origin_detail_evidence_repair_agent.py` | Repair / evidence recovery | `partially_validated` | Strong detail-evidence test coverage; recent DETAIL blocks improved bounded discovery, host prioritization, rejected URL isolation, and evidence strictness. | Very large file; may contain multiple responsibilities; must not approve its own results. | Split audit by discovery, extraction, assessment, report contract, and write behavior. |
| `scripts/run_employer_origin_agent_chain.py` | Chain orchestrator | `needs_capability_audit` | Can run chain commands and attempt repair; has tests. | Risk of mixing orchestration with repair and gate behavior; needs explicit stage boundaries. | Define allowed chain transitions and which agents own each transition. |
| `scripts/run_employer_origin_gate_agent.py` | Gate evaluator | `needs_capability_audit` | Has gate-related tests and read-only markers. | Gate agent must not discover evidence; if it writes reviews/events, write boundary must be explicit. | Audit reads/writes and align with gate contract baseline. |
| `scripts/run_gate001_initial_gate_review.py` | Initial gate review | `partially_validated` | Has dry-run/apply contract and tests. | Needs placement in current gate sequence; avoid overlapping with generic gate agent. | Register as specific gate agent or consolidate under gate framework. |
| `scripts/run_cand001_validated_origin_url_persistence_gate.py` | Candidate URL persistence gate | `partially_validated` | Has `--apply`, benchmark label, target-location args, and tests. | Sensitive write path; must remain explicit apply-only. | Capability audit for URL validity, source identity, and write boundary. |
| `scripts/run_employer_origin_source_url_recovery_agent.py` | URL recovery | `partially_validated` | Has apply-aware URL recovery flow. | Needs stronger taxonomy for missing/wrong/stale URLs; must avoid guessing and avoid storing weak URLs. | Link to STOP-002 strategies for `missing_source_url` and `wrong_source_url`. |
| `scripts/run_origin_source_discovery_agent.py` / `src/search_intelligence/origin_source_discovery_agent.py` | Origin discovery | `needs_capability_audit` | Large source agent exists with provider safety tests. | Must prove ability to handle aliases, provider failures, weak search results, false positives, and manual-review stops. | Capability audit before broader candidate expansion. |
| `scripts/run_origin_source_discovery_gate_agent.py` | Origin discovery gate | `needs_capability_audit` | Has tests and dry-run markers. | Gate/discovery boundary must stay clear; gate should judge evidence, not search. | Register as gate evaluator; audit write behavior. |
| `scripts/run_origin_url_repair_application_agent.py` | URL repair application | `governance_risk` | Existing script suggests apply behavior. | Potentially sensitive candidate URL changes; dry-run/apply semantics need explicit review. | Review before any expanded use; possibly route through CAND-001 gate. |
| `scripts/run_employer_origin_relevance_evidence_probe_agent.py` | Relevance evidence probe | `needs_capability_audit` | Produces relevance evidence for candidates. | Must distinguish absence of evidence from evidence of absence; high false-negative risk. | Add capability cases for no target signal, remote/Germany-wide evidence, and irrelevant hits. |
| `scripts/run_employer_origin_connector_candidate_agent.py` | Connector candidacy assessment | `needs_capability_audit` | Has tests and candidate workflow. | Must not build, register, or activate; must only judge candidacy. | Register exact input/output contract. |
| `scripts/run_employer_origin_connector_generation_foundation_agent.py` | Connector generation planning | `needs_capability_audit` | Existing foundation agent and docs. | Needs distinction between generated artifacts, review candidate, registration plan, and activation. | Align with connector build process and approval gates. |
| `scripts/run_approval_gated_connector_build_agent.py` | Approval-gated build | `governance_risk` | Tests and source implementation exist. | Build artifacts are sensitive; must preserve approval boundary and avoid uncontrolled activation. | Audit before allowing more auto-build behavior. |
| `scripts/run_employer_origin_connector_validation_agent.py` | Connector validation | `partially_validated` | Has dry-run flag and tests. | Must not self-approve; must handle parser failures and false-positive validation. | Register validation evidence contract. |
| `scripts/run_employer_origin_final_approval_gate_agent.py` | Final approval gate | `partially_validated` | Has dry-run and tests. | Human approval semantics must be explicit; no automatic approval through upstream success. | Align with RASIC/operator review model. |
| `scripts/run_employer_origin_registration_execution_plan_agent.py` | Registration execution planning | `governance_risk` | Existing plan agent and tests. | Registration/activation boundary is sensitive; must not silently execute. | Require explicit operator-approved plan and dry-run/apply model. |
| `scripts/run_employer_origin_source_lifecycle_tracking_agent.py` | Lifecycle tracking | `partially_validated` | Has dry-run and tests. | Lifecycle state must not be used to hide stale gate failures. | Add evidence contract for active-controlled lifecycle monitoring. |
| `scripts/run_nightly_search_intelligence_orchestrator.py` / `src/search_intelligence/nightly_orchestrator.py` | Orchestrator / loop | `needs_capability_audit` | Orchestrator tables/tests exist. | Needs clear limits: schedule, attention steps, no hidden activation, no unbounded loops. | Full orchestrator capability audit before scheduler changes. |
| `scripts/run_stepstone_company_discovery_cycle_agent.py` | Aggregator discovery loop | `partially_validated` | Has dry-run/apply and discovery-cycle tests; important for company novelty. | Needs metrics proving feed-forward suppression/novelty loop works over cycles. | Sensor contribution/blind-spot audit and Wave/Cycle governance follow-up. |
| `scripts/run_aggregator_discovery_suppression_agent.py` | Aggregator suppression helper/agent | `consolidation_candidate` | Related to StepStone suppression. | Overlaps with discovery cycle; may confuse current control flow. | Decide whether to consolidate under StepStone cycle agent. |
| `scripts/run_aggregator_novelty_loop_agent.py` | Aggregator novelty loop | `consolidation_candidate` | Existing loop script. | Potential overlap with StepStone cycle and market sensor metrics. | Clarify whether it is current product agent or historical foundation. |
| `scripts/run_candidate_expansion_from_market_observations_agent.py` | Candidate expansion | `governance_risk` | Promotes market observations to candidates. | Expansion creates downstream work and false positives; must be governed by promotion quality loop. | Audit before expanding sensors or candidates. |
| `scripts/run_candidate_promotion_gate_agent.py` | Candidate promotion gate | `needs_capability_audit` | Has tests. | Gate strictness may create false negatives; Türsteher quality remains a known risk. | Link to EO-003 promotion quality loop. |
| `scripts/run_false_negative_intelligence_agent.py` | False-negative analysis | `needs_capability_audit` | Existing script. | Must be separated from stopper reassessment and promotion logic. | Define relation to STOP-001 and future recall metrics. |
| `scripts/run_capability_gap_agent.py` | Capability gap analysis | `needs_capability_audit` | Existing script. | Name overlaps with this governance audit; unclear current role. | Decide whether current agent remains product agent or historical helper. |
| `scripts/run_company_vocabulary_agent.py` | Learning / vocabulary | `partially_validated` | Produces company vocabulary signals. | Must not directly promote candidates without gate. | Keep as learning/support agent. |
| `scripts/run_search_term_learning_agent.py` | Learning / search terms | `partially_validated` | Existing search-term learning foundation. | Must remain learning input, not gate decision. | Register as support agent. |
| `scripts/run_search_term_value_agent.py` | Learning / search-term value | `partially_validated` | Existing value agent. | Needs lifecycle quality metrics over time. | Keep support role. |
| `scripts/run_search_intelligence_learning_loop_agent.py` | Learning loop | `needs_capability_audit` | Existing script. | Overlap with several learning agents; unclear current product role. | Consolidation review. |
| `scripts/run_search_strategy_recommendation_agent.py` | Strategy recommendation | `needs_capability_audit` | Existing script. | Recommendations must not mutate pipeline. | Register as read-only support or archive. |
| `scripts/run_controlled_trial_search_term_agent.py` | Trial search terms | `needs_capability_audit` | Existing script. | Could affect source/scheduler behavior; needs boundary. | Decide current relevance. |
| `scripts/run_origin_job_structure_observation_agent.py` | Observation learning | `needs_capability_audit` | Large observation script. | Must implement bounded dynamic observation and seed dedup rules before expansion. | Capability audit before observation-loop expansion. |
| `scripts/run_origin_observation_seed_pool_agent.py` | Observation seed pool | `partially_validated` | Has dry-run. | Must not create DB clutter or repeat known seeds. | Link to dynamic observation governance. |
| `scripts/run_origin_observation_pattern_promotion_agent.py` | Pattern promotion | `governance_risk` | Has dry-run. | Promotion from observations can create downstream false positives. | Needs explicit promotion gate contract. |

## Stubs and Placeholder-Like Artifacts

These artifacts must not be described in current system diagrams as product-grade agents until promoted or removed.

| Artifact | Current classification | Reason |
|---|---|---|
| `scripts/run_employer_origin_autonomous_relevance_discovery_agent.py` | `stub_or_placeholder` | Very small file in intake; likely not product-grade. |
| `scripts/run_employer_origin_connector_implementation_agent.py` | `stub_or_placeholder` | Very small file in intake; implementation agent name overstates capability. |

## Immediate Capability Gaps

| Gap | Why it matters | Proposed follow-up |
|---|---|---|
| Stop taxonomy incomplete | STOP-001 handles Ratiodata-style over-sensitive stops but not all expected stop classes. | STOP-002 Stop Taxonomy & Repair Strategy Registry. |
| Agent write boundaries inconsistent | Several agents mention gate/source/connector writes but not all expose dry-run/apply/allow-write-actions. | GOV-001E Write Boundary Review. |
| Router/orchestrator responsibility overlap | Queue, Next-Safe-Action, Agent Chain, and Nightly Orchestrator can overlap. | GOV-001E Routing/Orchestration Consolidation Review. |
| Connector chain split across many agents | Build readiness, candidate, generation, validation, approval, registration planning, and execution planning are fragmented. | GOV-001F Connector Chain Responsibility Contract. |
| Historical docs may overstate current behavior | Many source-analysis docs look like build notes rather than current truth. | DOC-001 Documentation Rebaseline after GOV-00X. |
| Stubs can be mistaken for product agents | File names imply capability that is not implemented. | Mark as stub or remove from current diagrams. |
| Learning agents can accidentally become gate inputs | Vocabulary/search-term/observation outputs must remain learning signals unless gated. | Register learning-output boundary. |

## Minimum Acceptance for a Product Agent

An artifact may be described as a current product agent only if it has:

1. a single named responsibility,
2. explicit input and output contract,
3. explicit read/write boundary,
4. dry-run/apply or read-only guarantees where relevant,
5. tests for happy path and major stop/edge cases,
6. runtime smoke evidence for at least one realistic candidate/source,
7. documented routing to downstream agents,
8. documented operator-review boundary,
9. classification in the governance catalog,
10. known gaps listed if not fully capable.

## Decision

GOV-001D does not declare the agent estate finished.

It freezes the audit baseline:

> The project now has enough agent-like artifacts that each product-facing agent must be capability-audited before broad expansion. Names are not evidence. Tests, runtime reports, safety boundaries, and responsibility fit are evidence.
