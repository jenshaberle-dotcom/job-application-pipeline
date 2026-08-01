# Job Application Pipeline Product Requirements

Status: **draft product rebaseline — partially operator-approved**
Product owner and primary user: **Jens**
Project character: **A — Intent Locked**

## 1. Product objective

The Job Application Pipeline is a personal Search Intelligence and application-preparation system for Jens.

Its purpose is to:

- reduce job-search false negatives caused by noisy aggregators, repeated promoted result blocks, weak search terms, missing origin evidence and overly safe stops;
- discover relevant employers conservatively and validate concrete jobs on employer-origin sources;
- rank a small set of strategically useful current vacancies;
- assist with truthful, reviewable application artifacts;
- expose the complete workflow through a React Control Center in the Deep Ocean Intelligence visual language;
- preserve operator control over product semantics, activation, mutation and application decisions.

## 2. Approved product pillars

### 2.1 StepStone company-discovery waves

StepStone is used conservatively as a company initial finder.

Because the first result page repeatedly exposes the same prominent company blocks and the project intentionally avoids broad pagination or aggressive aggregator crawling, the system rotates bounded temporary company-exclusion waves across approved search terms.

Known companies are cooled down per search space rather than permanently blacklisted. The purpose is to reveal other employers while retaining the ability to rediscover known companies later.

The approved ML-first search raster is defined in `docs/planning/active/canonical_target_profile.md` and versioned through migrations. A search term does not receive `NOT` waves until its StepStone stability has been separately validated.

### 2.2 Top-5 system

The product must select a bounded set of current concrete vacancies that:

- are validated on the employer origin source/seed or an approved equivalent origin-evidence path;
- satisfy the approved profile and later-approved hard criteria;
- offer a credible medium- to long-term path toward Machine Learning Engineering with Reliability focus;
- expose evidence, uncertainty and ranking reasons.

Exact count, minimum threshold and behavior when fewer jobs qualify remain open decisions.

### 2.3 CV and application-letter assistant

The product must support AI-assisted preparation of job-specific CV and application-letter drafts based on:

- an operator-provided canonical CV;
- an operator-provided canonical base application letter;
- the validated concrete vacancy;
- explicitly approved additional facts.

The assistant must not invent experience, skills, achievements, employers, dates or qualifications. Generated artifacts remain proposals requiring operator review. Automatic submission is prohibited.

### 2.4 React Deep Ocean Intelligence Control Center

The primary product interface is a React Control Center using the Deep Ocean Intelligence design language.

It must eventually provide operator-facing access to:

- discovery-wave status and market coverage;
- employer/origin evidence;
- current Top-5 jobs and ranking explanations;
- uncertainty and blockers;
- review actions and lifecycle state;
- CV and application-letter draft preparation.

The exact V1 screen, interaction model and minimum end-to-end journey remain open decisions.

## 3. Product authority contract

The operator decides product behavior.

DON may independently choose technical implementation within approved requirements. DON may propose product changes, but every proposal remains non-authoritative until explicitly approved.

A green technical test does not prove product correctness. Product correctness requires conformance to approved acceptance scenarios and operator acceptance.

## 4. Approved and recorded product constraints

