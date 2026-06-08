# Search Intelligence Cycle Audit

Status: S7E foundation audit  
Scope: current Search Intelligence loop, agent responsibilities, database touchpoints and scheduler boundary  
Boundary: documentation only; no source activation, no Bronze writes, no scheduler change, no connector registration and no search-profile mutation

---

## 1. Current Components

The project now has a Search Intelligence loop that is broader than a crawler. It combines bounded market observation, company and term learning, candidate lifecycle evaluation, explicit approval gates and dashboard-ready Gold read models.

Current component groups:

| Component group | Purpose | Current role |
| --- | --- | --- |
| Aggregator discovery / novelty | Observe bounded market signals from exploration sources and classify whether companies or terms are new, repeated or saturated. | Market signal input and novelty pressure. |
| Company vocabulary | Preserve observed company and skill vocabulary without directly mutating search profiles. | Learning substrate for market and profile alignment. |
| Search-term value | Estimate whether observed terms are useful for the candidate profile and current market. | Search strategy intelligence input. |
| False-negative / FN pressure | Identify unresolved candidates or terms that may indicate missed relevant market coverage. | Prioritization pressure, not proof of missed jobs. |
| Employer-origin candidates | Track discovered companies as possible origin sources. | Candidate lifecycle backbone. |
| Origin Source Discovery Gate | Select or stop on plausible HTTPS employer-origin domains before connector feasibility. | Anti-black-magic URL/source selection gate. |
| Connector generation / build approval | Plan and, only after explicit approval, generate bounded connector artifacts. | Controlled build path. |
| Gold Search Intelligence views | Consolidate operational metrics into dashboard-ready read models. | UI and reporting contract. |
| Control Center UI | Local operational view for health, lifecycle, approvals, gaps, jobs and demo chain. | Human review and demo surface. |

---

## 2. Agent Inventory

Current and near-current agents/scripts in the Search Intelligence chain:

| Agent / script | Reads from | Writes to | Boundary |
| --- | --- | --- | --- |
| `run_aggregator_novelty_loop_agent.py` | Market evidence, existing candidates, vocabulary/search-term state | Aggregator novelty snapshots/items | No source activation, no Bronze writes, no search-profile mutation. |
| `run_search_term_value_agent.py` / related search-term agents | Candidate profile, company vocabulary, suggestions | Search-term value/confidence/suggestion tables | No automatic search-profile mutation. |
| `run_employer_origin_connector_generation_foundation_agent.py` | Employer-origin candidates and gate evidence | Connector-generation plans | Planning only; no connector registration or activation. |
| `run_approval_gated_connector_build_agent.py` | Candidate lifecycle, generation plans, approval state | Build request state and optionally connector artifact files after explicit approval | No auto-PR, no registration, no activation, no Bronze write. |
| `run_origin_source_discovery_gate_agent.py` | Candidate evidence URLs and known source signals | Origin-source discovery alternatives/review state | No browsing by default; stops on ambiguity; no activation. |
| `preview_gold_search_intelligence_metrics.py` | Gold views | None | Read-only smoke/preview. |
| `run_search_intelligence_control_center.py` | Gold views and approval/build state | Only bounded approval action when write-enabled and token-confirmed | No auto-PR, no activation, no Bronze write, no scheduler change. |

The important architectural distinction is that agents produce evidence, classifications and review states. They do not silently mutate the production ingestion surface.

---

## 3. DB Write/Read Map

### Primary write-side state

