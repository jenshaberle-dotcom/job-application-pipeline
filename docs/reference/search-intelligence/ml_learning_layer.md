# ML-LEARN-001 — Model-Agnostic Learning Layer

Status: **concept / architecture option — no model or runtime promotion approved**  
Scope: future Search Intelligence learning capability  
Relationship: complements deterministic generics and `LLM-BOOST-001`; does not replace product authority

## 1. Purpose

ML-LEARN-001 defines a future learning layer for the Job Application Pipeline without selecting a model family, framework or serving implementation.

The objective is to learn from structured job evidence and operator outcomes where generic deterministic logic and the bounded LLM booster stop delivering enough incremental value.

The intended order is:

```text
DB-backed source truth
-> deterministic normalization and generic evidence/features
-> deterministic baseline decisions and scores
-> bounded LLM booster where semantic ambiguity remains
-> optional ML learning layer for learned signals
-> deterministic/product-contract validation
-> Gold explanations and operator review
```

This concept intentionally preserves the current project philosophy:

- generics first;
- learned complexity only where measured lift justifies it;
- no hidden model authority;
- no model selection before the problem and evaluation contract are stable;
- product semantics remain operator-owned;
- Bronze/Silver remain reproducible data truth, while Gold may consume probabilistic signals.

## 2. Core architecture decision

The learning layer is **not** a replacement for deterministic Search Intelligence and is **not** an extension of source truth.

It is a signal-producing layer.

A learned component may eventually estimate or propose signals such as:

- role-family fit;
- task-content fit;
- skill relevance;
- skill transferability;
- capability gaps;
- relative job attractiveness;
- ranking preference;
- probability of operator interest;
- probability of progression to application/interview/offer when sufficient evidence exists;
- market or career-cluster similarity.

None of these signals may silently become product truth. Exact Top-5 semantics, thresholds, hard filters, ranking weights and action behavior remain governed by the approved product contract.

## 3. Layering contract

### Layer A — deterministic generics

This is the preferred first solution surface.

Examples include:

- canonical field normalization;
- role/title token normalization;
- structured requirement tags;
- exact and alias skill matching;
- generic synonym/ontology mappings;
- location and work-model parsing;
- seniority heuristics;
- evidence completeness;
- freshness and source-origin evidence;
- explicit hard criteria once product-approved;
- deterministic feature engineering and explainable baseline scoring.

The purpose is to solve as much as practical with cheap, testable and inspectable logic before introducing probabilistic behavior.

### Layer B — bounded LLM booster

`LLM-BOOST-001` remains the semantic escalation path where deterministic handling leaves an ambiguity or information gap.

The LLM layer may propose structured semantic evidence, but its output is not product authority. Existing deterministic validators and product contracts remain authoritative.

For future ranking or matching work, LLM-derived fields should be treated as one independently observable signal family rather than silently merged into canonical truth.

### Layer C — optional ML learning layer

ML is introduced only after enough reproducible evidence exists to answer a concrete question better than the generic baseline and, where relevant, the LLM-assisted baseline.

The learning layer must remain model-agnostic at architecture level. Candidate approaches may later include classical supervised learning, ranking models, representation learning, embeddings or other techniques, but no family is selected by this document.

The key requirement is measurable incremental value.

## 4. First candidate use cases

The following are candidate surfaces, not implementation commitments.

### 4.1 Semantic job-profile matching

Learn a signal that captures task and capability similarity beyond exact keyword overlap.

The comparison target is not only `title <-> title`, but a structured profile-to-job representation that can include:

- role family;
- task content;
- required capabilities;
- adjacent or transferable capabilities;
- seniority evidence;
- domain context;
- work model and geography where product-approved.

### 4.2 Learned job ranking

Learn relative ordering from explicit product-approved factors and later operator feedback.

A learned ranker must not invent hard criteria or silently reinterpret unresolved Top-5 decisions. It may only operate inside an approved ranking contract.

### 4.3 Skill transferability and capability-gap estimation

Distinguish between:

```text
exact match
related capability
transferable capability
credible learning gap
unsupported / unknown
```

This is intended to improve career-path reasoning without treating every missing literal technology name as a hard mismatch.

