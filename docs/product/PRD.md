# Job Application Pipeline Product Requirements

Status: **draft product rebaseline — operator approval required**
Product owner and primary user: **Jens**
Project character: **A — Intent Locked**

## 1. Product objective

The repository currently supports the following product intent, pending explicit operator ratification as the PRD baseline:

- build a personal Search Intelligence system for Hannover and remote-in-Germany opportunities;
- reduce false negatives caused by noisy aggregators, weak search terms, missing origin evidence and overly safe stops;
- provide controlled market understanding rather than maximum job volume;
- expose evidence, uncertainty, blockers and next safe actions;
- preserve operator control over activation, mutation and application decisions.

These statements are current repository truth. They are not a substitute for the detailed decisions below.

## 2. Product authority contract

The operator decides product behavior.

DON may independently choose technical implementation within approved requirements. DON may propose product changes, but every proposal remains non-authoritative until explicitly approved.

A green technical test does not prove product correctness. Product correctness requires conformance to approved acceptance scenarios and operator acceptance.

## 3. Recorded product constraints

| Requirement | Status | Current statement |
|---|---|---|
| `PRD-USER-001` | recorded_repo_truth_pending_confirmation | Jens is the initial and primary operator. |
| `PRD-PURPOSE-001` | recorded_repo_truth_pending_confirmation | The product reduces job-search false negatives and makes evidence and blockers visible. |
| `PRD-REGION-001` | recorded_repo_truth_pending_confirmation | Primary scope is Hannover and remote-in-Germany opportunities. |
| `PRD-VOLUME-001` | recorded_repo_truth_pending_confirmation | Quality and controlled understanding are more important than maximum result volume. |
| `PRD-EVIDENCE-001` | recorded_repo_truth_pending_confirmation | Product conclusions must expose their evidence and uncertainty. |
| `PRD-SOURCE-001` | recorded_repo_truth_pending_confirmation | Original/source evidence is preferred over unverified aggregator-only claims. |
| `PRD-SAFETY-001` | approved | Mutating actions require explicit boundaries, dry-run/apply separation where applicable, auditability and operator gates. |
| `PRD-AUTO-001` | approved | No automatic application submission is part of the current product. |
| `PRD-TRUTH-001` | approved | Reports and exports are outputs, not pipeline source-of-truth inputs. |

## 4. Product behavior requiring operator decisions

The exact product cannot be declared complete until the following are approved in `PRODUCT_DECISION_REGISTER.md`:

- target roles and profile hierarchy;
- geography, commute, hybrid and remote rules;
- hard exclusions and soft preferences;
- job freshness and stale/unknown-date handling;
- source and evidence thresholds;
- Top-5 semantics, count and minimum quality;
- ranking factors and uncertainty treatment;
- duplicate and multi-source handling;
- treatment of employer observations without a concrete active job;
- already-seen, rejected and applied-job behavior;
- review workflow and operator actions;
- daily/weekly product cadence;
- V1 presentation and success metrics.

No agent should infer these decisions from code or historical implementation notes.

## 5. V1 contract structure

The approved V1 PRD must eventually define:

### 5.1 Inputs

- which sensors and sources may contribute;
- minimum evidence for a concrete job;
- accepted freshness and location evidence;
- approved target-profile facts.

### 5.2 Processing behavior

- hard filtering;
- deduplication;
- role-family classification;
- fit and ranking semantics;
- uncertainty and missing-data treatment;
- separation of jobs, employers and research candidates.

### 5.3 Operator output

- what appears in the primary review queue;
- what every result must explain;
- which actions are available;
- which actions are proposal-only or forbidden;
- how fewer-than-target results are represented.

### 5.4 Success metrics

- relevance and false-negative expectations;
- freshness;
- evidence completeness;
- operator review effort;
- ranking usefulness;
- safe handling of uncertainty;
- reproducibility across repeated runs.

## 6. Non-goals until explicitly approved

The following remain outside Product V1 unless the operator changes the contract:

- automatic application submission;
- autonomous source activation;
- hidden ranking or unexplained fit claims;
- filling a result quota with below-threshold jobs;
- cloud, Kafka or Spark work without demonstrated product value;
- LLM-generated application artifacts before approved inputs, facts and review workflow exist.

## 7. Delivery rule

A product-shaping backlog item is ready only when it references:

1. at least one approved PRD requirement;
2. at least one approved acceptance scenario;
3. a visible operator outcome;
4. a technical validation plan;
5. an operator acceptance step.

Until the PRD rebaseline is approved, read-only evidence, bug fixes, safety work and operational stabilization may continue. Candidate creation, Top-5 semantics, ranking, review actions and other product-defining work remain gated by the relevant open decisions.
