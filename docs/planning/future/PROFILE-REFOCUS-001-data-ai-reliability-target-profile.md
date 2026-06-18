# PROFILE-REFOCUS-001 — Data & AI Reliability Target Profile

Status: Planned profile refocus  
Owner: job-application-pipeline  
Scope: Target-profile / search-intelligence planning only  
Created: 2026-06-18  
Mutation class: repository documentation only  
Runtime impact: none  

## 1. Why this exists

The user's career direction is becoming more specific than generic Data
Engineering. The emerging profile is:

> Data & AI Reliability Engineering: building reliable, traceable, controllable
> AI-assisted data and agent systems with a focus on data quality, evidence
> chains, drift control, human-in-the-loop gates, observability, and safe
> automation.

The job-application-pipeline should therefore continue to search for Data
Engineering roles, but it must also learn to recognize adjacent roles where the
actual work is closer to AI Reliability, LLMOps, AI Observability, AI Assurance,
RAG Evaluation, Agentic AI Governance, and safe automation.

This is not a runtime change yet. It is a planning anchor for target-profile,
search-term, matching, and CV-reference updates.

## 2. Working positioning

Preferred portfolio label:

**Data & AI Reliability Engineering**

Short description:

> Aufbau zuverlässiger, nachvollziehbarer und kontrollierbarer KI-gestützter
> Daten- und Agentensysteme — mit Fokus auf Datenqualität, Evidence Chains,
> Drift-Kontrolle, Human-in-the-Loop-Gates, Observability und sichere
> Automatisierung.

English variant:

> Building reliable, traceable, and controllable AI-assisted data and agent
> systems with a focus on data quality, evidence chains, drift control,
> human-in-the-loop gates, observability, and safe automation.

## 3. Role families to recognize

The pipeline should not only look for job titles containing "Data Engineer".
It should increasingly recognize these role families:

| Cluster | Example titles | Matching intent |
| --- | --- | --- |
| Core Data Engineering | Data Engineer, Data Platform Engineer, Analytics Engineer | Keep as foundation; strong fit when engineering-heavy. |
| DataOps / Platform | DataOps Engineer, Platform Engineer Data, Data Reliability Engineer | Strong fit when reliability, automation, CI/CD, observability, and data quality are central. |
| MLOps / LLMOps | MLOps Engineer, LLMOps Engineer, AI Platform Engineer | Strong fit when production AI systems, monitoring, routing, evaluation, and deployment are central. |
| AI Reliability | AI Reliability Engineer, AI Systems Reliability Engineer, AI Quality Engineer | Very strong fit when role focuses on reliable, observable, controlled AI systems. |
| AI Assurance / Responsible AI | AI Assurance Engineer, Responsible AI Engineer, AI Governance Engineer | Strong fit when technical governance, controls, risk, auditability, and evaluation are concrete. |
| RAG / Evaluation | RAG Engineer, AI Evaluation Engineer, LLM Evaluation Engineer | Strong fit when retrieval quality, answer grounding, evals, traces, and evidence are central. |
| Agentic Systems | Agentic AI Engineer, AI Agent Engineer, Agentic Systems Engineer | Strong fit only when safety, observability, tool boundaries, and controlled autonomy are part of the work. |

## 4. Search term families

### 4.1 Primary title and role terms

```text
Data & AI Reliability Engineer
AI Reliability Engineer
AI Systems Reliability Engineer
Data Reliability Engineer
LLMOps Engineer
MLOps Engineer
AI Platform Engineer
AI Engineer
RAG Engineer
AI Evaluation Engineer
AI Observability Engineer
AI Assurance Engineer
Responsible AI Engineer
AI Governance Engineer
Agentic AI Engineer
Agentic Systems Engineer
Data Quality Engineer
Data Governance Engineer
```

### 4.2 Technical and domain signals

```text
LLMOps
MLOps
AI Observability
LLM Observability
RAG Evaluation
RAG Observability
AI Evaluation
Evals
LLM-as-a-Judge
Tracing
Evidence Chains
Evidence-Based AI
Drift Detection
Drift Control
Model Monitoring
Data Quality
Data Lineage
Data Provenance
Data Governance
AI Governance
AI Assurance
Responsible AI
Human-in-the-Loop
Guardrails
Policy Gates
Agent Monitoring
Agentic AI
Reliable AI Agents
Safe Automation
Model Routing
Cost Control
Prompt Injection
AI Security
AI Safety
```

### 4.3 Technical bridge terms

```text
Python
SQL
PostgreSQL
Docker
CI/CD
GitHub Actions
pytest
Observability
Telemetry
Event-driven Architecture
Kafka
Data Pipelines
ETL
ELT
Data Warehouse
Data Lakehouse
API Integration
Cloud
Azure
AWS
GCP
```

### 4.4 German-language terms

