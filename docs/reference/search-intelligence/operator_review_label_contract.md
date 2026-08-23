# ML-PILOT-001A/B — Operator Review Label Evidence and Capture Contract

Status: append-only evidence + Control Center capture merged; runtime DB migration status proof pending
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

## Control Center capture path — ML-PILOT-001B

The canonical Product V1 Control Center may capture labels through the narrowly allowlisted action:

```text
POST /api/v1/product-v1/job-review-label
```

The browser may submit exactly:

```json
{
  "silver_job_id": 42,
  "label": "interesting"
}
```

No other client-supplied provenance is accepted. In particular, the browser cannot choose or forge reviewer identity, timestamps, evidence cutoff, evidence fingerprint, sampling reason, model identity, model score or authority flags.

The server owns those fields and, for the initial normal-review UI:

- records reviewer identity as the Control Center operator surface;
- uses the current timezone-aware UTC review timestamp as the evidence cutoff;
- reloads the exact 20-column MLF Silver evidence projection from `silver_jobs` under the exact job identity;
- fails closed if Silver evidence timestamps cross the review cutoff;
- fingerprints the canonical evidence bytes deterministically;
- records `selection_reason=normal_review`;
- records `capture_surface=control_center`;
- records deterministic-signal visibility only when the current `job_product_assessments.assessed_by` value is exactly `deterministic_product_v1`;
- records ML and LLM signal visibility as false in this first UI because those signals are not displayed there;
- leaves all ranking, application and product authority false.

The React job-detail surface exposes three one-click choices: `interesting`, `not_relevant`, and `unsure`. The click itself is the explicit operator judgment; no additional confirmation dialog is required because the action is append-only, low-authority and correctable.

The UI does not optimistically invent truth. After the POST result it reloads Product/DB truth, and the latest persisted label is projected back onto the exact Silver job.

If the same label is submitted again while the canonical Silver evidence fingerprint is unchanged, the action is idempotent and does not append another event. If the judgment changes, or the evidence changed, a new event is appended and the prior event is referenced through `supersedes_label_event_id` when present.

## Sampling reasons

The initial vocabulary is:

- `normal_review`
- `ml_uncertainty`
- `signal_disagreement`
- `exploration_random`
- `tail_sample`
- `blind_holdout`

This prevents the later training corpus from consisting only of jobs the current model already preferred.

ML-PILOT-001B uses only `normal_review`. Future sampling controllers may select the other reasons, but they must remain server-owned provenance rather than arbitrary browser input.

## Exposure bias

The system records whether deterministic, ML and LLM signals were visible to the operator. An active ML prediction may be recorded even when it is hidden in a `blind_holdout` review. This allows later analysis of whether displayed model scores influenced the human label.

## Authority boundary

Operator review labels are ground truth only for the scoped `operator_review_relevance` target. They do not establish:

- ranking authority;
- Top-5 membership;
- hard eligibility;
- lifecycle state;
- source activation;
- application action;
- interview or offer probability truth.

The Control Center label action performs no provider request, model training, Kaggle execution, external execution or GPU allocation.

## Runtime availability

Repository implementation and CI do not by themselves prove that the configured local PostgreSQL runtime has migration `101_create_job_review_relevance_label_events.sql` applied. A one-shot self-hosted read-only status workflow verifies migration tracking and pending filenames before any migration application is considered. Until that proof passes, the UI must honestly report capture unavailable when the label table/view are absent.

## Relationship to MLF-005

The operator explicitly allowed label capture to start before the outstanding MLF-005 live DB materialization proof so that useful feedback can accumulate early.

This does **not** waive MLF-005 for training. Until the live read-only package proof passes, the project must not create the supervised training snapshot/split or train Logistic Regression, LightGBM or another model from these events.

## First downstream use

After MLF-005 passes, the first training slice may join a frozen historical job-evidence snapshot with the latest eligible label event as of the dataset cutoff, group duplicates/reposts, use an out-of-time holdout and compare:

1. deterministic baseline;
2. logistic regression control;
3. LightGBM candidate.

All predictions remain shadow-only until separate promotion evidence exists.
