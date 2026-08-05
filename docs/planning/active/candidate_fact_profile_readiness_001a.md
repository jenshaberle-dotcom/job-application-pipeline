# Candidate Fact Profile Readiness 001A

Status: implementation for Issue `#378`

## Product reason

The exact E.ON requirement inventory and canonical employer tag map are runtime-proven. The private Candidate Fact Foundation is also infrastructure-proven, but its proof was deliberately isolated and removed. Repo evidence therefore does not establish that a real operator-approved private profile currently exists.

A later employer/candidate comparison must not run merely because the schema exists. It first needs a redacted read-only decision about whether the current private profile is an admissible comparison input.

## Audit scope

The audit reads only profile `default` from:

- `candidate_fact_profiles`;
- `candidate_facts`;
- `candidate_fact_profile_revisions`.

It uses a PostgreSQL read-only transaction and validates the stored payload through the existing `candidate_fact_profile.v1` parser.

An absent profile is a normal audit result:

```text
profile_state: absent
comparison_input_ready: false
blockers: approved_profile_missing
```

It is not treated as a database or product failure.

## Readiness rules

`comparison_input_ready` may be true only when all of the following hold:

- profile key is `default`;
- schema version is `candidate_fact_profile.v1`;
- source type is `local_private_json`;
- profile state is `approved`;
- profile-level approval metadata is present and consistent;
- the stored payload validates;
- the canonical payload hash matches the stored SHA-256;
- normalized fact rows match the exact canonical fact payloads;
- at least one immutable revision exists;
- at least one approved capability-evidence fact exists;
- at least one distinct capability tag exists on approved capability evidence.

Draft, superseded, absent or invalid profiles remain not ready. Target directions, preferences and planned capabilities remain excluded by the existing Candidate Fact evidence contract.

## Redaction contract

Console and JSON output may include only:

- audit/profile status;
- profile version and payload hash;
- validation booleans;
- revision and fact counts;
- category, evidence-class and approval-state counts;
- distinct capability-tag count;
- non-sensitive blocker codes.

The audit never emits:

- personal statements;
- provenance references;
- capability-tag values;
- fact keys;
- approver identities.

The complete private payload may be parsed and compared internally, but it is never copied into the audit result.

## Runtime command

```bash
.venv/bin/python -m scripts.run_candidate_fact_profile_readiness
```

Reports are written beneath:

```text
$HOME/product_v1_runtime_artifacts/
```

and are marked `review_output_only_not_pipeline_input`.

## Preserved boundaries

- zero database writes or Candidate Fact imports;
- no E.ON requirement-to-candidate comparison;
- no capability-fit decision or score;
- no assessment, readiness, ranking or Top-5 mutation;
- no weekly-hours inference;
- no provider, LLM or network request;
- no source, connector or scheduler activation;
- no application action.

## Completion condition

Issue `#378` remains open until the exact private runtime audit succeeds and establishes the actual current profile state.

- If the result is `absent` or otherwise not ready, the next slice is operator-controlled private profile authoring and plan-only validation.
- If the result is ready, a separate issue may implement a review-only comparison against the already proven E.ON employer tag map.

Neither follow-up is authorized by this audit slice.
