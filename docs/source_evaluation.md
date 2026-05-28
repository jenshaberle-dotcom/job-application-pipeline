# Source Evaluation

## Purpose

The project intentionally evaluates multiple real-world job data sources instead of optimizing only for a single API.

The goal is not only to ingest job postings, but also to understand the architectural, operational and data-quality implications of different source types.

## Strategic Source Evaluation Principles

The project does not treat every available source as automatically valuable.

A source must justify its continued use through the additional value it provides compared with its operational, technical and legal or terms-of-service related risk.

The project therefore follows these principles:

1. Prefer official APIs and canonical employer or ATS sources where feasible.
2. Use commercial aggregation platforms primarily as discovery sources.
3. Do not build an alternative public job platform or mirror third-party job advertisements.
4. Do not republish complete third-party job advertisements.
5. Use controlled sampling for sensitive HTML sources.
6. Require explicit acquisition boundaries before expanding pagination or collection depth.
7. Evaluate risky or fragile sources with a Source Value Score before treating them as long-term strategic sources.
8. Downgrade, limit or remove sources whose incremental value does not justify their risk and maintenance cost.

Commercial aggregation platforms can be useful, but their value must be proven.

The long-term goal is not to maximize raw source count. The goal is to build a reliable, explainable and useful personal job-market intelligence system.

## Source Role Strategy

The project distinguishes source roles when evaluating acquisition strategy.

| Source role | Preferred usage | Canonical-source expectation |
|---|---|---|
| Official API source | Primary ingestion and stable market baseline | Strong canonical-source candidate |
| ATS or company-board source | Employer-near acquisition through company or ATS boards | Strong canonical-source candidate |
| Company career page | Employer-origin acquisition when technically and responsibly feasible | Strong canonical-source candidate |
| Commercial aggregator or job portal | Discovery, exploration, source-value comparison and candidate-source discovery | Not canonical by default |

Commercial aggregators can help discover relevant employers, roles and market signals.

They should not be treated as preferred canonical sources when an employer-origin, ATS or official source is available.

This distinction supports the long-term strategy of using commercial platforms defensively while preferring employer-near sources for canonical job evidence.

## Terminology Alignment

Source evaluations use the shared project terminology from `docs/glossary.md`, ADR-022, ADR-026, ADR-027 and ADR-028.

Observed provider-specific structures should be described as source signals and then mapped to canonical project concepts such as source family, source target, source type, connector, search intent, result card, detail page, external job ID, Bronze record and canonical job.

Source evaluation must not collapse these levels:

| Level | Meaning | Example |
|---|---|---|
| Source family | Provider or platform family | `personio`, `greenhouse`, `stepstone` |
| Source target | Concrete acquisition target within that family | `personio:eraneos`, `greenhouse:stripe` |
| Source type | Strategic role or classification | ATS board, commercial aggregator, official API |

This distinction is required for Source Value, Source Health and later employer-origin acquisition decisions.

The project therefore intentionally includes:

- structured APIs
- semi-structured APIs
- ATS-based career systems
- HTML-based job pages
- sources with different levels of data quality
- sources with different anti-bot behavior
- sources with different metadata completeness

This evaluation is important to avoid overfitting the architecture to the Bundesagentur für Arbeit API.

Source evaluation should happen before adding complex or operationally risky sources as production connectors.

---

## Evaluation Criteria

| Criterion | Description |
|---|---|
| Access Model | How the source can be accessed, for example public API, public JSON, ATS board, HTML pages or browser-like access |
| Access Complexity | Difficulty of accessing the source reliably |
| Filtering Capability | Degree to which the canonical search intent can be applied server-side |
| Data Structure | Structured vs semi-structured vs HTML |
| Data Completeness | Quality and completeness of available metadata |
| Identifier Quality | Availability and stability of external job identifiers |
| Publication Date Quality | Availability and reliability of publication or freshness metadata |
| Stability | Expected API, endpoint or page stability |
| Anti-Bot Risk | Probability of rate limits, blocking or bot detection |
| Pagination Complexity | Difficulty of traversing result pages |
| Detail Page Requirement | Whether additional page requests are needed |
| Canonical Mapping Difficulty | Difficulty of mapping source data to the Silver model |
| Heartbeat Feasibility | Whether a lightweight source heartbeat can be implemented |
| Maintenance Effort | Expected long-term connector maintenance effort |
| Portfolio Value | Architectural and learning value |
| Legal / Ethical Risk | Terms of service, scraping concerns and responsible-use considerations |