### 4.4 Role and market clustering

Identify recurring clusters in roles, tasks, capability bundles or employers so the system can expose adjacent opportunity spaces that fixed search terms may miss.

### 4.5 Feedback learning

When sufficient operator history exists, learn from explicit outcomes such as:

```text
reviewed
interesting
saved
rejected
apply
applied
interview
rejected_after_application
offer
```

Feedback learning must distinguish different targets. `operator_interest`, `application_decision` and `interview_outcome` are not the same label and must not be collapsed into one opaque score.

### 4.6 Career and learning intelligence

A later layer may estimate which capability investments expand the reachable high-quality job space.

This is a downstream analytics use case, not a prerequisite for job ranking.

## 5. Training and experimentation platform

**Kaggle is the preferred training and experimentation platform for this concept.**

This is an execution choice, not a product-data authority change.

Kaggle may provide:

- managed CPU/GPU training;
- reproducible notebooks and experiments;
- bounded dataset versions;
- metric comparison;
- artifact generation for evaluated candidate models.

The repository and DB-backed pipeline remain the system of record.

No hand-maintained spreadsheet, CSV or ad-hoc local file becomes pipeline truth. Training data must be generated reproducibly from DB-backed state through an explicit dataset contract. Any Kaggle transport artifact is a generated training package only and must be traceable to its source query/snapshot and schema version.

Model artifacts returning from Kaggle are deployable candidates, not authoritative product state.

## 6. Training dataset contract

Before any model family is selected, the project should define a stable training-data contract.

Every dataset version should record at least:

- dataset contract version;
- source DB snapshot or reproducible query boundary;
- included source/job identities;
- canonical feature schema version;
- label definition and provenance;
- evidence timestamp/freshness boundary;
- train/validation/test split strategy;
- leakage controls;
- excluded or unresolved records;
- LLM-derived feature presence/version when applicable;
- target-profile/product-contract version;
- generation timestamp and code commit.

### Leakage boundary

Future information must not leak into training examples.

Examples:

- application/interview outcomes may not be available to features at ranking time;
- later job-description revisions may not alter historical training examples without explicit versioning;
- duplicate or reposted vacancies must be grouped so near-identical examples do not leak across train and validation/test partitions;
- employer-level repetition must be considered when evaluating generalization.

## 7. Feature families

The architecture should preserve feature provenance rather than flatten everything into an unexplained vector.

Candidate feature families include:

### Deterministic structural features

- role-family evidence;
- normalized task/skill tags;
- source/evidence quality;
- freshness;
- seniority evidence;
- geography/work-model evidence;
- requirement completeness;
- exact/alias/ontology matches;
- capability-gap counts and classes.

### LLM-assisted semantic features

Where LLM-BOOST-001 is used, structured outputs may be supplied as optional features if they have:

- evidence references;
- booster contract/model-stage version;
- deterministic validation status;
- explicit missing/unknown handling.

Ablation tests must show whether these features add value beyond deterministic generics.

### Operator-feedback features and labels

Feedback must be explicit, timestamped and scoped to the decision being modeled. Passive UI behavior should not automatically be treated as strong preference truth.

## 8. Evaluation strategy

Every ML experiment must compare against the simplest useful baseline.

The minimum comparison matrix is:

| Variant | Purpose |
|---|---|
| deterministic generic baseline | proves what can be solved without learned complexity |
| deterministic + LLM booster | measures semantic lift from the existing booster layer |
| deterministic + ML | measures learned lift independent of LLM features |
| deterministic + LLM + ML | tests whether the combined stack adds further value |

Useful metrics depend on the concrete task.

### Matching / classification

- precision;
- recall;
- false-negative rescue rate;
- false-positive rate;
- calibration where probabilities are emitted;
- coverage and unknown-rate.

### Ranking

- NDCG or another position-sensitive ranking metric;
- MRR / top-k hit rate where meaningful;
- pairwise preference accuracy;
- number of relevant jobs rescued into the operator review set;
- operator override/rejection rate.

### Operational metrics

- inference latency;
- compute cost;
- model/feature drift;
- missing-feature rate;
- reproducibility;
- incremental value over the preceding layer.

