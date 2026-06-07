# GOV-001C Agent Classification Catalog

Status: initial governance catalog
Scope: documentation and governance only
Created from: GOV-001A static inventory intake and GOV-001B governance foundation

## Purpose

The project now contains many scripts and modules whose names look like agents,
gates, queues, orchestrators, audits, repairs, or lifecycle controllers. The
GOV-001A intake found a large enough surface that informal naming is no longer
safe.

This catalog classifies agent-like artifacts into governance-relevant groups so
that later work can decide whether an artifact is a product agent, a helper, a
legacy spike, a stub, or a consolidation candidate.

This is not a runtime registry yet. It is a first governance baseline that must
be refined through code inspection, tests, and runtime evidence.

## Classification states

| State | Meaning | Default governance treatment |
| --- | --- | --- |
| `product_core_agent` | Current product-level agent with an active responsibility in the pipeline. | Must have responsibility, input/output contract, safety boundary, tests, and runtime evidence. |
| `product_support_agent` | Supports a product capability but is not the primary owner of a pipeline decision. | Must document which product agent or stage it supports. |
| `operator_helper` | Manual or diagnostic helper script, not a product agent. | Must not be presented as an autonomous pipeline agent. |
| `historical_spike_or_legacy` | Historical experiment, old foundation script, or superseded implementation. | Must be archived, renamed, or marked as historical before DOC-001. |
| `stub_or_placeholder` | Minimal placeholder that looks like an agent but cannot fulfill the implied responsibility. | Must be renamed, implemented, or removed from active documentation. |
| `consolidation_candidate` | Overlaps with another agent or represents fragmented responsibility. | Must be reviewed before further expansion. |
| `needs_capability_audit` | Static inventory cannot prove whether the agent can handle its promised responsibility. | Must enter the agent capability audit matrix. |

An artifact can carry more than one flag. For example, an agent can be a
`product_core_agent` and still be `needs_capability_audit`.

## Decision rules

### Product core agent

Classify as `product_core_agent` only when the artifact has an ongoing pipeline
responsibility such as:

- routing next safe actions,
- auditing or validating stop conditions,
- repairing evidence or URLs,
- evaluating gates,
- creating or validating connector build decisions,
- controlling lifecycle transitions,
- orchestrating scheduled intelligence cycles.

The agent must not merely be a one-off experiment or static report.

### Product support agent

Classify as `product_support_agent` when the artifact produces useful product
signals but is not the authoritative owner of a pipeline decision. Typical
examples are observation, learning, search-term analysis, or source-value
signals.

### Operator helper

Classify as `operator_helper` when a script previews, records, inspects, or
manually assists a decision but does not own a product responsibility.

Operator helpers are allowed, but they should not inflate the agent count.

### Historical spike or legacy

Classify as `historical_spike_or_legacy` when the artifact documents or
implements an earlier approach that has been superseded by current agents,
gates, or governance rules.

These artifacts should remain accessible when historically useful, but DOC-001
must make clear that they are not the current operating model.

### Stub or placeholder

Classify as `stub_or_placeholder` when an artifact has an agent-like name but is
too small or too incomplete to fulfill the implied product responsibility.

Stub-like agent names are dangerous because they create false confidence in the
pipeline. They should be renamed, removed, or implemented behind a real
contract.

### Consolidation candidate

Classify as `consolidation_candidate` when two or more artifacts appear to own
overlapping responsibilities, for example:

- next-safe-action routing vs. candidate queue routing,
- gate stop audit vs. pipeline stop reassessment,
- connector candidate vs. connector build readiness vs. connector generation,
- source URL recovery vs. origin URL repair application.

Consolidation does not automatically mean deletion. It means the responsibility
must be explicitly assigned and duplicate decision logic must be avoided.

## Initial classification from GOV-001A

The following classification is intentionally conservative. It is based on
static inventory signals such as file names, CLI flags, safety markers, line
counts, and test presence. It is not yet a complete code-level audit.

### Current product core agents

