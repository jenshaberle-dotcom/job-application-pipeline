# BOOSTER-ADMISSION-001 — Task-Specific Booster Admission

Status: implementation contract for side-effect-free admission evidence  
Scope: Search Intelligence ML and LLM booster opportunities  
Authority: does not activate provider execution, training, ranking, Top-5, lifecycle or application behavior

## 1. Purpose

ML and LLM capabilities are optional **boosters**, not mandatory stages in one universal pipeline chain.

The system should first identify a bounded decision surface where the deterministic baseline leaves a measured residual and where an additional learned or semantic capability has a credible chance of producing material incremental value.

The architecture is therefore:

```text
bounded decision surface
-> deterministic baseline
-> measured residual
-> task-specific booster admission evidence
     -> no booster when expected value is weak or evidence is immature
     -> ML shadow candidate when repeated learnable patterns justify it
     -> LLM shadow candidate when semantic/novel residuals justify it
-> separate evaluation and promotion ladder
-> deterministic/product authority remains outside the booster
```

This explicitly replaces any interpretation that `deterministic -> ML -> LLM` or `deterministic -> LLM -> ML` must run along the entire application pipeline.

## 2. Design principle

The pipeline does not search for places to insert ML or LLM merely because those capabilities exist.

Instead:

> Find expensive, weak, repetitive or semantically difficult decisions, measure the residual after the strongest deterministic baseline, then admit only the booster family with credible incremental value for that specific surface.

Different surfaces may therefore have different winners:

| Surface type | Likely first booster family |
|---|---|
| recurring job-review relevance | ML when explicit labels and volume exist |
| recurring ranking inside an approved candidate set | ML / learning-to-rank after label evidence |
| unusual ATS or source semantics | LLM |
| novel external-information gap | search/LLM path where applicable |
| hard eligibility / product contract | no probabilistic authority; deterministic only |
| one-off edge-case adjudication | LLM proposal followed by deterministic validation |

The table is a planning heuristic, not runtime activation.

## 3. Admission evidence

`src/search_intelligence/booster_admission.py` evaluates one booster family on one explicit `surface_id`.

Required planning evidence includes:

- a measured deterministic baseline;
- decision volume;
- deterministic residual rate;
- expected rescue rate;
- value per rescued case;
- incremental variable cost per escalated residual case;
- fixed validation/operational setup cost;
- problem-family fit;
- evidence quality;
- repeatability;
- operational risk;
- grounded evaluation readiness;
- observability readiness;
- an explicit authority boundary.

Expected value is deliberately calculated only over the **measured residual population**, not over every job or every pipeline step:

```text
expected escalated cases
  = decision volume × deterministic residual rate

expected rescues
  = expected escalated cases × expected rescue rate

expected gross value
  = expected rescues × expected value per rescue

expected net value
  = expected gross value
    - escalated cases × incremental cost per escalated case
    - fixed validation cost
```

The policy thresholds are inputs owned by the caller/operator/product contract. The module does not invent universal business thresholds.

## 4. ML-specific admission

ML needs stronger repeatability and volume evidence because a trained model creates feature, label, training, drift and artifact-operational surfaces.

In addition to the common admission evidence, ML admission applies policy thresholds for:

- minimum repeatability;
- minimum decision volume.

This means a high-value but highly novel/rare surface can still be rejected as an ML opportunity while remaining a credible LLM opportunity.

A supervised ML surface also needs grounded evaluation evidence. For `ML-PILOT-001`, explicit task-scoped operator labels are the intended ground truth; current deterministic scores must not be relabeled as human preference truth.

## 5. LLM-specific admission

LLM opportunities use the same baseline/residual/value/observability/authority discipline, but do not inherit the ML minimum-volume or repeatability gates.

That preserves the existing strength of `LLM-BOOST-001` on sparse, novel or semantically difficult cases.

Existing provider, budget, search-first, cache and deterministic-validation rules remain authoritative. BOOSTER-ADMISSION-001 does not bypass them and does not call a provider.

## 6. Shadow-only result

A positive admission result means only:

> this surface is worth collecting offline/shadow booster evidence under the applicable family-specific contract.

It never means:

- execute a provider call;
- start Kaggle;
- allocate CPU/GPU training compute;
- promote a model;
- change a score or rank;
- alter Top-5 membership;
- mutate a lifecycle state;
- activate a source/connector;
- generate or send an application;
- claim product authority.

The code enforces `execution_authorized=false` and `product_authority=false` in every admission decision.

## 7. Candidate prioritization

Multiple admitted surfaces are ranked by expected net value, not by their physical position in the pipeline.

This gives the intended development strategy:

```text
measure several bounded residuals
-> admit viable ML/LLM opportunities
-> rank by expected incremental value
-> implement/evaluate the strongest opportunity first
-> keep the rest dormant
```

An upstream or downstream surface does not receive priority merely because another booster exists nearby.

## 8. Promotion remains separate

Admission and promotion are different decisions.

A recommended general ladder is:

```text
admission evidence
-> offline fixtures / reproducible evaluation
-> shadow
-> bounded canary
-> controlled default for that surface only
```

Every transition needs its own measured evidence. A booster promoted on one surface does not become globally enabled elsewhere.

For ML, model training/external compute remains separately governed by `ML-KAGGLE-001` and the explicit operator GPU boundary.

For LLM, provider execution remains separately governed by `LLM-BOOST-001`, surface-specific economics and existing provider budgets.

## 9. First ML value surface

The first planned ML opportunity remains `ML-PILOT-001`:

```text
surface: job_review_relevance
question: how likely is this canonical job to be worth operator review?
```

This is intentionally selected because it is expected to combine:

- high recurring volume;
- repeated comparable decisions;
- direct opportunity value from false-negative rescue;
- an understandable deterministic baseline;
- a path to explicit operator ground truth;
- cheap CPU inference;
- later extension into ranking if the evidence supports it.

The initial model ladder remains:

```text
deterministic baseline
-> logistic regression control
-> LightGBM candidate
-> same out-of-time / duplicate-safe holdout
-> shadow comparison
```

This does **not** authorize training while the MLF-005 live read-only package proof remains open.

## 10. Re-entry truth

For any future booster surface, repository re-entry should record at least:

- `surface_id`;
- booster family;
- baseline contract/version;
- measured residual definition and time window;
- admission-policy version/thresholds;
- expected-value inputs and result;
- evaluation dataset/fixture identity;
- current promotion stage;
- last evidence fingerprint;
- explicit execution/product-authority flags;
- sole next safe action.

This keeps booster development reproducible and prevents a new chat, runner or workflow from inferring capability activation from stale narrative state.
