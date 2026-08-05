# E.ON Requirement Inventory 001A

Status: implementation for Issue `#365`

## Product reason

The exact E.ON Product V1 job now has source-grounded evidence for:

- permanent and full-time-compatible employment;
- German and English;
- hybrid work;
- senior-level job requirements.

Candidate capability fit nevertheless remains unknown. The job description has not yet been projected into a canonical set of concrete employer requirement statements, and an approved real Candidate Fact Profile does not yet exist.

A fit decision before both sides are explicit would confuse title or career direction with evidence.

## Exact binding

The runner is bound to:

- raw job `26342`;
- Silver job `466`;
- source `successfactors:eon_germany`;
- external job ID `eon_germany:1414903533`;
- title `(Senior) Data Engineer Data & AI (f/m/d)`;
- the already authorized controlled E.ON pilot dataset.

## Extraction contract

The inventory:

1. reads the stored employer-origin description only;
2. validates the already established fluent German/English and extensive-experience evidence;
3. converts HTML block boundaries into ordered text blocks;
4. recognizes an explicit profile/qualification heading;
5. stops at the next benefits, company, application or other non-profile heading;
6. removes exact duplicate statements;
7. assigns each statement a content-derived SHA-256 identity;
8. preserves the employer's statement text;
9. classifies only explicit lexical families;
10. leaves unsupported classification as `unclassified`.

## Statement families

- `experience`
- `language`
- `education`
- `technical_capability`
- `collaboration`
- `unclassified`

These are inventory families, not approved capability tags and not fit conclusions. A statement may require later operator review or more precise mapping.

## Stability contract

The statement key is derived from normalized statement content. The section hash is derived from the ordered statement keys, families and texts.

Therefore irrelevant HTML changes such as list versus paragraph markup do not change:

- statement texts;
- statement keys;
- statement ordering;
- section hash.

The raw description hash may change because it intentionally fingerprints the complete stored source text.

## Runtime command

```bash
.venv/bin/python -m scripts.run_eon_requirement_inventory \
  --raw-job-id 26342 \
  --silver-job-id 466
```

The runner opens a PostgreSQL read-only transaction and writes only a local review artifact under:

```text
$HOME/product_v1_runtime_artifacts/
```

The console output includes every projected statement, its family and its stable key so the real inventory can be reviewed directly.

## Fail-closed conditions

The runner stops when:

- the exact raw/Silver binding is missing or ambiguous;
- the record is not the authorized E.ON pilot dataset;
- the profile section cannot be recognized;
- the profile section contains no statements;
- the known language evidence is absent from the profile section;
- the known extensive-experience evidence is absent from the profile section;
- statement identity collisions occur.

## Preserved boundaries

The slice performs:

- zero database writes;
- zero candidate-fact reads or writes;
- zero assessment/readiness/ranking mutations;
- zero provider, LLM or network requests;
- zero source, connector or scheduler activations;
- zero application actions.

It does not infer weekly hours and does not create a capability-fit status or score.

## Follow-up

After private runtime validation, the reviewed inventory may feed a separate bounded mapping slice. That future work must:

- define canonical requirement tags from the actual statements;
- keep mandatory and optional requirements distinct;
- compare only against approved eligible Candidate Facts;
- exclude target directions and planned capabilities;
- preserve `unknown` when evidence is incomplete;
- avoid mutating the E.ON assessment until the comparison contract itself has been validated.
