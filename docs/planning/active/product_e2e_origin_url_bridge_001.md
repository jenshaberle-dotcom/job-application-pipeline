# PRODUCT-E2E-ORIGIN-URL-BRIDGE-001

Status: active implementation  
Issue: #388  
Authority: bounded origin discovery plus existing CAND-001 persistence boundary

## Runtime evidence

The generic Product V1 Golden-Path audit selected five real employers from three
source classes. The earliest repeated blocker occurred for both an aggregator
candidate (`1&1`) and a public-job-API candidate (`accompio GmbH`): each reusable
origin candidate existed, but `candidate_url` was unresolved.

The discovery-candidate ingress intentionally creates this state. CAND-001 already
owns validated URL planning, explicit persistence and audit recording. The missing
capability is therefore a source-neutral orchestration bridge, not another URL
finder or writer.

## Transition

```text
DB-backed discovery candidate
→ explicit discovery provenance check
→ bounded provider-free origin repair
→ existing CAND-001 plan
→ exact operator-approved CAND-001 Apply
→ unchanged Product E2E Golden-Path rerun
```

## Candidate selection

The bridge reads candidates directly from `employer_origin_source_candidates`.
The normal dry-run scans only candidates created by `PRODUCT-E2E-INGRESS-001` and
parses the persisted `discovery_source_class` marker from their notes. It initially
supports:

- `aggregator_company_discovery`;
- `public_job_api_discovery`.

It never derives provenance from the company name, URL, brand or source family.
Missing provenance is a capability gap. Other source classes keep their existing
lifecycle and return a valid stop.

The default portfolio selection is bounded to five candidates and prefers at
least one candidate from each supported source class when current DB state permits.

## Origin discovery

The bridge delegates to the mandatory staged origin-repair runtime already used by
CAND-001. For this slice:

- Tavily is explicitly disabled;
- LLM adjudication is explicitly disabled;
- no search-result export can be supplied;
- only the existing bounded ordinary HTTP probe and stored DB evidence are used;
- ambiguous results fail closed.

## Persistence

The bridge never writes `candidate_url` itself. The only writer remains CAND-001,
including its current URL conflict protection, A/B-tier evidence requirement,
transactional audit review and active-source protection.

Dry-run is the default. Apply requires every target in the exact form:

```text
candidate_id:company_key
```

and the exact token:

```text
approve_product_e2e_origin_url_persistence
```

The candidate ID and normalized company key must match current DB state. A replay
against an already-persisted URL is a no-action pass and creates no duplicate URL
transition.

## Classification

The bridge keeps these outcomes distinct:

- `passed` — URL already persisted or CAND-001 Apply completed;
- `operator_decision_required` — validated URL ready for explicit Apply or
  materially ambiguous evidence;
- `valid_stop` — no actionable bounded origin evidence or source class outside
  this bridge;
- `capability_gap` — missing provenance, identity or unclassified CAND-001 state;
- `not_reached` — selected target did not reach CAND-001 execution.

Operational command failures remain exceptions and must be classified before any
retry.

## Prohibited effects

The bridge has no authority for:

- company or URL allowlists;
- company-specific control flow;
- provider or LLM requests;
- report/JSON/CSV re-ingestion as truth;
- gate mutation beyond the existing CAND-001 persistence audit;
- connector generation, registration or source activation;
- Wave or scheduler mutation;
- Bronze, Silver, Gold, Product V1 assessment, ranking or Top-5 mutation;
- Candidate Fact creation or capability-fit inference.

## Acceptance

- full Pipeline CI and React build pass;
- unit tests prove equal behavior for aggregator and public-job-API candidates;
- provenance cannot be inferred from company identity;
- dry-run chooses a bounded source-diverse DB-backed portfolio;
- Apply requires exact ID/key targets and the exact approval token;
- persistence is delegated only to CAND-001;
- private runtime dry-run includes at least one supported case from each available
  source class;
- the unchanged Product E2E Golden-Path audit is rerun after any approved Apply;
- the next priority is bound to the earliest fresh cross-source blocker.
