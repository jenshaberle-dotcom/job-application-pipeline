# Private Candidate Fact authoring integrity 001A

Status: implementation for Issue `#383`

## Product reason

The private Candidate Fact authoring pack is runtime-proven. It creates:

- an empty schema-valid private draft profile;
- a source-bound E.ON workbook with eight employer statements and 26 canonical employer tags;
- no personal facts, provenance or capability claims.

The profile parser validates an individual Candidate Fact profile, but it does not validate the relationship between that profile and the authoring workbook. A separate local integrity check is required before any semantic comparison can be considered.

## Inputs

Default private files:

```text
private_candidate_facts/candidate_fact_profile.private.json
private_candidate_facts/eon_candidate_fact_authoring_workbook.private.json
```

Both paths are git-ignored private runtime state.

## Integrity scope

The validator checks:

- the profile through the existing `candidate_fact_profile.v1` parser;
- the exact workbook schema and review-only marker;
- the exact E.ON raw/Silver IDs;
- the proven description, section and tag-map hashes;
- the exact eight statement keys and employer texts;
- the exact 26 canonical employer tags;
- matching workbook/profile versions;
- supported operator decisions;
- structural Candidate Fact references.

Supported decisions:

```text
unreviewed
evidence_available
no_evidence
not_applicable
needs_followup
```

## Reference rules

- `evidence_available` requires at least one Candidate Fact key that exists in the private profile.
- `unreviewed`, `no_evidence`, `not_applicable` and `needs_followup` must not reference Candidate Facts.
- Duplicate references within a requirement fail closed.
- Unknown references fail closed.
- The same valid fact may be deliberately referenced by more than one employer requirement.

Reference validation is structural only. It does not decide that the referenced fact semantically satisfies the employer requirement.

## Completion rule

`authoring_complete=true` requires all eight requirements to have one of the final decisions:

- `evidence_available`;
- `no_evidence`;
- `not_applicable`.

Any `unreviewed` or `needs_followup` row keeps the pack incomplete.

An untouched generated pack therefore produces a valid but incomplete result:

```text
decision_counts: unreviewed=8
authoring_complete: false
blockers: unreviewed_requirements_present
```

A structurally complete authoring result is not a capability-fit result. It means only that the operator deliberately reviewed every row and all references are internally valid.

## Runtime command

```bash
.venv/bin/python -m scripts.run_private_candidate_fact_authoring_integrity
```

Optional paths:

```bash
.venv/bin/python -m scripts.run_private_candidate_fact_authoring_integrity \
  --profile private_candidate_facts/candidate_fact_profile.private.json \
  --workbook private_candidate_facts/eon_candidate_fact_authoring_workbook.private.json
```

Reports are written beneath:

```text
$HOME/product_v1_runtime_artifacts/
```

and are marked `review_output_only_not_pipeline_input`.

## Redaction contract

Console and report may expose only:

- profile version/status and payload hash;
- workbook hash;
- profile fact count;
- requirement and unique employer-tag counts;
- decision counts;
- distinct referenced-fact count;
- completion status and non-sensitive blockers.

They never expose:

- personal statements;
- provenance references;
- capability-tag values;
- Candidate Fact keys;
- private notes.

## Preserved boundaries

- no file mutation except the local review report;
- zero database reads/writes;
- no Candidate Fact import or approval;
- no semantic employer/candidate comparison;
- no capability-fit decision or score;
- no assessment, readiness, ranking or Top-5 mutation;
- no provider, LLM or network request;
- no source, connector or scheduler activation;
- no application action.

## Completion condition

Issue `#383` remains open until:

- full Pipeline CI passes;
- the untouched private pack is validated locally;
- the observed result is valid but incomplete with eight unreviewed requirements;
- redaction and zero-side-effect boundaries are confirmed.

The operator-authored facts themselves are a later human-controlled step. Semantic E.ON comparison remains separately gated.
