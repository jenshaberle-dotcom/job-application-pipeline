# Job Application Pipeline Product Requirements

Status: **active product rebaseline — partially operator-approved**  
Product owner and primary user: **Jens**  
Project character: **A — Intent Locked**  
Active product track: **PRODUCT-RECOVERY-001 / issue #783**

## 1. Product objective

The Job Application Pipeline is a personal Search Intelligence and application-preparation system for Jens.

Its purpose is to:

- reduce job-search false negatives caused by noisy aggregators, weak search terms, missing Employer-Origin evidence and stale/overly safe states;
- discover relevant employers conservatively;
- validate concrete current vacancies on Employer-Origin sources or explicitly approved equivalent origin evidence;
- rank a small set of strategically useful jobs under an explainable product contract;
- expose evidence, uncertainty and blockers through a React Control Center;
- assist with truthful, reviewable CV/application-letter preparation;
- preserve operator control over product semantics, source activation, ranking policy, provider actions and application decisions.

## 2. Approved product-value journey

The minimum Product V1 end-to-end journey is approved as:

```text
market discovery
-> Employer-Origin resolution
-> current exact vacancy
-> Bronze / Silver
-> assessment
-> capability fit
-> hard filters
-> deterministic ranking
-> bounded recommendation queue
-> selected job
-> Application Workspace
-> review-ready CV/letter package
```

This journey is the primary PRODUCT-RECOVERY-001 product truth.

## 3. Approved product pillars

### 3.1 Conservative market discovery

Aggregators and market sensors are used for bounded discovery/recall. StepStone remains a conservative company/job discovery input; existing bounded exclusion-wave logic is retained where it continues to provide value.

The central product boundary is broader than StepStone:

> **Aggregators discover; Employer-Origin evidence confirms Product/Application authority.**

BA, StepStone, GuteJobs or similar discovery evidence must not be presented as final employer-origin action truth merely because a job was observed there.

### 3.2 Employer-Origin and current vacancy truth

A recommendation must be a concrete current vacancy validated on the employer origin source/seed or an explicitly approved equivalent origin-evidence path.

Known stale/closed jobs must not remain current/actionable/recommended. Historical observations may remain in Bronze/Silver lineage.

The exact general policy for maximum posting age, unknown publication date and ambiguous/conflicting currentness evidence remains open in the decision register.

### 3.3 Top-5 system

The authoritative primary recommendation queue follows approved semantics:

- at most five jobs (`PD-050`);
- minimum overall quality **70/100** (`PD-051`);
- Employer-Origin/current-vacancy evidence (`PD-043`);
- no hard-filter failure (`PD-053`);
- missing required evidence blocks authoritative ranking (`PD-054`);
- visible score components, reasons and uncertainty (`PD-055`, `PD-056`).

The product may return fewer than five recommendations. It must **not** fill a quota with below-threshold, blocked or insufficiently evidenced jobs.

`rankable` and `recommended` are distinct: a job may have complete authoritative ranking inputs and still remain below the recommendation threshold.

### 3.4 Hard filters and capability fit

Approved hard-filter behavior includes:

- permanent employment required for Top-5 eligibility;
- German/English accepted working languages;
- weekly-hours compatibility with 35–40 hours;
- actual capability/requirement fit takes precedence over title-only seniority labels;
- missing required evidence remains manual-review-required rather than guessed.

Detailed decisions remain in `PRODUCT_DECISION_REGISTER.md`.

### 3.5 CV and application-letter assistant

The product supports job-specific application preparation from:

- operator-approved canonical/base CV;
- operator-approved canonical/base application letter;
- Candidate Facts;
- exact current vacancy evidence;
- explicitly approved additional facts.

Candidate Facts are the factual authority for candidate claims. Exact current vacancy evidence is the job-specific authority.

Provider/LLM behavior is approved only through the explicit operator **Generate application** action. During that action, approved base-document text may be shared with the configured provider as structure/style context. Provider output is a proposal and must not invent unsupported candidate facts.

The current document package may include:

- CV DOCX;
- CV PDF;
- application-letter DOCX;
- application-letter PDF;
- ZIP package/manifest.

Generated artifacts remain `draft_for_review`. Automatic submission/send is prohibited.

