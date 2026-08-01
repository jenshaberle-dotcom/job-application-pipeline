# Product Decision Register

Status: active PRD-rebaseline input
Owner: Jens

This register prevents product behavior from being guessed by DON, implementation code or historical planning artifacts.

## Decision states

- `approved`
- `recorded_repo_truth_pending_confirmation`
- `open_operator_decision`
- `proposed`
- `rejected`
- `superseded`

## A. User and operating rhythm

| ID | Status | Decision required |
|---|---|---|
| `PD-001` | recorded_repo_truth_pending_confirmation | Confirm Jens as the sole V1 operator or identify additional users. |
| `PD-002` | open_operator_decision | Define the primary usage rhythm: daily, weekday-only, event-triggered or manual review cycles. |
| `PD-003` | open_operator_decision | Define the maximum acceptable operator review effort per cycle. |
| `PD-004` | open_operator_decision | Define the primary first screen and the information required before any drill-down. |

## B. Target profile

| ID | Status | Decision required |
|---|---|---|
| `PD-010` | approved | Canonical hierarchy: Machine Learning Engineer foundation; strong Data Engineering and data-centric ML focus; AI/Data & AI Reliability as future specialization; GenAI as cross-cutting competency rather than standalone target profile. |
| `PD-011` | approved | Primary families: Machine Learning Engineer, ML Engineer, MLOps Engineer, ML Platform Engineer, AI Platform Engineer and substantive AI Engineer roles. Strong bridge families: Data Engineer, Data Platform Engineer and Analytics Engineer. Strategic probes: AI/ML Reliability. |
| `PD-012` | approved | Seniority labels do not decide eligibility by themselves. Actual requirements and evidenced capability fit are authoritative. A Senior/Lead/Principal-labelled vacancy remains eligible when the requirements fit. A Junior-labelled vacancy with Senior/Lead/Principal-level requirements is excluded. Approved 2026-08-02. |
| `PD-013` | open_operator_decision | Define which adjacent roles are interesting but not primary Top-5 candidates. |
| `PD-014` | open_operator_decision | Define required and disqualifying technical/task content independent of job title. |

## C. Geography and working model

| ID | Status | Decision required |
|---|---|---|
| `PD-020` | approved | Hannover is the geographic center. Germany-based fully remote roles are also admissible. Regional roles remain eligible when realistically commutable. |
| `PD-021` | approved | Approximately 30 minutes commute per direction is ideal; up to approximately 45 minutes per direction is generally acceptable. Car and public transport are both valid modes. Good public-transport access is a preference, not a hard filter. |
| `PD-022` | approved | Hybrid, onsite and fully remote roles are all admissible. Hybrid wins as a preference when roles are otherwise professionally and strategically comparable. |
| `PD-023` | approved | Fully remote roles in Germany are valid candidates. Remote is not a hard downgrade; the hybrid preference acts only as a comparison signal between otherwise similar jobs. |
| `PD-024` | open_operator_decision | Define handling of unclear or contradictory location/remote evidence. |
| `PD-025` | open_operator_decision | Define treatment of occasional travel, customer-site and relocation requirements. |

## D. Employment and hard filters

| ID | Status | Decision required |
|---|---|---|
| `PD-030` | approved | Permanent employment is required for authoritative Top-5 eligibility. Explicit fixed-term, temporary, freelance, internship or trainee roles fail this hard filter. Missing contract evidence remains manual-review-required. Approved 2026-08-02. |
| `PD-031` | approved | German and English are the accepted working languages. A role requiring an additional language fails the language hard filter. Missing language evidence remains manual-review-required. Approved 2026-08-02. |
| `PD-032` | approved | Salary is a negotiable soft signal, not a hard exclusion. The current target is approximately EUR 75,000 gross/year. The operator's current compensation remains private local runtime context and is not committed to the public repository. Approved 2026-08-02. |
| `PD-033` | open_operator_decision | Define company, industry or role exclusions. |
| `PD-034` | approved | The acceptable weekly-hours range is 35 to 40 hours. A vacancy passes when its evidenced selectable range overlaps 35–40 hours. Missing hours evidence remains manual-review-required. Approved 2026-08-02. |
| `PD-035` | approved | Capability and requirements fit take precedence over the advertised seniority title. Senior-labelled roles may qualify when the actual requirements fit. Junior-labelled roles carrying Senior/Lead/Principal-level requirements are excluded. Unsupported capability requirements fail; missing evidence remains manual-review-required. Approved 2026-08-02. |

## E. Job truth, freshness and evidence