---

## Recommended Evaluation Flow

A new source should move through the following stages:

1. Documentation-only candidate
2. Source analysis
3. Limited technical spike
4. Production connector decision
5. Production connector implementation
6. Dashboard and monitoring integration

Commercial job portals and HTML-based sources should not skip the source analysis and spike stages.

---

## Current Sources

## Bundesagentur für Arbeit API

### Type

Structured public API

### Evaluation Summary

| Criterion | Assessment |
|---|---|
| Access Model | Public API |
| Filtering Capability | Strong |
| Identifier Quality | Stable |
| Publication Date Quality | Exact |
| Pagination Complexity | Low |
| Anti-Bot Risk | Low |
| Heartbeat Feasibility | Good |
| Maintenance Effort | Low |
| Portfolio Value | Medium |
| Legal / Ethical Risk | Low |

### Advantages

- Stable structured responses
- Official public interface
- Good initial Bronze-layer source
- Good for validating ingestion architecture
- Low anti-bot risk
- Reliable pagination
- Strong server-side filtering

### Challenges

- Limited realism compared to modern ATS systems
- German-market-specific structure
- Relatively clean and normalized data
- Lower transformation complexity

### Architectural Value

Useful as the first production-style Bronze ingestion source.

However, the project architecture should not become overly optimized for this source alone.

---

## Greenhouse

### Type

ATS / company-board source

### Evaluation Summary

| Criterion | Assessment |
|---|---|
| Access Model | ATS board |
| Filtering Capability | None in current implementation |
| Identifier Quality | Stable |
| Publication Date Quality | Missing |
| Pagination Complexity | Low for current board usage |
| Anti-Bot Risk | Low |
| Heartbeat Feasibility | Good through board metadata or lightweight board check |
| Maintenance Effort | Medium |
| Portfolio Value | High |
| Legal / Ethical Risk | Low |

### Advantages

- Widely used by technology companies
- More realistic modern recruiting workflow
- Structured but company-specific source behavior
- Good candidate for canonical normalization testing
- Useful for validating full-fetch plus local filtering behavior
- Employer-near source target model for later canonical-source evaluation

### Challenges

- Different company implementations
- Different field availability
- Limited or missing publication metadata
- Requires local filtering for search intent
- Potentially inconsistent metadata quality

### Architectural Value

Greenhouse introduces realistic ATS-style data while remaining manageable for iterative architecture development.

It validates that the connector architecture can handle sources that do not support canonical search intent server-side.

### Decision

Implemented.

Greenhouse boards should be treated as source targets within the Greenhouse source family, not as separate search profiles.

---

# Current Discovery and Candidate Sources

## StepStone

### Type

Commercial job platform

### Current Status

Limited result-card connector implemented. See `docs/source_analysis/stepstone.md`.

### Expected Advantages

- Large job market coverage
- Rich metadata
- Realistic aggregation platform
- High relevance for German job market exploration
- Good test case for commercial portal complexity

### Expected Challenges

- Anti-bot protections
- HTML parsing complexity
- Potential legal restrictions
- Dynamic content loading
- Higher maintenance effort
- Possible consent or blocking behavior
- Unknown identifier stability
- Unknown heartbeat feasibility

### Required Next Step

Do not expand StepStone into broad crawling.

Next steps should focus on:

- source-value evaluation
- search-quality analysis
- controlled source-target lineage
- canonical-source discovery from employer or ATS links where feasible
- maintaining explicit acquisition boundaries
- avoiding detail-page fetching and uncontrolled pagination

### Portfolio Value

High, if kept as a bounded discovery and aggregator source with clear documentation of constraints.

