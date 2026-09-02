# DEMO-001 generic Product V1 assessment materialization

Status: implementation qualification
Parent: #707

## Runtime evidence

The qualified Eraneos / 1KOMMA5° live cohort currently has 15 Silver jobs,
11 current `active_confirmed` jobs, seven role-relevant current jobs and zero
cohort Top-5 jobs. All 11 current jobs are at `assessment_required`; the next
shared product gate is Product V1 assessment materialization.

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

After merge, run a plan against the two already-qualified live sources with
`--role-relevant-only`. Only if the plan is unblocked may the explicit Apply be
considered. Fresh cohort status after Apply determines the next real gate; this
document does not predict or force hard-filter/ranking success.