A more complex model is not promoted merely because an offline metric is slightly higher. The improvement must be large enough to justify added operational and explanatory cost.

## 9. Experiment and promotion ladder

The preferred progression is:

```text
problem + label contract
-> deterministic baseline
-> reproducible Kaggle dataset
-> offline Kaggle experiment
-> holdout comparison
-> repository-recorded experiment evidence
-> shadow scoring on live jobs
-> bounded operator review
-> canary use in Gold read models
-> controlled default signal
```

No stage before controlled default may alter candidate/source lifecycle, connector activation, application decisions or hard eligibility.

## 10. Runtime boundary

A future runtime integration should look conceptually like:

```text
Bronze
  -> Silver canonical job evidence
      -> deterministic feature/evidence layer
          -> generic baseline signals
          -> optional LLM semantic signals
          -> optional ML learned signals
              -> Gold decision/read models
                  -> product-contract validation
                  -> explanation
                  -> operator review
```

Silver stays canonical and reproducible. Learned outputs belong in Gold or in an explicitly non-authoritative feature/signal store feeding Gold.

A model prediction should carry at least:

- model artifact/version;
- feature contract version;
- input evidence fingerprint;
- prediction/signal;
- confidence or score semantics where applicable;
- inference timestamp;
- product authority flag (`false` until an explicit product contract says otherwise);
- explanation inputs sufficient for operator review.

## 11. Explainability and operator control

The Control Center must not display a bare opaque fit number as if it were self-explanatory.

A learned signal should be decomposable into understandable evidence such as:

- strong matching tasks;
- exact capabilities;
- transferable capabilities;
- explicit gaps;
- unresolved evidence;
- hard product criteria independently evaluated outside the model;
- which signal families influenced the recommendation.

The operator must be able to disagree with the learned recommendation without corrupting source truth.

## 12. LLM-as-teacher boundary

A future experiment may use an LLM to propose weak labels or semantic annotations for training efficiency.

This is allowed only as an experiment boundary:

- LLM labels remain provenance-marked weak labels;
- they are not equivalent to operator labels or employer-source truth;
- evaluation must include human/grounded holdout evidence;
- the model must not be evaluated only against labels produced by the same semantic teacher.

This option is intentionally parked until a concrete training task needs it.

## 13. Model-agnostic artifact contract

The repository should eventually standardize candidate model artifacts around metadata rather than a specific framework.

A candidate artifact should be accompanied by a manifest containing at least:

```text
artifact_id
training_run_id
model_family
model_version
feature_contract_version
dataset_version
product_contract_version
code_commit
training_platform = kaggle
evaluation_summary
known_limitations
promotion_state
```

`model_family` exists for traceability but is intentionally unspecified by this concept.

## 14. Non-goals

ML-LEARN-001 does not currently authorize:

- selection of a model family;
- selection of embedding providers or vector databases;
- replacement of deterministic hard filters;
- automatic Top-5 product semantics;
- automatic application submission;
- source activation or connector lifecycle mutation;
- training directly from unversioned ad-hoc files;
- treating LLM output as ground-truth labels;
- online self-training from every click;
- deployment of a model merely because a Kaggle score is good.

## 15. First implementation slice when activated

When this concept is later activated, the smallest useful slice should be **evaluation infrastructure, not model optimization**.

Recommended first slice:

1. define one target task and label contract;
2. materialize a reproducible DB-backed training snapshot for Kaggle;
3. establish a deterministic generic baseline;
4. optionally include the existing LLM-booster signal as a separately measurable feature family;
5. train one or more deliberately unspecified candidate approaches in Kaggle;
6. compare all variants on the same holdout set;
7. write experiment evidence back to repository/DB metadata;
8. shadow-score live jobs without changing product decisions.

Only after this slice proves meaningful incremental lift should model selection or runtime serving become a design decision.

## 16. Architectural principle

The layer exists to answer one question:

> Does learned behavior rescue useful signal that generic deterministic logic and the bounded LLM booster miss, at acceptable complexity and with enough evidence to explain and control it?

If the answer is no, the correct architecture is to keep the ML layer inactive.