---

## Workday

### Type

Enterprise ATS platform

### Expected Advantages

- Very common in enterprise recruiting
- Highly realistic production scenario
- Good test for normalization boundaries
- Strong portfolio value due to real-world complexity

### Expected Challenges

- Complex page structures
- Dynamic requests
- Difficult navigation flows
- Potential anti-bot protections
- Often inconsistent implementations between companies
- Higher maintenance effort

### Portfolio Value

Very High

---

## Personio

### Type

ATS / company career system

### Current Status

Personio is technically integrated for selected public XML source targets.

The current implementation supports Bronze ingestion, Silver normalization and controlled Batch 1 source-target evaluation.

Personio has not yet passed source-value validation. Its continued expansion depends on whether Batch 1 contributes measurable additional jobs, companies or canonical candidates compared with Bundesagentur, Greenhouse and StepStone.

### Expected Advantages

- Common in European companies
- Useful for small and medium-sized company job boards
- Good complement to Greenhouse and Workday

### Expected Challenges

- Company-specific configuration differences
- Potentially inconsistent metadata
- Limited search capabilities
- May require local filtering

### Portfolio Value

Medium to High

---

## Lever

### Type

ATS job board

### Expected Advantages

- Common in technology companies
- Similar architectural category to Greenhouse
- Useful for validating reusable ATS connector patterns

### Expected Challenges

- Board-specific differences
- Limited filtering
- Potential metadata gaps

### Portfolio Value

Medium to High

---

## Company Career Pages

### Type

Direct company websites

### Expected Advantages

- Highly realistic
- Diverse structures
- Good test for connector abstraction
- Good test for canonical modeling
- Can provide original employer-side job postings

### Expected Challenges

- No standardized structure
- High implementation variability
- Potential scraping instability
- Requires source-specific logic
- Requires careful legal and ethical assessment

### Portfolio Value

Very High

---

## Current Direction

The project currently has four active source categories:

- search-capable public API
- full-fetch ATS board
- controlled public XML ATS/company-board targets
- limited commercial aggregator discovery source

The next source expansion should use controlled source targets, evaluate source value, and avoid mixing source family, source target and source type in one ambiguous analytical level.

Commercial platforms such as StepStone should remain bounded discovery sources unless source-value analysis justifies continued controlled use.

The goal is to validate:

- connector abstraction quality
- Silver-layer boundaries
- canonical model assumptions
- normalization flexibility
- handling of incomplete or inconsistent data
- operational risk assessment
- heartbeat feasibility
- responsible source usage

Learning architectural differences between source types is more important than maximizing ingestion volume.

## Block D Source Value Findings

Block D moved the project from simple source expansion toward source-value evaluation.

The main finding is that raw acquisition volume is not sufficient to evaluate a source. A source must be evaluated by the number of jobs fetched before filtering, the number of jobs matched after local search-intent filtering, the number of jobs reaching Silver, company diversity, canonical candidate diversity, overlap with other sources and the ability to confirm known jobs at employer-origin sources.

### Personio Batch 1

Personio confirmed that source targets without server-side keyword search should not be queried once per search term.

The better pattern is:

- fetch one source target once
- match locally against all active search terms
- preserve or display matched terms
- record one ingestion run per source target

This reduces duplicate run semantics and makes source-target value easier to evaluate.

### Greenhouse Search Intent

Greenhouse showed that full-board volume can be misleading.

A large board snapshot can look valuable by raw volume, but its source value is much lower when only a small subset matches the active search intent. For Greenhouse-style boards, the project should distinguish:

- fetched jobs before filtering
- matched jobs after filtering
- Silver jobs
- distinct companies
- distinct canonical candidates
- cross-source overlap

This prevents treating broad board snapshots as high-value source evidence.

### Employer-Origin Evidence Validation

Employer-origin validation should not only ask whether a career site is reachable.

The stronger question is:

- A job is already known from Bronze or Silver.
- Can the employer-origin source confirm that exact job?

If the job is confirmed at the employer source, it becomes stronger evidence for the canonical job candidate.

