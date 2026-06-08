# Employer-Origin Connector Build Process

## Status

Accepted for project use after the controlled Finanz Informatik activation.

## Purpose

This document defines the standard process for evaluating, building and activating employer-origin career-site connectors.

The process is intentionally defensive. Constraints can be relaxed later when the project has stronger evidence, better automation and clearer operating boundaries. The first implementation principle remains:

> Start bounded, prove value, then expand deliberately.

## Why This Matters

Finanz Informatik is the first controlled employer-origin connector in the project. It is a milestone because it proves that employer-owned career sources can add source value without depending on broad aggregator ingestion.

This connector family changes the sourcing model:

- Aggregators remain useful for discovery and market signal exploration.
- Employer-origin sources provide controlled, high-precision source targets.
- A small number of relevant, incrementally unique jobs can be valuable.
- Source value must be evaluated by quality, uniqueness, risk and maintenance burden, not only volume.

The process in this document is designed to become agent-ready. A future AI agent should not receive a vague instruction such as "build a connector for company X". Instead, it should execute this gated process and stop at the first failed hard gate.

A documented stop is a valid outcome.

## Connector Family Definition

An employer-origin connector targets a company-owned or company-controlled career source.

Typical examples:

- a company career listing page
- a company-owned job board
- an ATS-backed page reachable through the employer domain
- a bounded employer-specific source target discovered through aggregators or Silver evidence

This is different from broad aggregators such as StepStone and from generic ATS family ingestion such as large Greenhouse or Personio exploration.

## Reference Implementation

The reference path is the Finanz Informatik controlled activation.

The relevant learning path was:

1. Employer signal appeared through existing sources.
2. The employer career source was manually identified and classified.
3. Reachability and source shape were inspected.
4. A bounded source-target spike was built.
5. Listing candidates were filtered by relevance and location/remote evidence.
6. Detail pages were probed only for a tiny candidate set.
7. Incremental uniqueness was compared against current DB evidence.
8. An activation gate was documented.
9. A bounded connector was added.
10. The connector was registered in the runner.
11. Bronze output was validated.
12. Silver relevance and canonicalization were adjusted.
13. Source-value semantics were updated from `unknown` to `employer_origin_career_site`.
14. The source was validated as a controlled source target, not as broad crawling.

## Process Overview

Every employer-origin candidate moves through the same gated process:

```text
Company Candidate
→ Source Discovery
→ Risk Gate
→ Technical Reachability Gate
→ Scope Gate
→ Defensive Preview Gate
→ Relevance Gate
→ Detail Evidence Gate
→ Incremental Uniqueness Gate
→ Connector Candidate Gate
→ Controlled Activation Gate
→ Bronze Validation
→ Silver Validation
→ Source Lifecycle Tracking
```

At each gate, the outcome must be one of:

- `continue`
- `defer`
- `manual_review_required`
- `abort_documented`
- `build_connector_candidate`
- `activate_controlled`
- `disable_or_deprecate`

## Gate 1: Company Candidate

### Goal

Identify a company that may justify employer-origin evaluation.

### Candidate Inputs

Acceptable signals include:

- repeated Silver evidence from existing sources
- aggregator matches for a target employer
- known local or remote-Germany employer relevance
- domain fit with the user's target profiles
- manually identified target companies

### Continue Criteria

Continue only if at least one meaningful signal exists.

### Stop Criteria

Stop if the company has no plausible target-domain, target-location or remote-Germany relevance.

## Gate 2: Source Discovery

### Goal

Find the employer-owned career/job source without broad crawling.

### Continue Criteria

Continue if there is a clear career listing or job-detail source.

### Stop Criteria

Abort or defer if discovery requires:

- login
- paid access
- broad crawling
- fragile browser automation
- unclear source ownership
- unclear usage boundaries

## Gate 3: Risk Gate

### Goal

Prevent risky, aggressive or unsuitable data acquisition.

This is a hard gate.

### Hard Stop Criteria

Abort if any of the following are required or observed:

- login-only access
- CAPTCHA or obvious bot-defense interaction
- browser automation as the only viable path
- aggressive pagination or crawling
- unclear terms or operational risk
- unstable access requiring repeated probing
- non-public job data
- source behavior that would likely create operational burden or legal uncertainty

### Continue Criteria

Continue only if bounded read-only probing appears defensible.

## Gate 4: Technical Reachability Gate

### Goal

Verify that the source is reachable with a small number of read-only requests.

### Expected Evidence

Capture:

- requested URL
- final URL
- status code
- response size
- title or source marker
- source family candidate
- potential ATS hints
- possible job-link signals

### Continue Criteria

Continue if the source is reachable and shows job-listing or job-detail signals.

### Stop Criteria

Stop or defer if the source is unreachable, unstable, login-gated or technically unclear.

## Gate 5: Scope Gate

### Goal

Define a bounded source target before any preview.

### Required Scope Definition

A source target must define:

- company key
- `source_name`
- source family
- source target
- requested URL
- location/remote target
- maximum listing pages
- maximum detail pages
- request timeout
- page-size boundary
- exclusion gates

Example:

```text
source_name: finanz_informatik:hannover
source_family: finanz_informatik
source_target: hannover
source_type: employer_origin_career_site
max_listing_pages: 1
max_detail_pages: 3
```

### Hard Stop Criteria

Do not continue if the only available approach is broad all-job ingestion.

## Gate 6: Defensive Preview Gate

### Goal

Fetch a tiny, bounded preview without writing to Bronze.

### Rules

- read-only
- no database writes
- no source activation
- no recurring ingestion
- no CSV/export-as-input handoff
- generated Markdown/JSON may be used as human-readable review output only

### Continue Criteria

Continue if the preview produces bounded candidate rows with inspectable evidence.

