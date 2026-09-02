# DEMO-001 generic Product V1 assessment materialization

Status: implementation qualification
Parent: #707

## Runtime evidence

The qualified Eraneos / 1KOMMA5° live cohort has now demonstrated that title-only
role preselection is useful for inspection priority but is too strict for Product
V1 admission. Current Employer-Origin jobs may carry relevant ML, Data Engineering
or Reliability evidence in the vacancy detail even when the title is generic
(`Platform Engineer`, `Software Engineer`, `Solution Engineer`, and similar).

For this product the loss function is intentionally recall-first: a false negative
before deterministic detail assessment is more costly than a false positive that
later capability, hard-filter and ranking stages can reject safely.

## Reused contracts

This slice deliberately reuses rather than reimplements:

- active + recurring search-profile source-role authority;
- `gold_job_lifecycle_health` current vacancy authority;
- migration-097 per-sighting `job_observations.normalized_evidence`;
- reviewed Personio complete-inventory authority from migration 099;
- the source-neutral deterministic Product V1 assessment evidence extractor;
- the existing bounded public-HTTPS detail fetch boundary;
- the E.ON pilot's useful writer mechanics: plan first, approval-gated Apply,
  advisory lock, conflict refusal and atomic Product V1 insertion.

The E.ON company binding is not reused.

## Authority composition

An initial assessment may be proposed only when all of the following are true:

1. an existing active recurring profile binds the source to role
   `employer_origin`;
2. the current Product V1/lifecycle projection is `active_confirmed` through an
   authoritative employer-origin observation reason and authoritative coverage;
3. the latest persisted normalized observation evidence exact-binds the same
   Silver vacancy URL and identifies employer-origin source evidence;
4. current detail text is fetched from the exact authorized vacancy origin;
   cross-origin redirects fail closed.

The Personio feed contract explicitly remains `product_authority=false`. It is
one input to the above composition, never sufficient authority by itself.

## Recall-first role boundary

Role relevance is not an authority gate. For current Employer-Origin vacancies
that already satisfy the authority composition above, default Product V1
materialization must remain recall-first and assess every `assessment_required`
row in scope.

`--role-relevant-only` is a precision-oriented inspection/diagnostic option. It
uses the title classifier to reduce a review set and may therefore create false
negatives. It must not be used as the canonical Demo/Product admission boundary.

The safe ordering is:

`current Employer-Origin -> deterministic detail assessment -> capability fit -> hard filter -> ranking`

not:

`current Employer-Origin -> title-only role filter -> detail assessment`.

Title classification remains useful as a priority/sorting signal and may be
broadened independently, but an absent title signal alone must not discard a
current authoritative vacancy before detail assessment.

## Materialized fields

The source-neutral extractor may populate only explicit vacancy evidence:

- employment type;
- required languages;
- weekly hours;
- work model;
- title seniority;
- requirements seniority.

The initial Product V1 row records the already-proven origin/current-vacancy
composition and leaves these boundaries unresolved unless later authoritative
input exists:

- capability fit: `unknown`;
- salary: `unknown`;
- all ranking component scores: `NULL`;
- overall score: `NULL`;
- hard-filter status remains derived by the canonical read model.

Exact evidence references and compact authority/evidence hashes are retained;
raw detail HTML is not persisted.

## Mutation boundary

Default mode is plan-only. Apply requires the exact explicit token
`PRODUCT-V1-ASSESSMENT-MATERIALIZE`, rechecks the same eligibility set and policy
version inside one transaction, takes per-job advisory locks and is insert-only.
Conflicting existing assessments fail closed. No source/profile activation,
provider/LLM request, ranking/Top-5 forcing or application/submission action is
performed.

## Demo acceptance

Run the plan against the already-qualified live Employer-Origin sources without
`--role-relevant-only`. The plan may include false positives; that is expected
and safer than suppressing plausible ML/Data/Reliability transitions before
current vacancy detail is assessed. Only unblocked proposals may proceed to the
explicit Apply step. Fresh cohort status after Apply determines the next real
gate; this document does not predict or force capability, hard-filter or ranking
success.
