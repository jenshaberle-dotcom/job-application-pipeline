# ML-PILOT-001A — Operator Review Label Evidence Contract

Status: implementation foundation
Target: `operator_review_relevance`

## Purpose

Capture explicit operator judgments that can later become supervised evidence for the first ML booster without turning model output, passive UI behavior or deterministic scores into ground truth.

## Label vocabulary

- `interesting` -> supervised target `1`
- `not_relevant` -> supervised target `0`
- `unsure` -> retained evidence, excluded from binary supervised training
- unreviewed jobs have no label and must never be treated as negatives

The label answers only: **is this canonical job worth operator review?**

It does not encode application intent, interview outcome or offer outcome.

## Provenance

Each append-only event binds:

- Silver job identity;
- label-contract version;
- reviewer and timestamp;
- evidence cutoff;
- fingerprint of the job evidence available at review time;
- why the job entered the review sample;
- capture surface;
- whether deterministic, ML or LLM signals were visible;
- active ML artifact and score when one existed, including blind holdout cases;
- optional note;
- optional superseded prior label event.

Corrections append a new event; historical label events are not edited in place.

## Sampling reasons

The initial vocabulary is:

- `normal_review`
- `ml_uncertainty`
- `signal_disagreement`
- `exploration_random`
- `tail_sample`
- `blind_holdout`

This prevents the later training corpus from consisting only of jobs the current model already preferred.

## Exposure bias

The system records whether deterministic, ML and LLM signals were visible to the operator. An active ML prediction may be recorded even when it is hidden in a `blind_holdout` review. This allows later analysis of whether displayed model scores influenced the human label.

## Authority boundary

Operator review labels are ground truth only for the scoped `operator_review_relevance` target. They do not establish:

- ranking authority;
- Top-5 membership;
- hard eligibility;
- source activation;
- application action;
- interview or offer probability truth.

## Relationship to MLF-005

The operator explicitly allowed label capture to start before the outstanding MLF-005 live DB materialization proof so that useful feedback can accumulate early.

This does **not** waive MLF-005 for training. Until the live read-only package proof passes, the project must not create the supervised training snapshot/split or train Logistic Regression, LightGBM or another model from these events.

## First downstream use

After MLF-005 passes, the first training slice may join a frozen historical job-evidence snapshot with the latest eligible label event as of the dataset cutoff, group duplicates/reposts, use an out-of-time holdout and compare:

1. deterministic baseline;
2. logistic regression control;
3. LightGBM candidate.

All predictions remain shadow-only until separate promotion evidence exists.
