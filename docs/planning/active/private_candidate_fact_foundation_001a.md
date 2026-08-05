# Private Candidate Fact Foundation 001A

Status: implementation for Issue `#362` / backlog story `APP-011`

## Product reason

The exact E.ON Product V1 assessment now has employer-origin evidence for employment type, German and English, hybrid work and senior-level requirements. It correctly remains blocked by:

- numeric weekly-hours evidence;
- candidate capability-fit evidence.

The canonical target profile cannot supply capability truth. It explicitly describes a direction and must not be used to infer seniority, production experience or already-held formal titles. A deterministic capability comparison therefore needs an operator-approved candidate/CV fact basis first.

## Privacy model

Personal candidate facts are local private runtime inputs.

The public repository contains only:

- the schema migration;
- validation and import code;
- fail-closed tests;
- a synthetic draft template;
- operational documentation.

It contains no Jens-specific CV statement, employer history, qualification, project claim or capability assertion. Dedicated `.gitignore` patterns protect common private input locations and names.

Recommended local location:

```text
$HOME/projects/job-application-pipeline/private_candidate_facts/candidate_fact_profile.private.json
```

Reports are written to:

```text
$HOME/product_v1_runtime_artifacts/
```

Reports are review outputs only and never pipeline source inputs.

## Contract

Schema version:

```text
candidate_fact_profile.v1
```

Profile states:

- `draft`
- `approved`
- `superseded`

Fact approval states:

- `proposed`
- `approved`
- `rejected`
- `superseded`

Every fact carries:

- stable `fact_key`;
- category;
- evidence class;
- statement;
- capability tags;
- limitations;
- one or more provenance records;
- optional validity dates;
- explicit approval state;
- fact-level approver and timestamp when approved.

An approved profile also requires its own approver and timezone-aware approval timestamp. Apply requires `--applied-by` to match that profile approver.

## Evidence classes

### Capability evidence eligible

- `professional_employment`
- `formal_education`
- `portfolio_implementation`
- `training_certification`

These remain distinguishable. In particular, portfolio implementation and training do not silently become professional production experience.

### Not capability evidence

- `operator_preference`
- `target_direction`
- `planned_capability`

These may be valid approved facts, but they must carry the limitation `not_capability_evidence` and are excluded from capability-evidence indexes.

## Additional fail-closed rules

- Portfolio implementation requires repository provenance.
- Professional-employment evidence requires operator assertion, canonical CV or employment-record provenance.
- Approved facts require fact-level approver and timezone-aware timestamp.
- Unapproved facts may not carry approval metadata.
- Unknown JSON keys are rejected.
- Duplicate fact keys, capability tags and provenance records are rejected.
- Content changes require a new `profile_version`.
- A profile with the same canonical hash is an idempotent replay.

## Database model

Migration 088 creates:

- `candidate_fact_profiles` — current versioned profile envelope and private canonical payload;
- `candidate_facts` — normalized queryable facts with evidence and approval state;
- `candidate_fact_profile_revisions` — immutable before/after payload revisions.

The migration is schema-only and inserts no candidate data.

## Operator flow

Copy the synthetic template to a git-ignored private path and replace all synthetic content locally.

### Validate in plan-only mode

```bash
.venv/bin/python -m scripts.import_private_candidate_fact_profile \
  --input private_candidate_facts/candidate_fact_profile.private.json \
  --applied-by jens
```

### Controlled Apply

```bash
.venv/bin/python -m scripts.import_private_candidate_fact_profile \
  --input private_candidate_facts/candidate_fact_profile.private.json \
  --applied-by jens \
  --apply \
  --approval-token CANDIDATE-FACT-PROFILE-IMPORT-001
```

### Idempotent replay

Run the same Apply command again. Expected result:

```text
revision_inserted: False
profile_updated: False
```

## Redaction contract

Console and JSON reports expose only:

- profile metadata;
- payload hash;
- fact counts;
- approval counts;
- category counts;
- evidence-class counts;
- mutation/replay state;
- preserved-boundary counters.

They do not emit candidate statements or provenance references.

## Preserved boundaries

This slice does not:

- import chat memory automatically;
- read or infer facts from CV files;
- decide E.ON capability fit;
- infer weekly hours;
- mutate E.ON assessment or Product V1 readiness;
- create scores or Top-5 membership;
- call a provider, network service or LLM;
- activate a source, connector or scheduler;
- create or send an application.

## Follow-up

After an approved private profile exists, a separate evidence-bound slice may compare only eligible approved facts with the exact stored E.ON requirements. The outcome may be `passed`, `failed` or `unknown`; it must not use target directions or planned capabilities as evidence.