| Artifact | Proposed role | Classification | Capability audit focus |
| --- | --- | --- | --- |
| `scripts/run_employer_origin_candidate_queue_agent.py` | EO candidate queue and next-safe-action router | `product_core_agent`, `consolidation_candidate`, `needs_capability_audit` | Ensure it only routes/prioritizes and does not become a mixed repair/gate agent. Validate blocked candidates route to Stopper Reassessment. |
| `scripts/run_pipeline_stop_reassessment_agent.py` | Stop validity audit and Stage-2 repair planner | `product_core_agent`, `needs_capability_audit` | Expand from access-risk/stale-stop handling toward full stop taxonomy. Confirm it never auto-unblocks by default. |
| `scripts/run_employer_origin_detail_evidence_repair_agent.py` | Bounded detail evidence repair | `product_core_agent`, `needs_capability_audit` | Verify it handles detail-link discovery, rejected URL contamination, provider candidates, location/employer strictness, and dry-run/apply boundaries. |
| `scripts/run_employer_origin_source_url_recovery_agent.py` | Candidate source URL recovery | `product_core_agent`, `needs_capability_audit` | Confirm missing/wrong URL recovery, apply safety, search-provider constraints, and no unsafe source activation. |
| `scripts/run_origin_source_discovery_agent.py` | Origin source discovery | `product_core_agent`, `needs_capability_audit` | Confirm discovery quality, provider handling, alias/domain ranking, budget behavior, and manual-review stops. |
| `scripts/run_origin_source_discovery_gate_agent.py` | Origin source discovery gate | `product_core_agent`, `needs_capability_audit` | Confirm gate ownership and boundary between discovery evidence and gate decisions. |
| `scripts/run_gate001_initial_gate_review.py` | Initial gate review | `product_core_agent`, `needs_capability_audit` | Confirm dry-run/apply behavior and current gate vocabulary alignment. |
| `scripts/run_cand001_validated_origin_url_persistence_gate.py` | Validated URL persistence gate | `product_core_agent`, `needs_capability_audit` | Confirm validated URL writes require explicit apply and do not persist stale/unsafe URLs. |
| `scripts/run_employer_origin_gate_agent.py` | Employer-origin gate evaluator | `product_core_agent`, `consolidation_candidate`, `needs_capability_audit` | Clarify overlap with specific gate agents and gate registry. |
| `scripts/run_employer_origin_agent_chain.py` | Employer-origin chain orchestrator | `product_core_agent`, `consolidation_candidate`, `needs_capability_audit` | Clarify whether it orchestrates only, repairs, or writes gate decisions. |
| `scripts/run_employer_origin_source_lifecycle_tracking_agent.py` | Source lifecycle tracking | `product_core_agent`, `needs_capability_audit` | Confirm lifecycle status semantics and active-controlled monitoring boundaries. |
| `scripts/run_employer_origin_connector_validation_agent.py` | Connector validation gate | `product_core_agent`, `needs_capability_audit` | Confirm validation evidence, failure modes, dry-run behavior, and no registration side effects. |
| `scripts/run_employer_origin_final_approval_gate_agent.py` | Final approval gate | `product_core_agent`, `needs_capability_audit` | Confirm approval remains human/explicit and cannot be bypassed by generated artifacts. |
| `scripts/run_approval_gated_connector_build_agent.py` | Approval-gated connector build planner | `product_core_agent`, `consolidation_candidate`, `needs_capability_audit` | Clarify boundary between build planning, artifact generation, validation, and registration. |
| `scripts/run_nightly_search_intelligence_orchestrator.py` | Nightly search-intelligence orchestrator | `product_core_agent`, `needs_capability_audit` | Confirm scheduler/runtime behavior, attention steps, idempotency, and stop/reporting semantics. |

### Product support agents