If the job is not confirmed, the result is still useful and may indicate:

- expired or no longer visible job
- parser or source-target gap
- vocabulary gap
- aggregator-only posting
- manual review needed

### Current Evidence Classification

Initial origin evidence validation produced the following interpretation:

- Rossmann: origin evidence confirmed for at least one known Data Engineer-style job. This indicates that the earlier landing-page smoke was too coarse and that the origin source needs better target/result-page handling.
- Finanz Informatik: origin evidence confirmed for Data Integration & Governance-style roles. This indicates a likely vocabulary gap around terms such as Data Integration, Governance, Analytics and Reporting.
- WERTGARANTIE: origin evidence confirmed for Analytics & Audience Manager. This weakens the aggregator-only hypothesis for that specific known job, but the source still needs cautious evaluation.
- HDI: Tech & Data and Data role families are clearly present, but exact known-job confirmation still needs manual or better target-specific validation. This is currently a manual-review or parser-target-gap case, not evidence that no relevant jobs exist.

### Block D Conclusion

Block D confirms that the project needs source-value metrics before broad expansion.

Good candidate metrics are:

- fetched_jobs_before_filter
- matched_jobs_after_filter
- matched_rate_pct
- silver_jobs
- distinct_companies
- distinct_candidate_keys
- cross_source_overlap
- new_companies
- origin_confirmed_jobs
- parser_or_target_gap_candidates
- vocabulary_gap_candidates
- aggregator_only_candidates

The next implementation step should not be a dashboard yet.

The next implementation step should be to persist enough acquisition and matching evidence so these metrics can be computed reliably instead of being inferred from ad-hoc script output.

## Future Source Lifecycle and Connector Recommendation Logic

Source Value is not a static property of a source.

A source may be valuable during one period and lose value later because of changing job availability, degraded data quality, increased duplicate rates, technical instability, changed acquisition rules, operational limits, legal risk or increasing maintenance cost.

Therefore, source evaluation must be treated as a lifecycle process, not as a one-time connector-build decision.

Future source evaluation should support both:

- evaluating new source candidates before connector implementation
- continuously evaluating existing active sources after implementation

The intended lifecycle logic is:

- discover a potential source candidate from Bronze, Silver or source-value analysis
- evaluate the candidate defensively
- estimate source value, risk and implementation complexity
- produce a recommendation
- let a human decide whether to build, limit, pause, deprecate or disable a connector

The system should not automatically create or remove connectors.

Potential future recommendation or lifecycle states include:

- `candidate`
- `under_evaluation`
- `connector_candidate`
- `active`
- `active_limited`
- `manual_watch`
- `paused`
- `deprecated`
- `disabled`
- `do_not_build`

Hard gates should override scoring.

Examples of hard gates are:

- high legal or operational risk
- unclear or problematic acquisition conditions
- login, authentication bypass or non-defensive access requirements
- persistent technical failures
- blocking or rate-limit signals
- no defensible acquisition policy

A source with high risk should not become a connector candidate only because it exposes many jobs.

Source-value scoring should consider at least:

- relevant jobs after filtering
- Silver jobs
- distinct companies
- distinct canonical candidates
- cross-source overlap
- origin-confirmed jobs
- new jobs or new companies contributed
- duplicate rate
- matched rate
- failure rate
- operational risk
- legal risk
- maintenance cost
- strategic relevance for the target search domain

Below defined thresholds, or when hard gates fail, a source may be limited, moved to watchlist, paused, deprecated, disabled or excluded from connector consideration.

Persisted source-value metrics are required because source quality and source risk can only be evaluated meaningfully over time.

This is the conceptual foundation for future source lifecycle decisions and connector recommendation logic.

### Source-Value Snapshot Window Semantics

Initial source-value snapshots may use the complete currently available local history.

This is useful as a baseline, but it must not be treated as a stable lifecycle score.

Historic totals can be distorted by earlier connector semantics, old search-term behavior, local test runs or one-time exploration spikes.

Future source-value snapshots should therefore support explicit evaluation windows, for example:

