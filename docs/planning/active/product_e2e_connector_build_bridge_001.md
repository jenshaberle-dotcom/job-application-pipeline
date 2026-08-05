# PRODUCT-E2E-CONNECTOR-BUILD-BRIDGE-001

Status: active implementation  
Issue: #390  
Authority: Product E2E portfolio planning through existing S6C build-request boundary

## Runtime evidence

After the exact Accompio CAND-001 Apply, the unchanged Product E2E Golden-Path
advanced the public-job-API case past `origin_url` and `origin_inventory`. The next
repeated cross-source blocker became `connector_build`:

- Accompio from `public_job_api_discovery`;
- adesso from `existing_origin_evidence`;
- Computacenter from `existing_origin_evidence`.

The Golden-Path classified these three cases as one `generic_cross_source_gap`.
The remaining 1&1 origin-URL gap and Clarios origin-inventory gap are local evidence
gaps and do not supersede the cross-source priority.

## Existing authority

S6C already owns connector-build evaluation and request persistence. It combines:

- candidate lifecycle state;
- employer-origin gate reviews;
- connector generation plans;
- false-negative learning pressure;
- the Gold connector-build candidate queue;
- local connector artifact existence.

S6C can create a reviewable `build_approval_required` record. It can generate
connector artifacts only after its separate explicit `--approve-build` boundary.
It cannot register connectors, activate sources, write Bronze jobs, change recurring
ingestion, change scheduling or create a pull request automatically.

The new bridge does not replace S6C. It binds the Product E2E portfolio to it.

## Transition

```text
current source-diverse Golden-Path portfolio
→ cases whose first blocker is connector_build
→ existing S6C evaluation with approval_provided=false
→ deterministic Product E2E classification
→ exact optional build-request persistence
→ separate later artifact-build approval
→ unchanged Golden-Path rerun
```

## Portfolio selection

The runner reconstructs the same bounded Golden-Path portfolio directly from
current DB seed and lifecycle state. It does not consume the previous JSON or
Markdown audit as pipeline input.

Company names and candidate IDs are evidence labels only. Selection and
classification do not contain company allowlists or employer-specific branches.

Only cases whose current first blocker is `connector_build` enter this bridge.

## Classification

The bridge preserves these outcomes:

- `passed / controlled_source_already_available`;
- `passed / connector_artifacts_present`;
- `operator_decision_required / connector_artifact_build_approval_required`;
- `valid_stop / gate_reassessment_required_before_build`;
- `valid_stop / origin_url_repair_required_before_build`;
- `valid_stop / origin_source_discovery_required_before_build`;
- `operator_decision_required / sample_job_review_required_before_build`;
- `operator_decision_required / manual_source_review_required_before_build`;
- `valid_stop / connector_build_evidence_insufficient`;
- fail-closed capability gaps for blocked, unexpected or unclassified states.

A dry-run never passes artifact approval to S6C. Encountering an
`artifact_generation_allowed` request in planning mode is therefore classified as
an authority mismatch rather than accepted silently.

## Build-request persistence

Dry-run is the default. Persisting a build request requires every target in the
exact form:

```text
candidate_id:company_key
```

and the exact token:

```text
approve_product_e2e_connector_build_request_persistence
```

A target is eligible only when current S6C evaluation returns:

- `build_status=build_approval_required`;
- `approval_required=true`;
- `approval_provided=false`;
- `artifact_generation_allowed=false`.

Persistence delegates to the existing S6C upsert. It creates or updates the single
candidate-bound build-request row and makes the operator decision visible through
`gold_candidate_lifecycle_status` and `gold_approval_queue`.

This approval does not authorize artifact generation. The later S6C
`--approve-build` action remains a separate operator decision.

## Boundary

The bridge has no authority for:

- provider or LLM requests;
- report, JSON, CSV or spreadsheet re-ingestion as truth;
- connector artifact generation during planning or request persistence;
- connector registration;
- source activation;
- Bronze, Silver or Gold job writes;
- scheduler or Wave mutation;
- Product assessment, ranking or Top-5 mutation;
- Candidate Fact or application-artifact mutation;
- automatic pull-request creation.

## Acceptance

- full Pipeline CI and React build pass;
- unit tests prove source-neutral classification;
- URL repair, sample review, gate reassessment and build approval remain distinct;
- exact target binding rejects candidate/key drift and duplicates;
- only a current `build_approval_required` request may be persisted;
- private DB-backed dry-run evaluates the fresh connector-build portfolio;
- any persistence is separately approved and verified as idempotent;
- artifact generation remains separately approved;
- the unchanged Golden-Path rerun chooses the next transition from fresh evidence.