| Artifact | Proposed role | Classification | Capability audit focus |
| --- | --- | --- | --- |
| `scripts/run_stepstone_company_discovery_cycle_agent.py` | StepStone company discovery cycle | `product_support_agent`, `needs_capability_audit` | Validate temporary known-company suppression, cyclic term behavior, and no pagination/limit circumvention. |
| `scripts/run_aggregator_discovery_suppression_agent.py` | Aggregator suppression diagnostics/control | `product_support_agent`, `consolidation_candidate` | Clarify relationship to StepStone company discovery cycle. |
| `scripts/run_aggregator_novelty_loop_agent.py` | Aggregator novelty loop | `product_support_agent`, `consolidation_candidate`, `needs_capability_audit` | Clarify whether this is still current or superseded by StepStone cycle work. |
| `scripts/run_origin_job_structure_observation_agent.py` | Origin job structure observation | `product_support_agent`, `needs_capability_audit` | Validate adaptive observation, seed deduplication, and learning-only boundary. |
| `scripts/run_origin_observation_seed_pool_agent.py` | Observation seed pool | `product_support_agent`, `needs_capability_audit` | Confirm seed source priority and no export-as-input regressions. |
| `scripts/run_origin_observation_pattern_promotion_agent.py` | Observation pattern promotion | `product_support_agent`, `needs_capability_audit` | Confirm promotion output remains learning input, not direct evidence or gate pass. |
| `scripts/run_false_negative_intelligence_agent.py` | False-negative intelligence signals | `product_support_agent`, `needs_capability_audit` | Clarify relationship to STOP-001 and future STOP-002 taxonomy. |
| `scripts/run_capability_gap_agent.py` | Capability gap analysis | `product_support_agent`, `needs_capability_audit` | Align with GOV-001 capability audit terminology. |
| `scripts/run_search_term_learning_agent.py` | Search-term learning | `product_support_agent`, `needs_capability_audit` | Confirm learning loop boundaries and false-negative term discovery. |
| `scripts/run_search_term_value_agent.py` | Search-term value evaluation | `product_support_agent`, `needs_capability_audit` | Confirm value metrics and source/search-term lifecycle semantics. |
| `scripts/run_search_strategy_recommendation_agent.py` | Search strategy recommendation | `product_support_agent`, `needs_capability_audit` | Clarify whether recommendations feed scheduler, profiles, or manual review. |
| `scripts/run_search_intelligence_learning_loop_agent.py` | Search-intelligence learning loop | `product_support_agent`, `consolidation_candidate`, `needs_capability_audit` | Clarify overlap with search-term learning and nightly orchestrator. |
| `scripts/run_company_vocabulary_agent.py` | Company vocabulary learning | `product_support_agent`, `needs_capability_audit` | Confirm alias/company-key correctness and role in discovery suppression. |
| `scripts/run_candidate_profile_agent.py` | Candidate profile signals | `product_support_agent`, `needs_capability_audit` | Clarify current usage and whether it remains active. |
| `scripts/run_controlled_trial_search_term_agent.py` | Controlled trial search terms | `product_support_agent`, `needs_capability_audit` | Confirm trial boundaries and no uncontrolled profile mutations. |

### Connector and registration chain candidates

The connector chain contains many specialized agents. They may be valid, but
the responsibility map is currently at risk of fragmentation. GOV-001 must
force a clear sequence and owner model.

| Artifact | Proposed role | Classification | Capability audit focus |
| --- | --- | --- | --- |
| `scripts/run_employer_origin_connector_candidate_agent.py` | Connector candidacy evaluation | `product_core_agent`, `consolidation_candidate`, `needs_capability_audit` | Clarify inputs and relationship to build readiness. |
| `scripts/run_employer_origin_connector_build_readiness_agent.py` | Build readiness decision | `product_core_agent`, `consolidation_candidate`, `needs_capability_audit` | Clarify whether readiness is separate from candidacy and approval-gated build. |
| `scripts/run_employer_origin_connector_generation_foundation_agent.py` | Connector generation planning | `product_core_agent`, `consolidation_candidate`, `needs_capability_audit` | Confirm whether it only plans or generates artifacts. |
| `scripts/run_employer_origin_connector_registration_plan_agent.py` | Registration planning | `product_core_agent`, `consolidation_candidate`, `needs_capability_audit` | Ensure no registration side effects before final approval. |
| `scripts/run_employer_origin_registration_execution_plan_agent.py` | Registration execution planning | `product_core_agent`, `consolidation_candidate`, `needs_capability_audit` | Clarify overlap with registration plan agent. |
| `scripts/run_employer_origin_connector_validation_agent.py` | Connector validation | `product_core_agent`, `needs_capability_audit` | Confirm validation failure handling and repair routing. |

### Operator helpers and manual utilities