| Requirement | Status | Current statement |
|---|---|---|
| `PRD-USER-001` | recorded_repo_truth_pending_confirmation | Jens is the initial and primary operator. |
| `PRD-PURPOSE-001` | approved | The product reduces false negatives, validates origin evidence, ranks useful jobs, supports application preparation and exposes the workflow through a controlled UI. |
| `PRD-PROFILE-001` | approved | Canonical identity: Machine Learning Engineer with strong Data Engineering/data-centric ML focus and Reliability as the future specialization direction. |
| `PRD-SEARCH-001` | approved | StepStone is a conservative company initial finder using bounded temporary company-exclusion waves; no broad pagination or aggressive crawler behavior. |
| `PRD-REGION-001` | approved | Hannover is the geographic center; realistically commutable regional roles and Germany-based fully remote roles are admissible. |
| `PRD-COMMUTE-001` | approved | Around 30 minutes per direction is ideal; up to around 45 minutes is generally acceptable by car or public transport. Public-transport quality is a soft positive signal. |
| `PRD-WORKMODEL-001` | approved | Hybrid, onsite and fully remote are admissible. Hybrid is preferred only between otherwise comparable roles. |
| `PRD-VOLUME-001` | recorded_repo_truth_pending_confirmation | Quality and controlled understanding are more important than maximum result volume. |
| `PRD-EVIDENCE-001` | recorded_repo_truth_pending_confirmation | Product conclusions must expose their evidence and uncertainty. |
| `PRD-SOURCE-001` | approved | Aggregators discover; employer-origin evidence confirms Top-5 eligibility. |
| `PRD-APPLICATION-001` | approved | CV and letter generation is proposal-only, source-grounded and operator-reviewed. |
| `PRD-SAFETY-001` | approved | Mutating actions require explicit boundaries, dry-run/apply separation where applicable, auditability and operator gates. |
| `PRD-AUTO-001` | approved | No automatic application submission is part of the current product. |
| `PRD-TRUTH-001` | approved | Reports and exports are outputs, not pipeline source-of-truth inputs. |

## 5. Product behavior still requiring operator decisions

The exact product cannot be declared complete until the following are approved in `PRODUCT_DECISION_REGISTER.md`:

- accepted seniority and adjacent-role behavior;
- required and disqualifying task content independent of title;
- employment, language, salary, industry and working-time constraints;
- handling of unclear location, office frequency and travel requirements;
- job freshness and stale/unknown-date handling;
- minimum active-job evidence and aggregator-only treatment outside Top 5;
- Top-5 count, threshold and behavior when fewer jobs qualify;
- full ranking factors, uncertainty treatment and explanations;
- duplicate and multi-source handling;
- treatment of employer observations without a concrete active job;
- already-seen, rejected and applied-job behavior;
- review workflow and operator actions;
- daily/weekly product cadence;
- React V1 presentation and success metrics.

No agent should infer these decisions from code or historical implementation notes.

## 6. V1 contract structure

### 6.1 Inputs

- approved search sensors and sources;
- employer-origin source/seed evidence;
- accepted freshness and location evidence;
- canonical target-profile facts;
- canonical CV and base application letter supplied by the operator.

### 6.2 Processing behavior

- conservative StepStone company discovery;
- employer/origin validation;
- hard filtering;
- deduplication;
- role-family and task-content classification;
- fit and ranking semantics;
- uncertainty and missing-data treatment;
- separation of jobs, employers and research candidates;
- source-grounded application-draft generation.

### 6.3 Operator output

- discovery and origin status;
- a bounded primary job review queue;
- visible evidence and uncertainty;
- ranking explanations;
- approved review actions;
- reviewable CV and application-letter drafts.

### 6.4 Success metrics

- relevance and false-negative expectations;
- freshness and origin-evidence completeness;
- operator review effort;
- ranking usefulness;
- safe handling of uncertainty;
- truthfulness of application artifacts;
- reproducibility and runtime reliability.

## 7. Non-goals until explicitly approved

- automatic application submission;
- autonomous source activation;
- hidden ranking or unexplained fit claims;
- filling a result quota with below-threshold jobs;
- treating aggregator-only evidence as confirmed Top-5 truth;
- cloud, Kafka or Spark work without demonstrated product value;
- application artifacts built from unapproved or invented facts.

## 8. Delivery rule

A product-shaping backlog item is ready only when it references:

1. at least one approved PRD requirement;
2. at least one approved acceptance scenario;
3. a visible operator outcome;
4. a technical validation plan;
5. an operator acceptance step.

Until the remaining PRD decisions are approved, read-only evidence, bug fixes, safety work, search-profile migration work and operational stabilization may continue. Candidate creation, final Top-5 semantics, ranking, review actions and other unresolved product behavior remain gated by the relevant open decisions.