- `--window-hours 24`
- `--window-days 7`
- `--window-days 30`

The first G1 implementation is a read-only preview over persisted snapshots:

```bash
python -m scripts.preview_source_value_windows --window-hours 24
python -m scripts.preview_source_value_windows --window-days 7
python -m scripts.preview_source_value_windows --window-days 30
python -m scripts.preview_source_value_windows --all-default-windows
```

This preview uses SQL window functions over `source_value_snapshots`. It does not create Gold views, lifecycle scores or recommendations yet.

The preview also reports explicit trend-maturity fields:

- `requested_window_hours`
- `observed_window_hours`
- `observed_window_coverage_pct`
- `trend_maturity`
- `interpretation_warning`

These fields prevent 24h, 7d or 30d windows from looking more mature than the available snapshot history supports.

For example, if only two snapshots exist inside a 30d window, the row is a mechanics preview and not a lifecycle decision signal.

Lifecycle decisions should be based on mature windowed trends, not only on all-time cumulative totals or immature preview windows.

Examples:

- a source may have high all-time volume but low current matched value
- a source may have been reliable historically but start failing recently
- a source may have many old duplicates but still provide new current employer-origin evidence
- a source may have low total volume but high value in a specific recent window

The current all-time snapshot should therefore be interpreted as an initial historical baseline.

Future lifecycle decisions such as `active_limited`, `manual_watch`, `paused`, `deprecated` or `do_not_build` should use explicit time windows and trends.

### Trend-Eligible Metric Boundary

Windowed source-value output is not one single signal. Different metrics answer different questions.

The project therefore separates trend interpretation into metric classes:

| Metric family | Interpretation | Default trend status |
|---|---|---|
| `silver_jobs_delta` | New canonical evidence created by the pipeline. | Stronger value signal when transformation coverage and source coverage are stable. |
| `raw_jobs_delta` | New unique Bronze hot-store records. | Support signal; not standalone market growth evidence. |
| `matched_jobs_after_filter_delta` | Source activity, repeated matching or post-filter throughput. | Activity signal; not automatically new market value. |
| `duplicate_rate_delta_pct` | Duplicate pressure, overlap and source/pipeline behavior. | Source-quality signal; not market growth evidence. |
| `failure_rate_delta_pct` | Operational reliability and source health. | Health trend signal; not job-market value. |
| `latest_lifecycle_state` / `latest_recommendation` | Current source lifecycle interpretation. | Decision support only after mature windows and coverage context. |
| all-time raw totals | Historical baseline. | Not a Gold trend without burden and retention interpretation. |

This distinction is important before Gold views and dashboards. A technically valid 7d delta may still be only a source-activity signal. It should not be presented as market movement unless the metric, window maturity and source coverage all support that interpretation.

### Source-Coverage Change Boundary

A window can change because the market changed, but it can also change because the observed source universe changed.

The project therefore treats the following as coverage-affecting events:

- adding a new source
- adding a new source target, for example another Greenhouse board or Personio feed
- removing, pausing or deprecating a source target
- materially changing active search terms
- materially changing local post-fetch filtering
- changing source-family, source-target or lineage semantics
- excluding or removing historical burden from the hot store

Coverage-affected windows are still useful, but they must be interpreted as pipeline/source-coverage movement, not as pure market movement.

This boundary is especially relevant before controlled source expansion. Adding several targeted Greenhouse or Personio boards may increase `raw_jobs_delta`, `matched_jobs_after_filter_delta` or even `silver_jobs_delta`. That increase is valuable, but it is not automatically evidence that the market itself grew.

Controlled source expansion should therefore happen before serious Gold/dashboard interpretation, while the first windows after expansion remain explicitly marked as coverage-affected or analytically immature.

See also ADR-030.


### Current Source Coverage Baseline

Before expanding additional source targets, the project records a current source-coverage baseline in `docs/source_analysis/source_coverage_baseline.md`.

The baseline establishes that the current system has four active connector/source families and eight active search profiles/source targets:

- Bundesagentur
- Greenhouse
- StepStone
- Personio

Important baseline caveats:

