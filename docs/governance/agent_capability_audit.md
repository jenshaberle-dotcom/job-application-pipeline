# GOV-001B Agent Capability Audit Foundation

Status: foundation draft. This document defines how each agent will be audited before further broad pipeline expansion.

## Purpose

The capability audit answers one question for every pipeline agent:

> Can this agent actually handle the expected content, edge cases, stops, false-negative risks, and operational difficulties of its responsibility?

An agent is not considered mature only because it has tests. It must also have a clear responsibility, known inputs/outputs, explicit failure modes, routing rules, and runtime evidence.

## Audit dimensions

| Dimension | Question | Evidence expected |
|---|---|---|
| Responsibility fit | Does the agent do one coherent job? | Registry entry and role mapping |
| Input coverage | Can it handle expected input variants? | Tests, fixtures, runtime reports |
| Edge-case coverage | Does it handle missing URLs, wrong domains, stale stops, no target signal, provider noise, duplicates? | Tests and documented examples |
| False-negative risk | Could it wrongly stop or ignore a relevant candidate? | Stop taxonomy, risk classification, reassessment route |
| False-positive risk | Could it promote weak evidence or wrong employers? | Gate strictness tests and evidence reports |
| Safety boundary | Are writes gated by dry-run/apply/allow-write-actions and review metadata? | CLI contract and implementation check |
| Repair/routing | Does it know when to repair, route, stop, or ask for operator review? | Next-action contract and report examples |
| Observability | Does it write a clear report or runtime record? | JSON/Markdown export or DB audit event |
| Test/runtime proof | Do tests and at least one runtime smoke prove the contract? | Test names and report paths |

## Capability levels

| Level | Meaning | Allowed use |
|---|---|---|
| L0 Unknown | Script exists, responsibility unclear | Do not expand; triage first |
| L1 Documented | Responsibility documented, limited proof | Read-only use or guarded experiments |
| L2 Tested | Unit tests cover normal and some edge cases | Controlled dry-run / report generation |
| L3 Runtime validated | Runtime smoke proves contract on real project state | Controlled operator-approved apply where applicable |
| L4 Operational | Observed over repeated runs with stable reports and failure handling | Eligible for scheduler/orchestrator integration |

## Initial capability audit backlog

The following are the first governance-critical audits. They are prioritized because they can directly affect false negatives, source activation, connector registration, or operator trust.

| Agent/script | Capability question | Why priority |
|---|---|---|
| `scripts/run_pipeline_stop_reassessment_agent.py` | Can it classify all expected stop classes, not only access-risk examples like Ratiodata? | STOP-002 taxonomy required |
| `scripts/run_employer_origin_candidate_queue_agent.py` | Does it route candidates without becoming a mixed queue/repair/gate agent? | Must remain router/planner |
| `scripts/run_employer_origin_detail_evidence_repair_agent.py` | Can it handle noisy detail links, target-location ambiguity, employer/domain mismatch, and stale rejected URLs? | Large/high-risk repair surface |
| `scripts/run_origin_source_discovery_agent.py` | Can it handle company-name-only, aliases, wrong hosts, search-provider gaps, and budget boundaries? | High false-negative impact |
| `scripts/run_employer_origin_agent_chain.py` | Does it orchestrate safely without hiding gate failures or over-coupling stages? | Chain-level risk |
| `scripts/run_approval_gated_connector_build_agent.py` | Does it enforce approval gates before build/registration/activation transitions? | Connector lifecycle risk |
| `scripts/run_nightly_search_intelligence_orchestrator.py` | Does it sequence safely and surface attention instead of silently progressing? | Scheduler/orchestration risk |
| `scripts/run_stepstone_company_discovery_cycle_agent.py` | Does suppression create real discovery novelty without hiding learning signals? | Search-intelligence false-negative risk |

## Stopper-specific capability requirement

The stop reassessment path must eventually distinguish at least these stop classes:

| Stop class | Example meaning | Default next action |
|---|---|---|
| `access-risk-over-sensitive` | Bot/recaptcha/consent marker found but job content may still be public | Stopper audit -> bounded detail repair dry-run |
| `missing-source-url` | Candidate has no URL or generated URLs failed | URL recovery/discovery |
| `wrong-source-url` | Candidate URL points to wrong host/provider/context | Origin source discovery / manual URL review |
| `no-detail-pages` | List page reachable but no concrete jobs extracted | Detail-link discovery / detail repair |
| `no-target-signal` | Jobs exist but no target-location/remote signal | Keep stopped unless new evidence appears |
| `employer-domain-mismatch` | Evidence from foreign domain/employer | Gate review; usually no auto repair |
| `hard-legal-or-bot-stop` | Real challenge/legal/access barrier | No automatic repair; operator decision |
| `connector-validation-failure` | Connector artifact exists but fails validation | Connector validation repair plan |
| `approval-stop` | Human decision required | No auto-apply |

## Output required per audited agent

Each capability audit should produce:

- registry classification
- capability level
- expected input classes
- known failure modes
- repair/routing behavior
- write/safety boundary
- tests proving the contract
- runtime smoke evidence where available
- capability gaps and follow-up work