| Artifact | Proposed role | Classification | Governance action |
| --- | --- | --- | --- |
| `scripts/preview_connector_build_candidate_queue.py` | Queue preview | `operator_helper` | Keep as helper or replace with current EO queue report. |
| `scripts/record_employer_origin_gate_review.py` | Manual gate review recording | `operator_helper`, `needs_capability_audit` | Verify write safety and whether it should be superseded by gate agents. |
| `scripts/review_finanz_informatik_activation_gate.py` | Historical/manual FI activation review | `operator_helper`, `historical_spike_or_legacy` | Mark as historical if FI activation path is now represented by general lifecycle/approval agents. |
| `scripts/run_employer_origin_gate_stop_audit.py` | Gate stop audit helper | `operator_helper`, `consolidation_candidate` | Review overlap with STOP-001. |
| `scripts/run_eo002e_gate_stop_next_safe_action_analysis.py` | Gate stop next-safe-action analysis | `operator_helper`, `historical_spike_or_legacy`, `consolidation_candidate` | Decide whether superseded by STOP-001/queue report. |

### Stub or placeholder candidates

| Artifact | Classification | Why this matters | Required action |
| --- | --- | --- | --- |
| `scripts/run_employer_origin_autonomous_relevance_discovery_agent.py` | `stub_or_placeholder`, `needs_capability_audit` | Static intake shows a very small agent-like script. The name promises autonomous discovery. | Inspect and either implement, rename as spike/helper, or remove from active docs. |
| `scripts/run_employer_origin_connector_implementation_agent.py` | `stub_or_placeholder`, `needs_capability_audit` | Static intake shows a very small implementation-agent script. The name promises connector implementation. | Inspect and either implement, rename as placeholder, or remove from active docs. |

### High-priority consolidation candidates

These areas should be reviewed before adding more agents.

1. **Next-safe-action routing**
   - `run_employer_origin_candidate_queue_agent.py`
   - `run_employer_origin_next_safe_action_agent.py`
   - `run_eo002e_gate_stop_next_safe_action_analysis.py`

   Governance question: which artifact is the current authoritative router?

2. **Stop and gate-stop handling**
   - `run_pipeline_stop_reassessment_agent.py`
   - `run_employer_origin_gate_stop_audit.py`
   - `run_eo002e_gate_stop_next_safe_action_analysis.py`
   - `src/search_intelligence/gate_stop_classification.py`

   Governance question: which artifact classifies stops, which reassesses them,
   and which only reports historical gate-stop signals?

3. **Connector chain**
   - connector candidate,
   - build readiness,
   - generation foundation,
   - registration plan,
   - registration execution plan,
   - validation,
   - final approval.

   Governance question: what is the canonical order, and which agent owns each
   boundary?

4. **URL and origin discovery**
   - origin source discovery,
   - origin source discovery gate,
   - source URL recovery,
   - origin URL repair application,
   - validated origin URL persistence gate.

   Governance question: when do we discover, repair, validate, persist, and
   reject source URLs?

5. **Learning loops**
   - search-term learning,
   - search-term value,
   - strategy recommendation,
   - nightly orchestrator,
   - capability gap,
   - false-negative intelligence.

   Governance question: what is learning input, what is operational routing,
   and what is a product decision?

## Agent maturity levels

Use these maturity levels during the GOV-001 capability audit.

| Level | Name | Meaning |
| --- | --- | --- |
| L0 | Inventory only | Exists in repo; responsibility not yet validated. |
| L1 | Documented responsibility | Purpose and boundary are documented. |
| L2 | Unit-tested contract | Has tests for expected inputs and boundaries. |
| L3 | Runtime-smoked | Has recent runtime evidence on real project data. |
| L4 | Capability-audited | Known content types, edge cases, stop cases, and false-negative risks are documented. |
| L5 | Product-trusted | Safe to use as current authoritative owner for its responsibility. |

No agent should be presented as product-trusted unless it has reached at least
L4 and has a clear ownership boundary.

## Required follow-up before DOC-001

Before the full documentation rebaseline, GOV-001 must produce:

- a canonical list of current product agents,
- a list of helper scripts that should not be called agents,
- a list of historical/spike docs and scripts,
- a list of stubs/placeholders,
- a consolidation map for overlapping responsibilities,
- a capability audit backlog for all product core agents.

DOC-001 should then rewrite the public project documentation against that
registry instead of continuing to reconcile scattered historical docs.