| ID | Status | Decision required |
|---|---|---|
| `PD-040` | open_operator_decision | Define the maximum acceptable age of a job posting. |
| `PD-041` | open_operator_decision | Define handling when publication date is unknown. |
| `PD-042` | open_operator_decision | Define the minimum evidence proving that a concrete job is still active. |
| `PD-043` | approved | A Top-5 job must be a current concrete vacancy validated on the employer origin source/seed or through an explicitly approved equivalent origin-evidence path. Aggregator evidence alone is discovery evidence, not final Top-5 confirmation. |
| `PD-044` | open_operator_decision | Define treatment outside Top 5 of aggregator-only jobs with strong detail evidence. |
| `PD-045` | open_operator_decision | Define when multiple URLs represent one job, one source family or distinct opportunities. |
| `PD-046` | open_operator_decision | Define how conflicting employer identity or entity evidence is shown and resolved. |

## F. Top-5 and ranking semantics

| ID | Status | Decision required |
|---|---|---|
| `PD-050` | approved | Top 5 means at most five jobs. The result is never filled with weaker, blocked or below-threshold jobs merely to reach five. Approved 2026-08-02. |
| `PD-051` | approved | Minimum overall quality is 70/100. Fewer than five jobs are valid when fewer jobs qualify. The threshold is an adjustable V1 starting value, not a permanent constant. Approved 2026-08-02. |
| `PD-052` | approved | Starting weights: profile/ML direction 40%, Reliability potential 25%, Data/Data-Engineering focus 20%, origin/evidence quality 15%. Jobs within 3 score points are otherwise comparable; only inside that window may hybrid, commute and public-transport preferences reorder them. The weights and delta remain versioned and adjustable. Approved 2026-08-02. |
| `PD-053` | approved | Hard-filter failures never enter the authoritative Top-5 queue. Unknown required hard-filter evidence remains review-required rather than silently passing or failing. Approved 2026-08-02. |
| `PD-054` | approved | Missing required evidence blocks authoritative ranking. Missing optional soft signals remain visible as uncertainty and do not become fabricated values. Approved 2026-08-02. |
| `PD-055` | approved | Each rank must expose score components, ranking reasons, uncertainties and relevant missing information. Approved 2026-08-02. |
| `PD-056` | approved | The UI shows rank, overall score, component scores, reasons and uncertainties together rather than a score without explanation. Approved 2026-08-02. |
| `PD-057` | open_operator_decision | Define deterministic versus LLM-assisted ranking boundaries. |
| `PD-058` | open_operator_decision | Define how ranking changes between cycles are explained. |

## G. Queue composition and lifecycle

| ID | Status | Decision required |
|---|---|---|
| `PD-060` | open_operator_decision | Define whether employers without a concrete active job appear outside the primary job queue. |
| `PD-061` | open_operator_decision | Define handling of jobs already viewed, saved, rejected, applied to or expired. |
| `PD-062` | open_operator_decision | Define resurfacing rules after material job or evidence changes. |
| `PD-063` | open_operator_decision | Define behavior when several jobs at one employer qualify. |
| `PD-064` | open_operator_decision | Define whether uncertain research candidates appear in a separate lane. |
| `PD-065` | open_operator_decision | Define review-state retention and history visible to the operator. |

## H. Operator actions and automation

| ID | Status | Decision required |
|---|---|---|
| `PD-070` | open_operator_decision | Approve V1 actions such as save, reject, inspect, mark applied, request refresh or park. |
| `PD-071` | approved | No automatic application submission. |
| `PD-072` | open_operator_decision | Define which actions require confirmation and which are reversible. |
| `PD-073` | open_operator_decision | Define which changes are proposals only versus direct bounded mutations. |
| `PD-074` | open_operator_decision | Define notification and reminder behavior. |
| `PD-075` | open_operator_decision | Define when provider/LLM calls may be triggered by the product workflow. |

## I. Product V1 and success

| ID | Status | Decision required |
|---|---|---|
| `PD-080` | open_operator_decision | Define the minimum end-to-end V1 journey across the approved product pillars. |
| `PD-081` | open_operator_decision | Define V1 UI/device expectations for the React Deep Ocean Intelligence Control Center. |
| `PD-082` | open_operator_decision | Define relevance and usefulness acceptance metrics. |
| `PD-083` | open_operator_decision | Define acceptable false-negative and false-positive behavior. |
| `PD-084` | open_operator_decision | Define freshness, evidence and runtime reliability targets. |
| `PD-085` | open_operator_decision | Define the operator acceptance campaign required before Product V1. |
| `PD-086` | open_operator_decision | Define explicit V1 non-goals to prevent scope expansion. |

## Decision protocol

For each open decision:

1. DON may present a small number of evidence-backed options and consequences.
2. Jens selects, modifies, postpones or rejects the options.
3. The accepted decision receives a date, rationale and affected requirement/scenario IDs.
4. Product, roadmap, backlog and tests are updated in the same or directly linked change.
5. Historical implementation that conflicts with the accepted decision becomes technical debt; it does not override the decision.
