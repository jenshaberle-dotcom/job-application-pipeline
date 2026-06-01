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