### Stop Criteria

Stop if preview output is too broad, unstable, irrelevant or only possible through aggressive access.

## Gate 7: Relevance Gate

### Goal

Filter candidates before any connector activation.

### Positive Signals

Relevant evidence may include:

- target roles
- target skills
- Hannover
- remote Germany
- domain fit
- meaningful Product Owner / Business Analyst / Data / BI / Software signals

### Exclusion Signals

Exclude or defer:

- Ausbildung
- duales Studium
- Praktikum
- Werkstudent
- trainee-only roles
- non-target locations without remote signal
- pure overview pages
- non-job pages
- unrelated domain roles

### Continue Criteria

Continue if there is at least one plausible target candidate.

Low volume is acceptable for employer-origin sources.

## Gate 8: Detail Evidence Gate

### Goal

Fetch detail pages only for the small candidate set that passed relevance gating.

### Rules

- detail fetches remain bounded
- only selected candidates are fetched
- no broad detail crawling
- no database writes
- detail evidence must support candidate interpretation

### Continue Criteria

Continue if detail pages confirm job identity and improve role/location/profile evidence.

## Gate 9: Incremental Uniqueness Gate

### Goal

Determine whether the employer-origin source adds value beyond already known sources.

### Key Principle

An employer-origin source does not need many jobs to be valuable.

One to three relevant and incrementally unique jobs can justify controlled activation when they add evidence not already available from existing sources.

### Required Comparison

Compare candidate jobs against current DB evidence, including:

- raw jobs
- Silver jobs
- title similarity
- company similarity
- source URL evidence
- location evidence
- profile evidence

### Outcomes

- `incrementally_unique_candidate`
- `possible_known_elsewhere_review`
- `known_duplicate_or_low_incremental_value`
- `manual_review_required`

### Continue Criteria

Continue if at least one candidate appears incrementally valuable or if manual review justifies a controlled preview.

## Gate 10: Connector Candidate Gate

### Goal

Decide whether connector code is justified.

### Continue Criteria

A connector candidate may be built only if:

- risk gate passed
- scope is bounded
- preview is stable enough
- relevance is present
- incremental value is plausible
- source semantics can be modeled cleanly
- tests can be written without network dependence

### Required Connector Properties

The connector must:

- preserve source evidence in Bronze
- expose deterministic external IDs where possible
- respect page-size and request boundaries
- filter locally across active search terms when server-side search is unavailable
- preserve matched terms
- preserve source family/target/type semantics
- avoid hidden local artifacts as inputs

## Gate 11: Controlled Activation Gate

### Goal

Activate the connector only as a bounded source target.

### Required Checks

Before activation:

- connector registered in ingestion CLI/runner
- DB profile migration is schema-compatible
- search terms are attached by DB relationships, not external artifacts
- source name is explicit and stable
- `source_type` is explicit, not `unknown`
- Bronze output is bounded
- Silver can interpret the source
- tests cover connector, migration, CLI and Silver behavior
- activation is documented
- recurring ingestion remains controlled

### Hard Stop Criteria

Do not activate if any of these remain unclear:

- connector requires broad crawling
- source risk is unresolved
- source profile migration is schema-blind
- Silver cannot interpret the data and this is not explicitly documented
- activation relies on CSV/Excel/export-as-input handoffs

## Gate 12: Bronze Validation

### Goal

Confirm raw persistence after activation.

### Required Evidence

Validate:

- source name
- raw job count
- newest fetched timestamp
- external IDs
- source URLs
- matched terms
- source family/target/type in raw evidence
- ingestion run status

### Continue Criteria

Continue only if Bronze output is bounded, explainable and source-specific.

## Gate 13: Silver Validation

### Goal

Confirm canonical interpretation.

### Required Evidence

Validate:

- Silver count for source
- canonical source type
- role/skill/accessibility evidence
- title/company/location mapping
- processing decisions
- skipped rows with reasons if applicable

### Continue Criteria

Continue only if Silver behavior is explainable.

A source may remain Bronze-only only if that is explicitly documented and accepted.

## Gate 14: Source Lifecycle Tracking

### Goal

Treat the source as a managed asset, not a one-time connector.

### Lifecycle States

Possible states:

- `candidate`
- `active_controlled`
- `watchlist`
- `degraded`
- `deprecated`
- `disabled`

### Ongoing Evaluation

Evaluate:

- incremental uniqueness
- relevance quality
- duplicate rate
- operational risk
- request stability
- parsing stability
- maintenance cost
- Silver/Gold value

## Agent-Ready Interpretation

A future AI agent must execute this process gate by gate.

The agent must stop at the first failed hard gate and produce a documented stop reason.

The agent must not:

- bypass gates
- activate sources directly without approval
- execute destructive operations
- depend on CSV/Excel/export artifacts as inputs
- broaden scope without explicit instruction
- use browser automation unless a later policy explicitly allows it
- convert human-readable review files into hidden pipeline state

Valid agent outputs are:

- documented stop PR
- source candidate review PR
- bounded preview PR
- connector candidate PR
- controlled activation PR

The preferred future architecture is DB-backed review state for candidates and gates. Markdown and JSON reports remain human-readable outputs only.

## Documentation Requirements Per Candidate

Every employer-origin candidate should document:

- company candidate
- source URL
- source family/target/type
- risk assessment
- scope boundaries
- preview result
- relevance result
- detail evidence result
- incremental uniqueness result
- activation decision
- stop reason if aborted
- known limitations
- follow-up decision

## Design Principle

The process is intentionally stricter than necessary at the beginning.

This protects the project from creating long-lived ingestion debt, cloud-migration problems, hidden local dependencies and brittle connector sprawl.

The project may loosen individual constraints later, but only after the corresponding risk is explicitly understood and documented.
