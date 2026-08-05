# Private Candidate Fact Authoring Pack 001A

Status: implementation for Issue `#381`

## Product reason

The exact E.ON employer requirement inventory and canonical tag map are runtime-proven. The private Candidate Fact readiness audit is also runtime-proven and reports:

```text
profile_state: absent
comparison_input_ready: false
blockers: approved_profile_missing
```

This is the expected clean state after the isolated synthetic foundation proof was removed. It also means a real employer/candidate comparison is not yet authorized.

The existing private import command can validate or apply a completed Candidate Fact profile, but it must never invent personal facts. This slice creates only a local authoring scaffold.

## Generated local files

Default directory:

```text
$HOME/projects/job-application-pipeline/private_candidate_facts/
```

The path is already protected by repository ignore rules.

### `candidate_fact_profile.private.json`

A valid `candidate_fact_profile.v1` envelope with:

- profile key `default`;
- operator-selected profile version;
- status `draft`;
- no approval metadata;
- zero facts.

The empty draft can pass the existing parser and plan-only import validation. It is not approved and cannot be comparison-ready.

### `eon_candidate_fact_authoring_workbook.private.json`

A review-only workbook bound to:

- raw job `26342`;
- Silver job `466`;
- description SHA-256 `ee2498caa5c374f0b3740030213391b7a73a91b27e00e0de396c16ee963d3a8a`;
- section SHA-256 `d4dcbd0714c68fc356e8b25fd677e686854fa36999d528134feb1e2a78f5ad40`;
- tag-map SHA-256 `3a49b958d433d452c60b8167595345e9581e056c58526ddfc2a26e063356b856`.

It contains exactly eight employer statements and 26 unique employer tags from the same sealed specification used by the canonical tag mapper.

Every requirement starts with blank operator fields:

```json
{
  "evidence_decision": "unreviewed",
  "candidate_fact_keys": [],
  "private_notes": ""
}
```

Employer tags are prompts for review. They are not candidate truth.

### `README.private.md`

The private operating guide explains:

- operator authors every personal fact;
- evidence classes and provenance remain explicit;
- portfolio, training and professional employment stay distinct;
- preferences, target directions and planned capabilities are not capability evidence;
- plan-only validation precedes approval and Apply;
- no private file may be committed.

## Generation command

```bash
.venv/bin/python -m scripts.create_private_candidate_fact_authoring_pack \
  --profile-version eon-authoring-draft-v1
```

The generator does not read the database and performs no import.

## Overwrite control

Existing private files are never overwritten by default. Controlled replacement requires the exact token:

```text
CANDIDATE-FACT-AUTHORING-PACK-OVERWRITE-001
```

Example:

```bash
.venv/bin/python -m scripts.create_private_candidate_fact_authoring_pack \
  --profile-version eon-authoring-draft-v2 \
  --overwrite-token CANDIDATE-FACT-AUTHORING-PACK-OVERWRITE-001
```

## Plan-only validation

After the operator manually authors facts in the private profile:

```bash
.venv/bin/python -m scripts.import_private_candidate_fact_profile \
  --input private_candidate_facts/candidate_fact_profile.private.json \
  --applied-by <operator-name>
```

Without `--apply`, the existing command remains plan-only and performs no mutation.

## Preserved boundaries

- zero Candidate Fact statements generated;
- zero provenance references generated;
- zero capability claims inferred;
- no extraction from chat memory, CV files, uploads, repositories, plans or target profiles;
- no database read or write;
- no profile import, approval or Apply;
- no E.ON comparison or capability-fit decision;
- no assessment, readiness, ranking or Top-5 mutation;
- no provider, LLM or network request;
- no source, connector, scheduler or application action.

## Completion condition

Issue `#381` remains open until:

1. full Pipeline CI passes;
2. the exact local pack is generated on the merged main commit;
3. the generated empty draft passes the existing plan-only validator;
4. output proves eight statements, 26 tags and zero generated candidate facts;
5. no existing private file is overwritten without the exact token.

The operator must still author and approve real private facts after this slice. No later Apply or employer/candidate comparison is authorized here.