- `greenhouse:stripe` contains substantial historical burden and must not be read as clean market volume.
- Bundesagentur was the first source and has a time/tenure advantage; it also has 10 early raw rows without run/profile lineage from the bootstrap phase.
- StepStone intentionally fetches one complete result page of 25 entries and does not perform full-fetch acquisition due to defensive risk assessment.
- Personio currently has low volume but provides employer-near ATS signals.
- `ingestion_runs`, `raw_jobs`, `silver_jobs` and `source_value_snapshots` answer different questions and must not be blindly equated.

This baseline must be considered before comparing source-value trends or selecting new targets for controlled expansion.


### Source Target Selection Matrix

Controlled source coverage expansion now uses a documented selection matrix before new targets are activated.

See `docs/source_analysis/source_target_selection_matrix.md`.

The first S1 expansion should remain intentionally small:

```text
2-3 Greenhouse boards
1-2 Personio/ATS or employer-origin boards
optionally 1 highly relevant employer-specific board
```

The matrix separates active targets, candidates, manual-review cases, parser gaps, reserves and watchlist sources. This prevents HDI, Rossmann, Finanz Informatik or WERTGARANTIE from being rediscovered ad hoc and prevents new Greenhouse boards from being added as uncontrolled raw-volume sources.

### Defensive Greenhouse Board Validation

Before activating additional Greenhouse boards, the project validates selected board candidates with `scripts.validate_greenhouse_board_candidates`.

The validation step is intentionally read-only:

- one boards API request per selected Greenhouse board token
- no database writes
- no profile activation
- no detail-page fetching
- local matching against the current Data Engineering search-term set

The default validation set contains the two primary Greenhouse Batch 1 candidates, `contentful` and `commercetools`. The reserve candidate `celonis` must be included explicitly.

Validation output is activation evidence, not long-term source value evidence. Source value still requires scheduled ingestion, source-value snapshots, Silver processing and review after several runs.

### S1D Controlled Contentful Activation

S1D activates `greenhouse:contentful` as the first controlled Greenhouse expansion target after defensive validation.

Validation evidence used for the decision:

| Board | Status | Total jobs | Matching jobs | Decision |
|---|---|---:|---:|---|
| `contentful` | reachable | 89 | 2 | Activate as first controlled Greenhouse expansion target. |
| `commercetools` | reachable | 11 | 0 | Do not activate now. |
| `celonis` | reachable | 189 | 1 | Keep as reserve. |

The activation is intentionally limited to one company board. The first 24h/7d/30d windows after activation are `coverage_changed` and must not be interpreted as pure market movement.

After the first Contentful runs, the next strategic step is a source strategy review before additional expansion. That review should reassess Greenhouse and Personio value for Hannover or remote-in-Germany relevance and evaluate aggregators such as LinkedIn, XING, Indeed and Glassdoor as a separate discovery-oriented source family.

See `docs/source_analysis/source_strategy_review.md` for the S2 boundary.

S2B adds the aggregator-specific assessment in `docs/source_analysis/aggregator_discovery_assessment.md`. The current decision is that LinkedIn, XING, Indeed and Glassdoor are discovery sources first, not direct automated ingestion sources. They may inform employer/source-target selection and false-negative analysis, but they should not be used as uncontrolled Bronze volume sources.

Until S2 selects the next source move, additional Greenhouse, Personio, employer-origin or aggregator targets should not be activated only because an existing connector or source pattern is available.


## Historical Burden Analysis Before Windowed Trends

Historical source-value metrics must be interpreted before implementing window functions or lifecycle trend views.

Window functions over distorted history can produce technically correct but misleading trend signals.

Known historical distortion candidates include:

- broad Greenhouse board snapshots before refined local filtering semantics
- wildcard or exploratory runs
- commercial aggregator history with high duplicate pressure
- local test data and missing-lineage records
- runs created before search-term and source-target semantics stabilized

The project therefore treats Historical Burden Analysis as a required bridge between persisted source-value snapshots and future Gold trend views.

The current read-only baseline script is:

