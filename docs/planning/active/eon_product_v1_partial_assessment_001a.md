# E.ON Product V1 Partial Assessment 001A

Status: implementation for issue `#348`  
Boundary: exact E.ON pilot job only  
Input runtime identity: raw job `26342`, Silver job `466`, external job `eon_germany:1414903533`

## Product purpose

The controlled E.ON runtime execution proved the real path from one live
SuccessFactors vacancy through Bronze and Silver to the Product V1 readiness
state `assessment_required`.

This slice advances that exact job by persisting a deliberately incomplete,
source-grounded `job_product_assessments` row. It does not attempt to make the
job rankable. Missing evidence remains visible and blocking.

## Evidence accepted

The runner accepts only the already authorized E.ON pilot raw dataset and
verifies:

- exact raw and Silver IDs supplied by the operator;
- source `successfactors:eon_germany`;
- external job ID `eon_germany:1414903533`;
- exact `(Senior) Data Engineer Data & AI (f/m/d)` title;
- canonical ATS-backed employer-origin source type;
- explicit pilot authorization in raw JSON;
- zero provider requests in acquisition evidence;
- exact-job HTTP 200 detail observation;
- verified E.ON Digital Technology employer identity;
- explicit `Permanent` and `Full time` SuccessFactors metadata;
- approved and version-aligned Product V1 ranking and hard-filter policies.

## Persisted assessment facts

The bounded assessment records:

- origin validated;
- activity observed active through the fresh exact-job HTTP 200 evidence;
- permanent employment observed;
- Senior title marker observed;
- policy key and version;
- structured explanations and uncertainties.

## Deliberately unknown

The following values remain unknown because this slice has no sufficient
source-grounded evidence:

- required languages;
- numeric weekly hours;
- salary range;
- work model;
- commute and public-transport quality;
- requirements seniority;
- candidate capability fit;
- profile-direction, data-focus, reliability-focus and evidence-quality scores;
- overall ranking score.

The approved hard-filter policy therefore keeps the expected Product V1 state at
`hard_filter_decision_required`.

## Plan-only preflight

```bash
python -m scripts.run_eon_product_v1_partial_assessment \
  --raw-job-id 26342 \
  --silver-job-id 466
```

Plan-only mode performs DB reads and writes one review-only report. It performs
no network request and no DB mutation.

## One-shot Apply

```bash
python -m scripts.run_eon_product_v1_partial_assessment \
  --raw-job-id 26342 \
  --silver-job-id 466 \
  --assessed-by deterministic_eon_partial_product_v1 \
  --apply \
  --approval-token EON-PRODUCT-V1-ASSESSMENT-001
```

Apply acquires a transaction-scoped advisory lock and inserts at most one
assessment row. An exact existing row is accepted as an idempotent replay. Any
conflicting assessment fails closed.

## Expected result

```text
readiness_before: assessment_required
assessment_inserted: true
readiness_after: hard_filter_decision_required
```

A different post-assessment readiness aborts the transaction rather than
silently widening eligibility.

## Explicit non-goals

This slice does not:

- call a provider or LLM;
- call the network;
- activate a connector or scheduler;
- create additional Bronze or Silver rows;
- infer missing languages, hours, salary or capability fit;
- create any ranking score;
- force a Top-5 entry;
- generate or submit an application;
- create generic assessment autonomy for other jobs.