```text
KI-Zuverlässigkeit
KI-Governance
KI-Qualitätssicherung
KI-Beobachtbarkeit
KI-Absicherung
KI-Risikomanagement
KI-Agenten
Agentische KI
Nachvollziehbarkeit
Datenqualität
Datenherkunft
Daten-Governance
Drift-Erkennung
Drift-Kontrolle
Mensch-in-der-Schleife
sichere Automatisierung
prüfbare KI-Systeme
```

## 5. Matching implications

Future matching logic should distinguish several signal levels.

### Strong positive signals

- AI reliability, LLMOps, MLOps, AI observability, RAG evaluation, AI assurance,
  AI governance, or reliable AI agents are explicit role responsibilities.
- The role combines data pipelines or platform engineering with production AI
  reliability.
- The role mentions evaluation, tracing, monitoring, drift detection, evidence,
  policy gates, guardrails, or human-in-the-loop workflows.
- The role includes Python, SQL, CI/CD, cloud, APIs, observability, or platform
  engineering.

### Medium positive signals

- Generic AI Engineer role with production/system focus.
- Data Engineer role with strong data quality, lineage, governance, or
  observability elements.
- Platform role where AI/ML systems are a supported product area.

### Weak positive signals

- Data Analyst, BI, dashboarding, or reporting roles that mention AI only
  superficially.
- Prompt-engineering-only roles without system responsibility.
- Research-only ML roles without production, governance, or reliability focus.

### Negative or malus signals

- High travel requirement.
- Consulting role with frequent on-site customer travel.
- Pure sales/pre-sales AI role.
- Pure ML research role without engineering/production responsibility.
- Pure BI/reporting role without data engineering or AI reliability ownership.
- Vague "AI enthusiasm" without concrete systems, quality, governance, or
  observability work.

## 6. CV and portfolio reference text

Short CV positioning:

> Data & AI Reliability Engineering: Entwicklung zuverlässiger,
> nachvollziehbarer und kontrollierbarer KI-gestützter Daten- und
> Agentensysteme mit Fokus auf Datenqualität, Evidence Chains, Drift-Kontrolle,
> Human-in-the-Loop-Gates, Observability und sichere Automatisierung.

MCP project framing:

> Entwicklung eines MCP-basierten Control-Plane-Projekts zur kontrollierten
> Nutzung von KI-Agenten in Software- und Datenprojekten. Schwerpunkt:
> Repo-/DB-basierte Wahrheit, Drift-Erkennung, Evidence Chains, Read-only Gates,
> No-Mutation-Proof, Human-in-the-Loop-Freigaben, Agent Capability Governance
> und sichere Automatisierung.

Job-application-pipeline framing:

> Aufbau einer datengetriebenen Job-Application-Pipeline mit PostgreSQL, Python,
> Validierungslogik und Governance-Schichten. Schwerpunkt: kontrollierte
> Datenaufnahme, Source-Bewertung, Generik-Nachweis, Review-Gates,
> Observability und Vorbereitung auf Cloud-/Event-Architektur.

Combined portfolio story:

> Die Pipeline ist das datengetriebene Such- und Bewertungssystem. MCP ist die
> Reliability- und Governance-Control-Plane, die KI-gestützte Projektarbeit
> nachvollziehbar, kontrollierbar und drift-resistent machen soll.

## 7. Backlog implications for the pipeline

Future implementation can split into small, reviewable steps:

### PROFILE-REFOCUS-001A — Planning anchor

Add this document and preserve the search/profile direction.

Acceptance:
- Documentation only.
- No database, matching, source, scheduler, or export changes.

### PROFILE-REFOCUS-001B — Search-term registry extension

Add or update profile/search-term data so the pipeline can discover Data & AI
Reliability, LLMOps, AI Observability, AI Assurance, and Agentic AI Governance
roles.

Acceptance:
- Terms are DB-backed or repository-backed according to current architecture.
- No CSV/Excel/Markdown-as-pipeline-input violation.
- Terms are clearly classified by role family and signal strength.

### PROFILE-REFOCUS-001C — Matching signal model

Extend matching/scoring so relevant adjacent roles are recognized even if the
title does not contain "Data Engineer".

Acceptance:
- Search and scoring remain generic.
- No one-off company-specific logic.
- High travel remains strong malus.
- AI reliability / governance signals are positive but not blindly decisive.

### PROFILE-REFOCUS-001D — CV artifact alignment

Update CV/profile artifacts so the user's public profile and pipeline target
profile use the same positioning.

Acceptance:
- ATS-friendly language.
- Concrete project evidence from MCP and job-application-pipeline.
- No exaggeration beyond actual project maturity.

## 8. Non-goals

This planning slice does not:
- change active search terms
- modify the database
- modify matching logic
- activate new sources
- change scheduler behavior
- create exports
- use generated review artifacts as pipeline inputs
- claim the user already holds a formal AI Reliability title

## 9. Current status note

This is a direction-setting artifact. It captures an emerging profile and should
guide future pipeline search/matching/CV work. Runtime changes should follow only
after the current repository state is inspected and the implementation path is
made compatible with the pipeline's architecture rules.