### 3.6 React Deep Ocean Intelligence Control Center

The primary reference UI is the React Control Center using the Deep Ocean Intelligence design language.

Current product surfaces include:

- jobs/review state;
- source/origin status;
- Bronze/Silver/Gold data-layer observability;
- ranking/evidence detail;
- Application Workspace and downloads.

The exact production V1 screen/device contract remains open (`PD-081`), but the current React Control Center is the reference implementation for Product Recovery.

### 3.7 Product-facing release history

Product-visible checkpoints are documented through GitHub Releases with explicit features, bug fixes, known limitations and relevant operator proof. Release history does not replace current docs/product authority; it provides auditable product change history beyond commit archaeology.

## 4. Product authority contract

The operator decides product behavior.

Engineering may independently choose technical implementation within approved requirements. Proposed product changes remain non-authoritative until explicitly approved.

A green technical test does not prove product correctness. Product correctness requires:

1. technical correctness;
2. conformance to approved PRD/decision/acceptance contracts;
3. operator acceptance of the visible outcome.

## 5. Approved and recorded product constraints

| Requirement | Status | Current statement |
|---|---|---|
| `PRD-USER-001` | recorded_repo_truth_pending_confirmation | Jens is the initial and primary operator. |
| `PRD-PURPOSE-001` | approved | The product reduces false negatives, validates Employer-Origin/current vacancy evidence, ranks useful jobs, supports application preparation and exposes the workflow through a controlled UI. |
| `PRD-E2E-001` | approved | Minimum V1 journey is discovery -> Employer-Origin -> current vacancy -> Bronze/Silver -> assessment/capability/hard filters -> deterministic ranking -> bounded recommendation queue -> Application Workspace -> review-ready document package. Approved 2026-09-03. |
| `PRD-PROFILE-001` | approved | Canonical identity: Machine Learning Engineer foundation; strong Data Engineering/data-centric ML focus; Reliability as future specialization. |
| `PRD-SEARCH-001` | approved | Aggregators/market sensors are bounded discovery inputs. StepStone may remain a conservative initial finder; aggregator evidence alone is not final recommendation/application authority. |
| `PRD-REGION-001` | approved | Hannover is the geographic center; realistically commutable regional roles and Germany-based fully remote roles are admissible. |
| `PRD-COMMUTE-001` | approved | Around 30 minutes per direction is ideal; up to around 45 minutes generally acceptable by car or public transport. Public-transport quality is a soft positive signal. |
| `PRD-WORKMODEL-001` | approved | Hybrid, onsite and fully remote are admissible. Hybrid is preferred only between otherwise comparable roles. |
| `PRD-VOLUME-001` | recorded_repo_truth_pending_confirmation | Quality and controlled understanding are more important than maximum result volume. |
| `PRD-EVIDENCE-001` | approved | Product conclusions must expose required evidence/uncertainty; missing required evidence does not become fabricated success. |
| `PRD-SOURCE-001` | approved | Aggregators discover; Employer-Origin evidence confirms Top-5/Application eligibility. |
| `PRD-TOP5-001` | approved | Top 5 means at most five jobs, minimum overall quality 70/100, and no quota filling below the approved threshold. |
| `PRD-APPLICATION-001` | approved | CV/letter generation is operator-triggered, source-grounded, proposal-only and operator-reviewed. Approved base document text may be provider structure/style context only during explicit Generate. |
| `PRD-SAFETY-001` | approved | Material mutations require explicit boundaries, appropriate dry-run/apply separation, auditability and operator gates. |
| `PRD-AUTO-001` | approved | No automatic application submission/send is part of the current product. |
| `PRD-TRUTH-001` | approved | Reports and exports are outputs, not pipeline source-of-truth inputs. |
| `PRD-RECOVERY-001` | approved | Current product recovery target is a normal observable cold-to-application flow producing at least five jobs that genuinely satisfy the approved recommendation contract plus a near-submission-quality review package. A truthful run may return fewer when fewer qualify. Approved 2026-09-03. |

## 6. Product behavior still requiring operator decisions

Open decisions remain in `PRODUCT_DECISION_REGISTER.md`. High-value unresolved areas include:

