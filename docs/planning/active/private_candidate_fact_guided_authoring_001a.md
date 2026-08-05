# CANDIDATE-FACT-GUIDED-AUTHORING-001

Status: active implementation  
Issue: #385  
Authority: local private operator authoring only

## Runtime motivation

The first real operator execution of the private Candidate Fact authoring pack proved that the technical files were correct but the interaction was not usable. The documented shell block opened the empty profile and the nested E.ON workbook directly in Nano. No data was changed, but the operator had to interpret the raw `candidate_fact_profile.v1` and workbook schemas manually.

The runtime evidence remained safe:

- profile status `draft`;
- fact count `0`;
- E.ON requirements `8`;
- unique employer tags `26`;
- decisions `unreviewed=8`;
- `authoring_complete=false`;
- no database read or write;
- no import, approval, comparison or capability-fit decision.

This slice removes direct JSON editing from the normal operator path.

## Product contract

The command

```bash
.venv/bin/python -m scripts.author_private_candidate_facts
```

loads the existing ignored private profile and workbook, verifies their structural integrity, and guides the operator through all eight E.ON requirements.

For each requirement it displays:

- the sealed employer statement;
- the canonical employer tags as prompts only;
- the existing review decision;
- a numbered decision menu.

The operator can explicitly choose:

- `evidence_available`;
- `no_evidence`;
- `not_applicable`;
- `needs_followup`;
- `unreviewed`;
- `q` to quit without saving.

For `evidence_available`, the operator can reference an existing private Candidate Fact or author a new one through explicit prompts. The assistant never fills a personal statement, capability tag, limitation, provenance reference, evidence class or review decision automatically.

## Candidate Fact creation boundary

A newly entered fact is always written as:

- `approval_status=proposed`;
- `approved_by=null`;
- `approved_at=null`.

The profile remains `draft`. Approval and profile import remain separate later actions.

The guided dialogue asks for:

- stable `fact_key`;
- evidence class;
- schema-compatible category;
- operator-confirmed statement;
- operator-entered capability tags;
- operator-entered limitations;
- one or more provenance entries;
- optional validity dates.

The existing `candidate_fact_profile.v1` parser validates the complete candidate profile before the fact is accepted in the in-memory session.

## Save protocol

At any prompt, `q`, EOF or keyboard interruption discards the in-memory session and leaves both files unchanged.

After all eight rows, the CLI shows only a redacted summary. Writing requires the exact confirmation token:

```text
SPEICHERN
```

A confirmed changed session:

1. validates the complete profile and workbook pair through the existing profile parser and authoring-integrity validator;
2. creates timestamped private backups beneath `private_candidate_facts/backups/`;
3. writes both JSON files using temporary same-directory files and `os.replace`;
4. restores both originals from memory if either replacement fails.

No backup or write occurs for quit, declined confirmation or an unchanged payload.

## Preserved prohibitions

The CLI has no authority for:

- chat, CV, repository or document fact extraction;
- provider or LLM calls;
- network access;
- database reads or writes;
- Candidate Fact import;
- Candidate Fact or profile approval;
- E.ON semantic comparison;
- capability-fit decision;
- score, readiness, ranking or Top-5 mutation;
- source, scheduler or application action.

Employer tags remain employer prompts and never become candidate truth without explicit operator entry.

## Acceptance proof

Required before closure:

- CI full suite passes;
- `q` leaves both private files byte-identical;
- eight explicit `no_evidence` decisions produce a structurally complete review without facts;
- an explicitly authored portfolio fact validates as `proposed` with repository provenance;
- final summaries do not contain private statements, provenance references or tag values;
- confirmed save creates exact backups and a structurally consistent profile/workbook pair;
- local runtime against the real untouched pack starts the guided menu without opening Nano;
- no private save is required for the initial smoke proof.