```bash
python -m scripts.analyze_historical_burden --limit 30
```

The script is intentionally diagnostic only. It identifies review candidates and burden categories, but it does not delete, archive or reclassify records.

Important interpretation boundaries:

- Bronze remains tolerant and raw-first.
- False positives in Bronze are acceptable when they preserve evidence and reduce false negatives.
- Historical records should not be deleted only because they are noisy.
- Cleanup candidates must be separated from retention and archival policy decisions.
- Source lifecycle decisions should wait for explicit 24h, 7d or 30d window semantics.

Initial review categories may include:

| Category | Meaning |
|---|---|
| `ordinary_operational_history` | Normal historical evidence that should remain available for analysis. |
| `commercial_aggregator_history` | Aggregator-derived history that may be valuable for discovery but risky as canonical market signal. |
| `greenhouse_without_current_matching_metadata` | Older broad-board Greenhouse records without current local matching evidence. |
| `greenhouse_legacy_wildcard` | Wildcard or broad Greenhouse runs that can inflate volume and duplicate metrics. |
| `personio_without_current_matching_metadata` | Records from early Personio semantics that may need re-interpretation after local multi-term matching. |
| `missing_lineage` | Records without sufficient profile or run lineage, often created by tests or early manual exploration. |

These categories are not deletion rules.

They prepare the later H2 Cleanup / Retention Strategy, where the project can decide whether specific historical subsets should remain operational, be excluded from trend scoring, be archived, or be removed from local development data.

## Cleanup and Retention Strategy

Historical Burden Analysis does not directly produce deletion rules.

The project follows ADR-029 and treats cleanup as a retention and trend-eligibility decision.

Important separation:

- retained evidence is data that remains useful for audit, debugging or historical source analysis
- trend-eligible evidence is data that may safely contribute to future 24h, 7d or 30d lifecycle metrics
- archive candidates are valuable or explanatory but operationally noisy records that may later move out of the hot database
- `archive_before_hot_store_removal_candidate` is the preferred review track for historical noise that should be exported and documented before any cloud hot-store migration
- deletion candidates are limited to clearly transient, test or invalid records after explicit review

Default interpretation for current burden categories:

| Category | Default retention interpretation |
|---|---|
| `ordinary_operational_history` | Keep and allow for future trend use when lineage is sufficient. |
| `commercial_aggregator_history` | Treat as `archive_before_hot_store_removal_candidate` unless rows provide Silver-backed evidence; exclude from employer-origin trend scoring by default. |
| `greenhouse_without_current_matching_metadata` | Treat as `archive_before_hot_store_removal_candidate` unless rows provide Silver-backed evidence; keep locally for H2 review/export, but do not migrate blindly into a cloud hot store. |
| `greenhouse_legacy_wildcard` | Treat as `archive_before_hot_store_removal_candidate` unless rows provide Silver-backed evidence; this is legacy broad-match history, not a current trend signal. |
| `personio_without_current_matching_metadata` | Review after local multi-term semantics; keep until source-target value is understood. |
| `missing_lineage` | Review manually; exclude from trend scoring and consider test/transient cleanup if origin is clear. |

This keeps Bronze raw-first while preventing old exploratory history from distorting future lifecycle scoring.

### Current H2 Retention Review Semantics

The dry-run retention review workflow classifies records into review tracks rather than cleanup commands.

The intended tracks are:

| Review track | Meaning | Default next step |
|---|---|---|
| `retain_as_silver_evidence` | Raw row has Silver-backed evidence. | Keep in the operational database. |
| `retain_operational_history` | Normal operational history with sufficient current relevance. | Keep in the operational database unless a later policy changes. |
| `archive_before_hot_store_removal_candidate` | Historical burden with explanatory or archival value, but low long-term hot-store value. | Export, document, exclude from Trend/Gold calculations, and review before cloud hot-store migration. |
| `delete_candidate_after_review` | Clearly transient, test or invalid data after explicit review. | Delete only through explicit reviewed cleanup workflow. |

