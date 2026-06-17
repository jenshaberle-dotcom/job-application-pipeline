# LLM Application Workflow and CV Update Agent Roadmap

Status: planning
Scope: job-application-pipeline
Created: 2026-06-17
Intent: capture planned LLM usage points for job matching, employer enrichment, application artifact generation, CV optimization, and a later CV update agent.

## Why this belongs in the pipeline project

The job-application-pipeline is intended to become more than a collector of job postings. The long-term product goal is to support a controlled application workflow:

- discover relevant jobs,
- evaluate personal fit against Jens profile,
- explain why a job is relevant or not relevant,
- support application documents,
- learn from the portfolio projects,
- and keep CV/application positioning aligned with real project progress.

LLM usage should therefore be designed as explicit, governed product capability inside the pipeline roadmap, not as ad-hoc chat work.

This document records the intended LLM usage points and prioritizes them according to product value, dependency order, and governance risk.

## Priority overview

| Priority | Capability | Short description | Current decision |
| --- | --- | --- | --- |
| P1 | Job-Fit-Scoring | LLM evaluates pipeline jobs against Jens profile and returns explained relevance values. | Highest product relevance, but only after deterministic baseline and governance boundaries exist. |
| P2 | CV Optimization | LLM suggests job-specific CV highlights based on existing CV facts and project evidence. | Valuable for applications, but must not invent experience. |
| P2/P3 | Application Letter Generation | LLM drafts application letters from pipeline job data, Jens profile, and approved CV facts. | High usability value, dependent on profile/CV fact model and artifact workflow. |
| P3 | Employer Classification | LLM enriches employers with industry/domain signals to improve discovery and review. | Useful, but evidence-backed classification is required to avoid hallucinated employer metadata. |
| P4 | CV Update Agent | Agent analyzes pipeline and MCP progress, extracts portfolio-relevant skills, and proposes CV updates. | Strategic later capability; read-only proposal mode first, human approval required. |

## 1. Job-Fit-Scoring

Priority: P1
Product area: Matching, review queue, Top-5 jobs, decision support

Goal:
Use an LLM to evaluate each relevant pipeline job against Jens personal and professional profile and produce an explainable relevance assessment.

Expected output examples:

- relevance score,
- fit category,
- positive signals,
- negative signals,
- uncertainty,
- missing evidence,
- travel/remote/working-hours concerns,
- salary or seniority concerns,
- explanation suitable for UI review.

Why it matters:
This is closest to the core value of the pipeline. The system should not only collect jobs; it should help decide which jobs deserve attention.

Important profile signals:

- Data Engineer target direction,
- Product Owner and engineering background,
- low travel preference,
- Hannover/remote preference,
- 35h/week preference,
- target salary around 83k EUR,
- portfolio project evidence,
- MCP project as engineering automation evidence.

Governance requirements:

- No hidden scoring.
- Every score needs a reason.
- Missing evidence must be explicit.
- LLM score must not overwrite deterministic hard filters.
- Travel requirement should remain a strong personal-fit signal.
- LLM output should be stored as proposal/review signal, not as final truth.
- Cost and provider calls must be controlled before production use.

Recommended sequencing:
Build after deterministic matching and profile facts are stable enough to ground the LLM. This should likely become the first real LLM-backed product capability.

## 2. Employer Classification

Priority: P3
Product area: Discovery, employer-origin candidates, market intelligence

Goal:
Use an LLM to classify employers by industry, domain, technology relevance, likely data/AI maturity, and potential fit for Jens profile.

Potential classification fields:

- industry,
- business domain,
- employer type,
- likely tech/data maturity,
- public sector / insurance / automotive / energy / IT service provider signals,
- relevance for Data Engineering transition,
- evidence basis,
- uncertainty.

Why it matters:
Employer classification can improve discovery prioritization and help identify attractive employer-origin sources beyond pure keyword matching.

Risks:

- Employer metadata can be hallucinated.
- Company names can be ambiguous.
- Classification may become stale.
- Classification must not become a hard gate without evidence.

Governance requirements:

- Evidence-backed only.
- Store uncertainty.
- Separate inferred classification from verified facts.
- Do not let LLM classification create candidates or gate decisions automatically.
- Use as review and prioritization signal first.

Recommended sequencing:
Add after the employer-origin discovery loop is stable enough to benefit from enrichment. This is valuable, but should not block the current EXPAND/GENERIC closure work.

## 3. Application Letter Generation

Priority: P2/P3
Product area: Application artifacts, candidate workflow, document generation

Goal:
Use an LLM to draft tailored application letters based on:

- job detail data,
- employer context,
- Jens approved CV facts,
- portfolio project evidence,
- MCP project evidence where relevant,
- job-fit scoring explanation.

