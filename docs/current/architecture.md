# Current System Architecture

Status: current truth  
Active product track: **PRODUCT-RECOVERY-001 / issue #783**

## Architecture in one sentence

The system separates broad market discovery from Employer-Origin product authority, moves verified current vacancies through Bronze/Silver and evidence-backed Product V1 gates, then exposes ranked recommendations and review-only application preparation through the React Control Center.

```text
Discovery plane
  -> Employer-Origin authority plane
  -> Bronze/Silver data plane
  -> assessment / hard-filter / ranking decision plane
  -> Control Center
  -> Application preparation plane
  -> Release / operator-proof plane
```

## Product-value flow

```text
Market Sensors / Aggregators
  -> employer/job discovery evidence
  -> Employer-Origin resolution
  -> exact current vacancy verification
  -> Bronze observation
  -> Silver canonical job
  -> Product assessment
  -> capability-fit evidence
  -> hard filters
  -> deterministic ranking
  -> Top-5 threshold policy
  -> Application Workspace
  -> CV + letter DOCX/PDF/ZIP draft_for_review
```

The current architecture contains all of these capabilities, but PRODUCT-RECOVERY-001 exists because they are not yet connected into one reliable normal cold-to-application execution path.

## Authority boundaries

| Boundary | Current rule |
|---|---|
| Discovery vs action | BA, StepStone, GuteJobs and other aggregators are discovery evidence; they are not final application/action URLs. |
| Discovery provenance vs resolved origin | Historical `source_name/source_url` may identify how a job was found. Product action authority must use separately verified Employer-Origin vacancy truth. |
| Currentness vs historical observation | A historical Bronze/Silver sighting does not prove the vacancy is still active. Current/actionable/recommended state requires fresh evidence. |
| Rankable vs recommended | Rankable means ranking evidence is complete. Top-5 additionally requires the approved recommendation policy, including the 70/100 threshold. |
| Candidate facts vs generated prose | Candidate Facts are factual authority. Provider-generated prose is a proposal constrained by Candidate Facts and exact vacancy evidence. |
| Provider vs product authority | Provider success never grants ranking, approval, submission or send authority. |
| CI vs runtime truth | CI proves repository contracts. Local PostgreSQL, live employer HTTP and private document/provider behavior require operator-side proof. |
| Repair tooling vs normal product path | Demo/refill/recovery runners are diagnostic/recovery tools, not the desired steady-state architecture. |
| Release vs commit history | GitHub Releases are product-facing checkpoints. Commit history remains engineering detail. |

## Main architecture areas

### 1. Discovery plane

Market sensors and aggregators maximize useful recall under bounded acquisition rules. Their job is to reveal employers, search spaces and job candidates.

Discovery includes sources such as BA and StepStone, but those sources are intentionally **not** final Product/Application authority.

### 2. Employer-Origin authority plane

Candidate/origin discovery resolves a market observation to an employer-controlled source or explicitly approved equivalent origin-evidence path.

Important current invariant:

```text
aggregator discovered != employer-origin verified
```

A job may legitimately carry aggregator discovery provenance while also having a later resolved Employer-Origin vacancy. The two truths must remain separate and must not be collapsed back into one ambiguous URL field.

### 3. Current vacancy verification

Exact vacancy truth is checked before Product recommendation/application authority. Current implementation includes exact-detail HTTP checks, closure markers and detail fingerprints.

When live detail differs from the assessment snapshot:

```text
detail drift
  -> audited assessment refresh
  -> capability/ranking evidence invalidated as required
  -> normal gates rerun
```

A stale detail fingerprint must never be silently reused as current ranking evidence.

### 4. Bronze and Silver data plane

- **Bronze** retains bounded raw observations and lineage.
- **Silver** provides canonical job representation, normalization and quality state.

Historical acquisition truth is intentionally retained even when a vacancy later becomes inactive. Product-current truth must therefore not be inferred from Silver existence alone.

### 5. Product V1 assessment and ranking plane

The Product V1 decision chain is:

```text
initial assessment
-> capability fit
-> hard filters
-> ranking components
-> rankable
-> recommendation threshold / Top-5 projection
```

Hard filters include approved employment, language, weekly-hours and capability/seniority semantics. Missing required evidence remains review-required.

`rankable` is not synonymous with `recommended`. The approved Top-5 policy is at most five jobs and currently requires overall score >= 70/100.

### 6. React Control Center

The React Control Center is the reference operator UI. It currently provides product truth, review-scope jobs, source status, data-layer observability, ranking/application surfaces and evidence drill-down.

DEMO-001 hardened the frontend runtime by removing duplicated Product Truth fetch/normalization work and pathological persistent DOM observation.

The UI must distinguish presentation-only review affinity from authoritative Product V1 ranking.

### 7. Application preparation plane

Application Workspace combines:

- approved private base CV and base application letter;
- Candidate Facts;
- exact current vacancy evidence;
- provider-backed structured drafting when explicitly requested;
- evidence-first deterministic fallback;
- local DOCX/PDF/ZIP export.

Outputs remain `draft_for_review`. There is no automatic submission or send path.

### 8. Observability and data-layer metrics

The Data Layers surface exposes Bronze/Silver/Gold inventory, flow, coverage, freshness and source contribution without creating product authority.

Observability must explain the pipeline; it may not manufacture missing job/ranking state.

### 9. Release and operator-proof plane

Product checkpoints are represented as GitHub Releases with:

- semantic version/tag;
- release notes grouped around visible features and bug fixes;
- known limitations;
- exact repository CI/re-entry proof;
- separately labeled operator proof for local runtime facts.

`v0.1.0-demo.1` is the first salvaged product checkpoint.

## Current integration debt

DEMO-001 proved that the largest remaining risk is **integration debt**, not absence of components.

Current recovery targets:

1. **Truth propagation** — resolved Employer-Origin/currentness truth must flow consistently into Product read models and action URLs.
2. **One orchestration path** — normal operation must replace the current sequence of scout/refill/integrity/evidence-close helpers.
3. **Rankable throughput** — normal daily execution must produce enough fully assessed jobs without manual repair campaigns.
4. **Recommendation quality** — five recommended jobs must satisfy the approved threshold naturally; quota filling is forbidden.
5. **Application quality** — exported CV/letter must preserve coherent document structure and require only small human edits.
6. **Complexity reduction** — overlapping runners, views, policies and recovery surfaces that do not support the product-value path should be consolidated or retired.

## Current maturity statement

The architecture is no longer accurately described as only a discovery/connector system. It now spans discovery through application preparation and release management.

At the same time, it is **not yet a closed-loop product**: a cold `market discovery -> application package` run still needs too much operator/recovery intervention. PRODUCT-RECOVERY-001 makes closing that gap the primary architecture objective.

Detailed contracts live under `docs/reference/`. Current diagrams live in `system-diagrams.md`.
