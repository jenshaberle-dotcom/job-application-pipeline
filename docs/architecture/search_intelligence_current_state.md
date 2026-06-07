# Search Intelligence Current State

## Purpose

This document is the primary entry point for understanding the current Search Intelligence subsystem.

It intentionally describes the current architecture rather than historical evolution.

---

## Mission

<!-- DOC-001-DOC-002-CURRENT-SNAPSHOT:START -->
## Current Operational Snapshot — 2026-06-07

This project is currently in a Search Intelligence stabilization phase.

The operational funnel is:

```text
Market Sensors
→ Candidate Promotion / Türsteher
→ URL Finder
→ Evidence Gates
→ Connector Build Candidate
→ Bronze / Silver / Gold
→ UI / Operations
```

Current truth table:

| Area | Status | Current Interpretation |
|---|---|---|
| Market Sensors | Implemented, not the current priority bottleneck | Existing sensors appear sufficient for the next validation step; new sensors are not the immediate fix. |
| Candidate Promotion / Türsteher | Implemented, suspected false-negative contributor | Do not rewrite first; validate with a bounded guest-list/reprocessing campaign. |
| StepStone Discovery Iteration Closure / Wave Search Intelligence | Built but operationally unvalidated | Code/tests exist, but practical rotation/new-company yield and scheduler integration still need validation. |
| URL Finder / Origin Source Discovery | Implemented, EO-002B validation runner added | Measure selected URLs, alternatives, rejected URLs, confidence and risk level across real candidates with `run_eo002b_url_finder_validation.py`. |
| Evidence Gates | Implemented, may be correctly defensive or too strict | EO-002B should identify where candidates stop before gate thresholds are changed; gate-stop report join remains the next follow-up. |
| Candidate Reprocessing Benchmark | Implemented as dry-run-first safety tool with guest-list support | Use repeated `--company-key` arguments for bounded EO-002B candidates instead of broad manual poking. |
| Scheduler / Orchestrator | Present but not trusted as fully validated | Do not rely on automation until Wave Search Intelligence behavior is verified. |
| Governance | DOC-001 established | System Impact, Drift, Lessons Learned, White Whale, Conversation Health and Reflection checks are now repo-level rules. |
| Documentation | DOC-002 baseline in progress | Current-state docs are being reconciled before the next large behavior-changing block. |

Immediate sequence:

1. DOC-001 Governance Foundation Gate.
2. DOC-002 Documentation Drift Baseline.
3. EO-002B Candidate Reprocessing & URL Finder Validation foundation.
4. EO-002B gate-stop metrics join and decision report.
5. Wave Search Intelligence + Scheduler/Orchestrator validation.
6. Larger Adrian-quality documentation/design polish.

Important boundary:

Do not present built Search Intelligence features as operationally complete until realistic data runs validate them.
<!-- DOC-001-DOC-002-CURRENT-SNAPSHOT:END -->

The project has evolved from a job-search pipeline into a Personal Market Intelligence Platform.

The goal is continuous improvement of:

- Market Understanding
- Discovery Coverage
- Vocabulary Coverage
- Candidate Understanding
- Capability-Gap Visibility

---

## Source Taxonomy

### Source Type

Technical acquisition category.

Examples:

- Official API
- ATS API
- Career Site
- Aggregator
- Structured Job Board

### Source Role

Strategic responsibility within the system.

Examples:

- Company Discovery
- Market Discovery
- Origin Validation
- Ground Truth

See:

- source_taxonomy_and_source_roles.md

---

## Search Intelligence Flow

Exploration & Discovery Sources
↓
Market Evidence
↓
Company Vocabulary
↓
Candidate Intelligence
↓
Search-Term Value
↓
Capability Gap
↓
Employer-Origin Connector Generation
↓
Confirmed Origin Jobs / Better Market Evidence
↓
Future Gold Layer Analytics

---

## Market Evidence

Observed market signals.

Examples:

- Companies
- Roles
- Technologies
- Skill Vocabulary

---

## Company Vocabulary

Observed terminology extracted from market evidence.

Examples:

- analytics
- cloud
- platform
- kafka
- databricks

---

## Candidate Intelligence

Represents:

- Current capability
- Transition assets
- Growth areas

---

## Search-Term Value

Combines:

- Market Evidence
- Vocabulary Signals
- Candidate Direction

Purpose:

Prioritize valuable market terminology.

---

## Capability Gap

Identifies learning opportunities between market demand and current capability.

Examples:

- Spark
- Kafka
- Databricks
- Cloud Data Platforms

---




## Aggregator Novelty Loop

S6B introduces a DB-backed novelty and saturation assessment for bounded aggregator sources.

It reads existing Market Evidence and compares it with known employer-origin candidates and known company vocabulary. The output is a reviewable snapshot that distinguishes unregistered candidate backlog from truly newly observed cycle evidence, and indicates whether the current bounded query is still finding new companies/terms, unresolved candidate reassessment pressure, or mostly saturated repeated evidence.

This layer does not fetch additional pages, mutate profiles, activate sources or write Bronze records.

---
## Employer-Origin Connector Generation

S6A adds a planning layer that turns DB-backed employer-origin candidate gate evidence into a connector-generation plan.

This is the current Ground Truth expansion path. It prepares bounded connector artifact dry runs after source analysis and feasibility gates are satisfied, but it does not activate sources or write Bronze records.

---

## Discovery Metrics

Examples:

- New Companies Discovered
- New Vocabulary Discovered
- Confirmed Origin Jobs
- Connector Generation Plans Ready
- Search-Term Portfolio Growth

---

## Ground Truth Metrics

Examples:

- Relevant Jobs
- Unique Jobs
- Data Quality
- Operational Stability

---

## Related Documents

- source_taxonomy_and_source_roles.md
- search_intelligence_architecture.md
- search_intelligence_terminology.md
- historical_terminology.md
- ../source_analysis/employer_origin_connector_generation_foundation.md

## S6C Current State

Approval-gated connector build requests are now modeled as a separate foundation. This enables unresolved high-pressure candidates to move from repeated observation into reviewable connector artifacts without granting registration or activation automatically.


## S6D Current State

The Search Intelligence Control Center provides a browser-readable operational view for the now connected Search Intelligence chain. It brings active connectors, unresolved candidates, build approvals and registration approval opportunities into one DB-backed UI so that the project no longer depends on long console output for daily review.

## S7A Gold Market Coverage

Current Search Intelligence state now includes a first Gold read-model foundation:

- `gold_market_coverage_summary`
- `gold_candidate_lifecycle_status`
- `gold_approval_queue`
- `gold_source_health_summary`

These views are read-only and are intended to support the tabbed Control Center, daily status checks and demo-ready market coverage reporting.

S7B connects the Control Center to the Gold Search Intelligence views. The UI remains a functional foundation, but its KPIs and candidate lifecycle now come from dashboard-ready Gold read models instead of raw Search Intelligence tables.

<!-- EO-002C-CURRENT-STATE:START -->
## EO-002C Current-State Addition — Reprocessing Decision Report

EO-002C adds a read-only decision-report scaffold on top of EO-002B URL Finder validation reports.

Status:

- implemented as reporting code,
- no DB writes,
- no scheduler change,
- no gate rewrite,
- intended to decide whether the next block should improve URL discovery, join gate history, revise the Türsteher, or proceed to Wave/Scheduler validation.

This keeps the project from jumping from raw validation output directly into broad behavior changes.
<!-- EO-002C-CURRENT-STATE:END -->

<!-- EO-002D-CURRENT-STATE:START -->
## EO-002D Current-State Addition — URL Finder Repair

EO-002D repairs the first URL Finder bottleneck found by the EO-002B/EO-002C smoke run.

Status:

- corporate-alias deterministic URL generation improved,
- Hannover Rück / Hannover Re alias domains are now generated within the bounded default budget,
- E.ON parent-careers domains are now generated within the bounded default budget,
- no candidate URL write,
- no scheduler change,
- no gate weakening.

This keeps the next Search Intelligence step focused on URL discovery quality before Türsteher, gate or scheduler changes.
<!-- EO-002D-CURRENT-STATE:END -->

<!-- ARCH-001-SAFETY-SECURITY-STATE:START -->
## ARCH-001 Current State Impact

The current Search Intelligence architecture is in freeze/maturity mode.

EO-002D improved origin URL discovery for the current benchmark cases. The next implementation work must not add opportunistic feature breadth. It must follow ARCH-001:

- identify the safety zone before changing behavior
- identify agent permissions before adding writes or external calls
- preserve read-only validation as separate from write/apply flows
- use the candidate lifecycle state machine for transitions
- use gate contracts for stop reasons and next safe actions
- treat security controls as architecture requirements, not polish

Next active block after ARCH-001: EO-002E Gate Stop / Next-Safe-Action Evidence Analysis.
<!-- ARCH-001-SAFETY-SECURITY-STATE:END -->

<!-- EO-002E-CURRENT-STATE:START -->
## EO-002E Current-State Addition — Gate Stop / Next-Safe-Action Evidence Analysis

EO-002E applies the ARCH-001 freeze to the first post-URL-discovery bottleneck.

Status:

- implemented as read-only reporting and analysis,
- joins optional EO-002B URL Finder report evidence with DB candidate/gate/action-run state,
- does not write candidate URLs, gates, evidence, connectors, source activation or scheduler state,
- makes the URL persistence boundary explicit when a selected URL exists only in a validation report.

Current interpretation:

- EO-002D made URL discovery strong enough for the current benchmark pair,
- EO-002E determines whether the next safe step is SZ1 candidate URL persistence review, SZ2 gate/evidence work, or manual review,
- SENSOR-001 BA Remote/Nationwide Coverage Validation is a confirmed roadmap gap, but not an immediate architecture change.
<!-- EO-002E-CURRENT-STATE:END -->

<!-- BEGIN CAND-001-CURRENT-STATE -->
## CAND-001 Candidate URL Persistence State

EO-002E showed that validated origin URLs can exist only in URL-Finder reports while `candidate_url` remains empty. CAND-001 introduces the reviewed SZ1 transition for persisting those URLs into candidate metadata.

This is a state transition, not a gate relaxation. It must happen before downstream detail-evidence or connector-candidate decisions rely on candidate-origin URL state.
<!-- END CAND-001-CURRENT-STATE -->

<!-- BEGIN GATE-001-CURRENT-STATE -->
## GATE-001 Current-State Addition

After CAND-001, validated origin URLs can become persisted candidate state under SZ1 review/apply control. GATE-001 is the next SZ2 step: initial gate review for `source_discovery`, `technical_reachability_gate` and `risk_gate`. Passing these gates should lead to bounded detail evidence discovery, not connector registration or activation.
<!-- END GATE-001-CURRENT-STATE -->