Why it matters:
This turns the pipeline from a discovery system into an application-support system.

Dependencies:

- stable job detail data,
- approved CV fact base,
- job-fit scoring or at least matching rationale,
- artifact workflow,
- human review step,
- no invented experience.

Governance requirements:

- Drafts are review artifacts only.
- No automatic sending.
- No fabricated skills, degrees, employers, dates, or project claims.
- Every generated claim should be traceable to profile/CV/project evidence.
- Separate ATS-friendly content from design/layout generation.

Recommended sequencing:
After job-fit scoring and profile/CV fact grounding. It is useful, but should not be the first LLM capability because it depends on upstream relevance and evidence.

## 4. CV Optimization

Priority: P2
Product area: CV tailoring, application artifacts, profile positioning

Goal:
Use an LLM to propose which existing CV highlights should be emphasized for a specific job.

Examples:

- emphasize Data Engineering project work,
- emphasize pipeline architecture,
- emphasize PostgreSQL/Python/testing/CI/CD,
- emphasize Product Owner experience where helpful,
- emphasize MCP engineering automation project for roles involving automation, governance, AI tooling, or platform engineering.

Important boundary:
The LLM should optimize selection and wording of existing evidence, not invent new experience.

Expected output:

- suggested CV highlight set,
- job-specific profile summary,
- relevant project bullets,
- risks or weak areas,
- missing evidence,
- suggested wording with source rationale.

Governance requirements:

- Approved CV facts are source of truth.
- Project claims must reflect real repository state.
- The MCP project may be used as a necessary and valuable part of Jens development story where relevant.
- Suggestions require human approval before being used in CV documents.
- No automatic modification of canonical CV files.

Recommended sequencing:
After a CV/profile fact model exists and before or alongside application letter generation.

## 5. CV Update Agent

Priority: P4 strategic
Product area: Portfolio learning loop, career narrative, profile maintenance

Goal:
Design a later agent that periodically analyzes progress in both the job-application-pipeline and the mcp-autonomous-engineering-agent projects, extracts portfolio-relevant findings, and proposes CV/profile updates.

Important distinction:
This is not a free-writing bot. It is a governed update loop.

Inputs:

- pipeline repository progress,
- MCP repository progress,
- sealed PRs and milestones,
- validation results,
- architecture decisions,
- project capabilities,
- portfolio-relevant skills,
- actual implemented evidence.

Potential outputs:

- suggested CV bullet updates,
- suggested project description updates,
- suggested LinkedIn/GitHub profile highlights,
- skill evidence matrix,
- role-positioning recommendations,
- stale or outdated CV claims,
- missing evidence for target roles.

Governance requirements:

- Read-only analysis first.
- No automatic CV rewrite.
- No automatic commits to CV documents.
- Human approval required.
- Must cite project evidence or repository state.
- Must distinguish implemented capability from planned capability.
- Must avoid turning every implementation detail into CV material.
- Should run as a controlled proposal agent, not as a source of truth.

Why it matters:
This creates a feedback loop between real engineering progress and job-market positioning. It can make the portfolio project more valuable because implemented capabilities are not forgotten or underrepresented in applications.

White-Whale risk:
High. This should be parked as a later governed capability, not built before the current pipeline/MCP fundamentals are stable.

Recommended sequencing:
After the application workflow has stable job-fit scoring, CV facts, and artifact generation. The first version should be a manual/read-only report, not an autonomous update system.

## System impact check

Affected pipeline areas:

- Matching and scoring
- Job review queue
- Employer-origin discovery
- Application artifact generation
- CV/profile data model
- Portfolio evidence tracking
- LLM/provider governance
- Cost and budget control
- Audit and review outputs

Risks:

- hallucinated employer metadata,
- invented CV claims,
- over-weighting LLM scores,
- unclear source of truth,
- provider cost growth,
- mixing planned capability with implemented evidence,
- turning strategic agents into distracting White-Whale work.

Required future safeguards:

- provider/cost gate before real LLM calls,
- structured prompt and output schema,
- deterministic hard filters before LLM judgement,
- human review workflow,
- audit trail for generated recommendations,
- explicit distinction between proposal, review state, and accepted truth,
- tests for schema validation and fail-closed behavior.

Current decision:

This roadmap is accepted as planning input. It does not authorize real provider calls, database writes, candidate creation, gate decisions, scheduler changes, or automatic CV updates.

Near-term next action remains the controlled pipeline readiness and EXPAND/GENERIC dependency closure path. The first likely implementation candidate from this roadmap is Job-Fit-Scoring, but only after the current discovery and review chain is stable enough to provide reliable grounded input.