This distinction is important for legacy `greenhouse:stripe` history. The project does not classify all Greenhouse data as noise. Greenhouse rows with Silver evidence remain retained evidence. The historical burden concern is limited to old full-fetch or wildcard rows without Silver evidence.

The project story should preserve the learning value: early broad Greenhouse ingestion created volume and helped expose the difference between data volume and data value. That lesson is valuable. The individual noisy raw rows, however, do not automatically deserve long-term operational cloud hot-store retention once the review and export evidence exists.

See also `docs/source_analysis/historical_burden.md`.

### Archive Export and Hot-Store Removal Dry-Run

The H2 workflow now includes two additional safety steps after retention review:

```bash
python -m scripts.export_historical_burden_archive --export-dir exports/historical_burden_archive
python -m scripts.prepare_historical_burden_hot_store_removal --archive-dir exports/historical_burden_archive --export-dir exports/historical_burden_hot_store_removal_review
```

The archive export preserves the rows classified as `archive_before_hot_store_removal_candidate` in local JSONL/CSV/manifest artifacts. The hot-store removal dry-run then validates the archive and produces a review list of rows that would be eligible for a future explicit removal command.

Current result:

| Metric | Value |
|---|---:|
| Archived rows | 752 |
| `greenhouse:stripe` archived rows | 589 |
| `stepstone` archived rows | 163 |
| Silver-backed rows in archive | 0 |
| Dry-run eligible rows | 752 |
| Dry-run blocked rows | 0 |

This does not authorize deletion. It documents that the project can preserve explanatory evidence while avoiding long-term cloud hot-store retention for historical burden without Silver-backed value.


### Guarded Hot-Store Removal Command

The project now has a guarded command for historical-burden hot-store removal planning:

```bash
python -m scripts.remove_historical_burden_from_hot_store --review-dir exports/historical_burden_hot_store_removal_review --output-dir exports/historical_burden_hot_store_removal_execution
```

This command defaults to dry-run mode and writes an execution plan plus manifest. In dry-run mode it must report `database_cleanup_action: none` and `executed_removal: false`.

The current dry-run plan produced:

| Metric | Value |
|---|---:|
| Planned candidates | 752 |
| Eligible now | 752 |
| Blocked now | 0 |
| `greenhouse:stripe` candidates | 589 |
| `stepstone` candidates | 163 |

Execute mode is intentionally not a normal command path. It requires all of these confirmations:

- `--execute`
- `--confirm-retention-track archive_before_hot_store_removal_candidate`
- `--confirm-candidate-count 752`
- `--confirm-candidates-sha256 <validated-removal-candidates-csv-sha256>`
- `--confirm-cleanup-action remove_archived_historical_burden_from_hot_store`
- `--allow-source greenhouse:stripe`
- `--allow-source stepstone`

The exact source allow-list is part of the safety model. The command should fail if candidate sources differ from the reviewed source set.

This command is not the cleanup path for `delete_candidate_after_review` rows. Test/transient cleanup should be designed separately, because deleting true test data is a different policy from removing already archived historical burden from a hot operational store.

### Reviewed Test/Transient Cleanup

Reviewed test/transient cleanup is intentionally separate from historical-burden hot-store removal.

The cleanup workflow targets only rows classified as:

```text
delete_candidate_after_review
```

The first local execute run removed exactly two reviewed test/transient `raw_jobs` rows from sources `manual_test` and `test`.

Current result:

| Metric | Value |
|---|---:|
| Candidate rows before execute | 2 |
| Eligible rows before execute | 2 |
| Blocked rows before execute | 0 |
| Deleted `raw_jobs` rows | 2 |
| Deleted `job_observations` rows | 0 |
| Deleted `silver_processing_decisions` rows | 0 |
| Remaining cleanup candidates after execute | 0 |

This cleanup does not change the treatment of historical burden rows. The 752 `archive_before_hot_store_removal_candidate` rows remain governed by the archive/export and guarded hot-store-removal workflow.

The distinction is part of the source-value safety model: true test/transient rows can be removed after explicit review, while historically noisy but explanatory source records must be archived, documented and reviewed before any hot-store removal.
