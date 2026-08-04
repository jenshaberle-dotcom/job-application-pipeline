# E.ON Controlled Pilot — Private Runtime Execution Harness

Status: implementation slice for issue `#346`  
Boundary: local/private runtime only  
Product target: one real E.ON job from live SuccessFactors acquisition through Bronze, Silver and Product-V1 readiness

## Purpose

The repository already contains the bounded E.ON connector, the inactive pilot
profile migration and the atomic Bronze-to-Silver pilot runner. The missing
operational step is a single fail-closed command that binds those components to
one reviewed repository revision and one approved local preview artifact.

`scripts/run_eon_private_runtime_execution.py` provides that command. It is not a
scheduler and it does not create a remote write service.

## Execution sequence

The harness performs the following sequence:

1. require an exact 40-character Pipeline commit SHA;
2. verify that the local checkout is on that exact commit and has a clean
   worktree;
3. validate the existing preview artifact as approval evidence only;
4. inspect tracked DB migrations and stop on checksum drift or unrelated pending
   migrations;
5. in `--apply` mode, apply only migrations 084 and 085 when still pending;
6. produce the E.ON pilot dry-run report with zero network and zero DB mutation;
7. run exactly one explicit E.ON Apply;
8. verify the unique raw job, Silver row, canonical source type, inactive pilot
   profile and DB-derived Product-V1 readiness;
9. preserve all reports as `review_output_only_not_pipeline_input`.

## Plan-only preflight

Plan-only mode performs repository, artifact and migration validation without
applying migrations, performing network requests or mutating pipeline data.

```bash
python -m scripts.run_eon_private_runtime_execution \
  --expected-pipeline-sha <reviewed-main-sha> \
  --preview-artifact /path/to/eon_successfactors_preview_20260804T161857.json
```

## One-shot private Apply

Run only from the reviewed WSL checkout with the private PostgreSQL `.env`
available:

```bash
python -m scripts.run_eon_private_runtime_execution \
  --expected-pipeline-sha <reviewed-main-sha> \
  --preview-artifact /path/to/eon_successfactors_preview_20260804T161857.json \
  --reviewed-by connector_autonomy_a1 \
  --applied-by connector_autonomy_a1 \
  --apply \
  --approval-token EON-CONTROLLED-PILOT-INGESTION-001
```

## Fail-closed stops

Execution stops before the live Apply when:

- the checkout SHA differs from the reviewed SHA;
- the worktree is dirty;
- the preview artifact differs from the approved E.ON job contract;
- migration tracking is missing;
- a tracked migration checksum changed;
- any pending migration is outside 084 and 085;
- the pilot profile is not exactly the inactive one-record profile;
- the fresh fetch does not return the exact authorized job;
- post-apply uniqueness, Silver type, inactive-profile or readiness verification
  fails.

## Explicit non-goals

This harness does not authorize:

- scheduler changes or recurring ingestion;
- provider or LLM requests;
- browser automation or access-control bypass;
- source-family activation;
- assessment insertion or score invention;
- Top-5 forcing;
- application generation or submission;
- reuse of the read-only provider benchmark credentials for writes.

Issue `#346` remains open until the real private-runtime Apply and its resulting
audit artifact have been inspected.
