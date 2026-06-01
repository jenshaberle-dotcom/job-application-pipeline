# Search Intelligence Architecture

## Purpose

Search Intelligence extends the ingestion platform beyond job collection.

The goal is continuous improvement of market understanding, vocabulary coverage,
candidate fit understanding and capability-gap visibility.

---

## End-to-End Flow

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

## Exploration & Discovery

Examples:

- StepStone
- LinkedIn
- Indeed
- Bundesagentur

Outputs:

- Company Discovery
- Market Discovery
- Vocabulary Discovery

---

## Market Evidence

Observed market signals extracted from discovery-oriented sources.

Examples:

- Companies
- Roles
- Technologies
- Skill vocabulary

---


## Aggregator Novelty Loop

Evaluates bounded aggregator market evidence over learning cycles.

Purpose:

- separate unregistered companies from known employer-origin candidates
- separate newly observed companies/terms from repeated cycle evidence
- identify unresolved known candidates that require gate reassessment
- detect saturation when limited result windows stop producing novelty

Boundary:

- no pagination
- no source-limit circumvention
- no search-profile mutation
- no source activation
- no Bronze writes
- no scheduler changes

---

## Company Vocabulary

Observed terminology associated with companies and market segments.

Examples:

- analytics
- cloud
- platform
- databricks
- kafka

---

## Candidate Intelligence

Represents current capability and future career direction.

Examples:

- Existing strengths
- Transition assets
- Growth areas

---

## Search-Term Value

Combines:

- Market Evidence
- Vocabulary Signals
- Candidate Intelligence

Purpose:

Prioritize terms that provide meaningful market and career insight.

---

## Capability Gap

Identifies development opportunities between market demand and current capability.

Examples:

- Spark
- Kafka
- Databricks
- Cloud Data Platforms

---


## Employer-Origin Connector Generation

Transforms reviewed market and gate evidence into bounded connector-generation plans for origin sources.

Purpose:

- increase confirmed employer-origin Ground Truth
- reduce aggregator-only evidence dependency
- feed better origin evidence back into Market Evidence, Search-Term Value and Capability Gap evaluation

Boundary:

- no auto-PR
- no source activation
- no Bronze writes
- no recurring ingestion approval
- no CSV/Excel/export artifact as process input

---

## Future Gold Layer

Potential future outcomes:

- Learning ROI
- Career Path Analysis
- Market Trend Analysis
- Skill Investment Prioritization


## Current State Reference

See:

- search_intelligence_current_state.md

## S6C Approval-Gated Connector Build

The approval-gated connector build layer sits after Aggregator Novelty and Employer-Origin Connector Generation. It resolves the state where a candidate is repeatedly observed and still unresolved by allowing a bounded connector artifact build after explicit approval. Registration, source activation and Bronze persistence remain separate gates.


## S6D Control Center UI

The Search Intelligence Control Center is the product-facing control surface for the connector lifecycle. It does not introduce a new source of truth; it reads DB-backed candidates, gate reviews, reassessment signals, generation plans and build requests. Token-gated UI actions delegate to the same bounded CLI agents used by the pipeline.

## S7A Gold Market Coverage

S7A adds dashboard-facing Gold read models for Search Intelligence. These views consolidate candidate lifecycle state, FN pressure, connector-generation/build requests, approval queues, source health summaries and bounded aggregator novelty into UI-ready read models.

The Control Center should increasingly consume these Gold views instead of re-implementing decision logic from raw Search Intelligence tables.