| Table family | Purpose |
| --- | --- |
| `aggregator_novelty_snapshots`, `aggregator_novelty_items` | Novelty and saturation observations from bounded exploration sources. |
| `company_vocabulary_observations` | Company/skill/vocabulary observations from market evidence. |
| `search_term_suggestions`, `search_term_confidence_snapshots`, `search_term_validation_runs`, `search_term_value_scores` | Search-term learning, validation and value scoring. |
| `false_negative_risk_snapshots` | FN pressure and unresolved market-coverage pressure. |
| `employer_origin_source_candidates` | Candidate company/source lifecycle. |
| `employer_origin_candidate_gate_events`, `employer_origin_candidate_gate_reviews` | Gate evidence and manual/review decisions. |
| `employer_origin_connector_generation_plans` | Connector-generation feasibility and recommendation state. |
| `employer_origin_connector_build_requests` | Explicit build approval queue and build-request lifecycle. |
| Origin Source Discovery Gate tables | Candidate origin URL/domain alternatives, selected source decisions and manual-review blockers. |

### Read-side / serving state

| View | Purpose |
| --- | --- |
| `gold_market_coverage_summary` | One-row market coverage and pressure summary for dashboard KPIs. |
| `gold_candidate_lifecycle_status` | Candidate lifecycle state, gate progress, blocker and next action. |
| `gold_approval_queue` | Human-actionable approval queue. |
| `gold_source_health_summary` | Controlled-source health and source contribution summary. |

Rule: UI and demo reporting should prefer Gold views over raw agent tables whenever the information is product-facing.

---

## 4. Gold View Map

The Gold layer is currently the boundary between agent internals and the Control Center UI.

| Product question | Gold view |
| --- | --- |
| How many origin connectors are active? | `gold_market_coverage_summary` |
| Which candidates are blocked, open or ready for approval? | `gold_candidate_lifecycle_status` and `gold_approval_queue` |
| Is FN pressure high or critical? | `gold_market_coverage_summary`, candidate lifecycle rows |
| Which source/candidate needs action next? | `gold_candidate_lifecycle_status.next_action` |
| What should appear in the approval tab? | `gold_approval_queue` |
| Is a controlled source healthy? | `gold_source_health_summary` |

Known limitation: the current Gold foundation covers market coverage and connector lifecycle first. Jobs/application drafts and capability-gap dashboards need their own Gold read models before the UI should become more detailed there.

---

## 5. Current Manual Cycle

The current workflow is controlled and mostly manual between steps:

1. Run bounded source ingestion / exploration.
2. Persist raw evidence and market observations.
3. Run Search Intelligence agents for novelty, vocabulary, search-term value and FN pressure.
4. Review candidate lifecycle and Gold metrics.
5. Run Origin Source Discovery Gate for selected candidates.
6. If a plausible origin source exists, run connector generation planning.
7. If the candidate has enough pressure but still needs manual authorization, approve connector artifact build explicitly.
8. Review generated connector artifacts in a separate branch/PR.
9. Keep registration and activation as separate future gates.

This is safe, but it is operationally fragmented. The same cycle should become one orchestrated intelligence run with explicit boundaries.

---

## 6. Proposed Nightly Intelligence Cycle

Proposed S7F direction: one nightly intelligence orchestrator that reads the latest ingestion/market state and advances only review-safe intelligence state.

Suggested order:

1. Validate database/migration readiness.
2. Read latest bounded exploration and source states.
3. Run novelty/saturation analysis.
4. Update company vocabulary observations.
5. Recompute search-term value/confidence snapshots.
6. Recompute FN pressure / candidate reassessment pressure.
7. Run Origin Source Discovery Gate for candidates without a selected origin source, but stop on ambiguity.
8. Generate or refresh connector-generation plans for candidates that passed origin-source discovery.
9. Update approval queue state for build requests that require human approval.
10. Refresh/read Gold views and emit one operator summary.

Allowed outputs:

- DB-backed review state
- dashboard-ready Gold reads
- human-readable summary
- explicit next actions

Blocked outputs:

- source activation
- connector registration
- Bronze writes caused by the intelligence cycle
- scheduler mutation
- auto-PR
- permanent search-profile mutation

---

## 7. Scheduler Boundary

The scheduler should not become a hidden decision-maker.

Recommended split:

| Scheduler action | Allowed? | Rationale |
| --- | --- | --- |
| Run normal ingestion profiles | Yes | Existing pipeline responsibility. |
| Run nightly Search Intelligence read/review cycle | Yes, after S7F | Converts existing data into review state. |
| Register connectors | No | Requires explicit gate and review. |
| Activate sources | No | Production surface change. |
| Write Bronze from newly generated connectors | No | Requires registration/activation first. |
| Change search profiles automatically | No | Needs separate reviewed strategy-adaptation gate. |
| Create PRs automatically | No | Keep branch/review workflow explicit. |

The scheduler may prepare recommendations. It must not silently expand data acquisition behavior.

---

## 8. Risk Controls

Key controls that should remain non-negotiable:

- HTTPS-only origin candidates.
- Reject or manually review aggregator URLs pretending to be employer-origin URLs.
- Stop on ambiguous multiple plausible domains.
- Preserve evidence URLs and reasons for every origin-source decision.
- Keep connector artifact build separate from registration and activation.
- Keep generated connector artifacts reviewable in connector-specific branches.
- Keep Gold views read-only and dashboard-oriented.
- Do not use CSV/Excel/export artifacts as pipeline inputs.
- No hidden scheduler side effects.
- No cloud-cost-relevant broad exploration without explicit defensive limits.

Worst-case failures this design tries to prevent:

- building a connector for the wrong domain,
- accidentally scraping an aggregator as if it were an origin source,
- activating an unreviewed connector,
- letting nightly automation mutate search profiles or source activation,
- turning generated artifacts into unreviewed production code,
- hiding pipeline decisions in local files or manual console-only steps.

---

## 9. Known Gaps

Known gaps before this becomes a mature end-to-end product loop:

1. Origin Source Discovery Gate needs broader real-candidate validation beyond HDI and Finanz Informatik.
2. The Control Center still needs a stronger UI layout and better visual information density.
3. Gap Analysis tab needs Gold-backed capability-gap serving models.
4. Jobs & Applications tab needs Gold-backed job ranking and application-draft workflow models.
5. The nightly intelligence orchestrator is not yet implemented as one reproducible cycle.
6. Approval UX is currently token-based; a later UI confirmation/dialog pattern would be more ergonomic while preserving explicit approval.
7. Connector build artifacts are generated but not yet integrated into a full reviewed connector-specific PR flow.
8. Registration and activation gates remain intentionally separate future work.
9. Scheduler integration must be designed carefully to avoid redundant or hidden side effects.
10. Demo storytelling is good in concept, but visual polish is still behind the quality of the standalone infographic.

---

## 10. Next Implementation Blocks

Recommended sequence:

### S7F — Nightly Search Intelligence Orchestrator

Create a single bounded orchestrator that runs the review-safe intelligence cycle and emits a clear operator summary.

Must include:

- deterministic run order,
- idempotent/re-run-safe behavior,
- clear DB read/write map,
- no source activation,
- no Bronze writes,
- no scheduler mutation,
- no auto-PR.

### S7G — Origin Source Discovery Real-Candidate Validation

Run the Origin Source Discovery Gate across all active/open employer-origin candidates and document outcomes.

Must include:

- candidate-by-candidate decision summary,
- ambiguous URL/domain handling,
- aggregator URL rejection/manual-review behavior,
- fallback when no credible origin URL exists.

### S7H — Gold Gap & Jobs Serving Models

Add Gold views for:

- capability gaps,
- market-demand terms,
- newly arrived ranked jobs,
- review-ready application draft queue.

### S7I — Control Center UI Polish Round

Only after the serving models exist, improve UI layout and visuals so function and visualization grow from the same data contracts.

---

## Demo Framing

This is the intended story:

> The project is not a crawler. It is a gated market-intelligence product. It observes bounded market signals, learns companies and vocabulary, identifies coverage pressure, discovers plausible origin sources, proposes connector builds and requires explicit approval before anything can become production ingestion behavior.

