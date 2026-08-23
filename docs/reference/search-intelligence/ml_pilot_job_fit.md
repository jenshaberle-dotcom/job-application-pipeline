# ML-PILOT-001 — Shadow Job Review Relevance Pilot

Status: **pilot design only — implementation blocked until MLF-005 live DB package proof passes**
Authority relationship: extends `ML-LEARN-001` and `BOOSTER-ADMISSION-001`; does not create ranking or product authority.

## Purpose

The first practical ML pilot should answer one narrow question:

> Given a canonical job and the approved target profile, how likely is this job to be worth operator review?

The pilot is deliberately not an application-decision model and not an interview/offer predictor. It produces a non-authoritative shadow signal that can be compared with the deterministic baseline and the existing bounded LLM booster.

ML-PILOT-001 is a **task-local ML booster experiment**, not the start of an ML stage that must run along the full pipeline. Other pipeline surfaces remain deterministic or use the existing LLM booster unless their own measured admission evidence shows incremental value for ML.

## Target

Initial target name: `operator_review_relevance`.

Only explicit, task-scoped operator labels may become supervised truth. Unlabeled jobs are excluded from supervised training and must not be silently treated as negatives.

Candidate positive feedback events for a future label contract include explicit `interesting`, `saved`, or `apply` decisions. Candidate negative feedback requires an explicit not-relevant/reject-for-review decision. The exact event mapping must be frozen in a later label-contract slice before training.

Application outcomes such as `interview`, `rejected_after_application`, and `offer` are separate targets and must not be mixed into this pilot label.

LLM annotations may later be included as provenance-marked weak semantic evidence, never as operator ground truth.

## Model ladder

The first experiment should compare three layers on the same leakage-controlled holdout:

1. **Deterministic baseline** — current generic evidence/features and hard criteria, with no learned component.
2. **Logistic regression** — transparent linear ML control model.
3. **LightGBM binary classifier** — first practical nonlinear candidate.

No model is allowed product authority during the pilot.

### Why logistic regression

Logistic regression is the control model because it is fast, deterministic under a fixed contract, easy to inspect, and establishes whether the supervised signal is learnable at all. If a more complex model cannot materially beat it, added complexity is not justified.

### Why LightGBM first

LightGBM is the preferred first practical candidate because the expected feature surface is heterogeneous tabular data with missing values and nonlinear interactions. It is efficient on CPU, works with modest training sets, exposes feature importance, supports SHAP-style explanation later, and provides a natural path toward a learning-to-rank variant if pairwise/ranking feedback becomes available.

The pilot does not require GPU execution. Kaggle may later be used for reproducible experiment execution only after the applicable provider gate is explicitly authorized.

## Initial deterministic feature families

The first feature contract should prefer features already derivable from DB-backed canonical evidence:

- role family;
- seniority;
- city/region and work model;
- publication age/freshness;
- source/evidence quality;
- requirement completeness;
- exact skill-match count and ratio;
- related-skill match count and ratio;
- transferable-capability count;
- credible learning-gap count;
- unsupported/unknown gap count;
- task/profile match evidence;
- role-similarity category;
- requirement count;
- missing-evidence indicators.

Hard product criteria remain outside model authority even when corresponding evidence is exposed as a feature.

Free text, embeddings, vector databases, transformer fine-tuning, and model-family-specific semantic infrastructure are intentionally excluded from the first pilot. They may be evaluated later only if the simpler baseline leaves a measured residual problem.

## Split and leakage rules

Before training, the pilot dataset must freeze a split contract that includes:

- time-based holdout so evaluation jobs are later than training jobs;
- duplicate/repost grouping across splits;
- no future operator/application/interview outcome in rank-time features;
- historical job evidence frozen at the applicable evidence cutoff;
- product/target-profile version bound to the dataset;
- employer concentration reported and, where useful, tested with an employer-held-out sensitivity split.

Later job revisions must not silently rewrite historical training examples.

## Evaluation

At minimum compare:

- precision and recall;
- PR-AUC when class balance makes it meaningful;
- calibration / Brier score;
- false-negative rescue versus deterministic baseline;
- top-k hit rate and NDCG when the shadow score is evaluated as an ordering signal;
- operator override/rejection rate once shadow review is available;
- inference latency and missing-feature rate.

The key pilot question is not whether LightGBM can fit the training data. It is whether it produces useful out-of-time lift beyond the strongest deterministic baseline and whether that lift remains explainable and operationally cheap.

## Booster admission relationship

`BOOSTER-ADMISSION-001` governs whether this surface is worth spending further ML effort on. The admission evidence must be task-local and must measure the residual after the deterministic baseline.

A positive admission result means only that offline/shadow evaluation is justified. It does not authorize training execution, Kaggle, GPU use, product scoring, ranking, Top-5 membership or application behavior.

The same admission framework may later evaluate other ML or LLM opportunities. A win on `job_review_relevance` does not activate ML on adjacent pipeline stages.

If several booster opportunities are admissible, the development order should follow expected incremental net value rather than pipeline position. This pilot is intended to be the first ML surface because it is expected to combine high repeatability, useful false-negative rescue and a path to explicit operator ground truth.

## First experiment flow

```text
DB-backed canonical jobs + explicit operator labels
-> frozen deterministic feature projection
-> leakage-controlled train/validation/test contract
-> immutable checksummed training package
-> CPU validation
-> deterministic baseline
-> logistic regression
-> LightGBM classifier
-> same-holdout comparison
-> shadow predictions only
-> operator review
```

A later combined ablation may compare deterministic + LLM, deterministic + ML, and routed deterministic + ML + conditional LLM residual behavior. LLM calls must remain separately measurable rather than being hidden inside the ML target.

## Admission gate

Pilot implementation and supervised label/split materialization must not start until the MLF-005 live read-only Silver package proof has passed and repository truth records that evidence.

Even after that gate, this pilot remains shadow-only. It cannot change Top-5 semantics, lifecycle state, source activation, connector behavior, hard eligibility, or application actions.