- adjacent-role/task-content boundaries (`PD-013`, `PD-014`);
- unclear/contradictory location, remote/travel evidence (`PD-024`, `PD-025`);
- company/industry exclusions (`PD-033`);
- maximum posting age, unknown publication date and general ambiguous-currentness proof (`PD-040`–`PD-042`);
- aggregator-only treatment outside Top 5 and duplicate/multi-source identity (`PD-044`–`PD-046`);
- deterministic vs LLM-assisted ranking and change explanations (`PD-057`, `PD-058`);
- already-viewed/rejected/applied/resurfacing and queue-diversity behavior (`PD-060`–`PD-065`);
- save/reject/refresh/park confirmation/reversibility and notifications (`PD-070`, `PD-072`–`PD-074`);
- exact production V1 screen/device expectations (`PD-081`);
- general false-positive/false-negative SLOs and numeric freshness/runtime reliability targets (`PD-083`, `PD-084`);
- complete production-readiness acceptance campaign and explicit final V1 non-goals (`PD-085`, `PD-086`).

Engineering must not infer these from historical implementation.

## 7. V1 contract structure

### 7.1 Inputs

- approved market sensors/discovery sources;
- Employer-Origin source/seed evidence;
- current exact vacancy evidence;
- approved target-profile/Candidate Facts;
- operator-approved base CV and application letter;
- approved product/ranking policy versions.

### 7.2 Processing behavior

- bounded market/company/job discovery;
- Employer-Origin resolution;
- exact vacancy currentness/detail verification;
- Bronze/Silver normalization and lineage;
- assessment bound to current detail evidence;
- capability fit and hard filtering;
- deterministic ranking under approved factors;
- uncertainty/missing-data handling;
- separation of discovery-only, rankable and recommendation-eligible jobs;
- source-grounded application-draft generation.

### 7.3 Operator output

- discovery and Employer-Origin status;
- current/actionable job queue;
- evidence/currentness/uncertainty;
- ranking components and reasons;
- bounded Top-5 recommendations;
- Application Workspace;
- reviewable CV/application-letter DOCX/PDF/ZIP artifacts.

### 7.4 Success metrics

Primary PRODUCT-RECOVERY-001 metric (`PD-082`):

- one normal observable flow;
- at least five **current Employer-Origin jobs satisfying all approved evidence/hard-filter/recommendation requirements including score >=70** in the acceptance campaign;
- no aggregator final action leakage;
- no known stale recommendation leakage;
- selected-job application documents that operator review judges to require only small edits.

General longer-term metrics still include:

- false-negative/false-positive behavior;
- freshness and evidence completeness;
- operator review effort;
- ranking usefulness;
- runtime reliability;
- application truthfulness/quality.

## 8. Current non-goals

Until PRODUCT-RECOVERY-001 stabilizes the core path:

- automatic application submission/send;
- quota filling with below-threshold jobs;
- treating aggregator-only evidence as confirmed Product/Application authority;
- weakening currentness/evidence gates to improve demo counts;
- broad new deterministic hardening without measurable product-recovery impact;
- productive ML expansion before the normal deterministic/current Product V1 path and feedback surface are stable;
- post-application feature expansion beyond retained backlog/contracts;
- cloud/Kafka/Spark expansion without demonstrated product value;
- application artifacts built from unapproved or invented facts;
- new demo-only orchestration as a substitute for the normal product flow.

## 9. Product Recovery delivery rule

A primary-path Product Recovery item is ready only when it states:

1. approved PRD/PD/PA anchors;
2. visible operator outcome;
3. which cold-to-application stage it improves;
4. technical validation plan;
5. operator/runtime proof boundary;
6. whether complexity is added, integrated or retired;
7. release-note impact when product-visible.

Safety/security/data-integrity and incident recovery may proceed independently when required.

## 10. Current checkpoint interpretation

`v0.1.0-demo.1` is a salvaged demo milestone, not a production-ready Product V1 declaration.

It proves valuable implementation capability and preserves the bug fixes learned during the demo window. It also documents the current limitation: the cold market-to-application journey still requires too much repair/operator choreography and application-document quality needs further iteration.

PRODUCT-RECOVERY-001 closes that gap; it does not rewrite the approved product contract to match the current implementation.
