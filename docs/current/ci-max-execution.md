# CI-Max Trusted Local Execution

Status: current execution contract

The Job Application Pipeline uses CI as the default execution plane for development and bounded product operations. Manual terminal choreography is not a normal pipeline stage.

## Execution surfaces

### 1. Normal repository CI

Normal PR/push CI owns portable validation such as tests, Ruff, compilation, frontend build, migration/governance contract checks and re-entry identity checks.

It may run on the selected warm runner or GitHub-hosted fallback where the workflow explicitly permits that. It must not depend on the operator's local `.env` or mutate the live local Product database.

### 2. Trusted Local Product CI

Live local Product/runtime operations use `.github/workflows/trusted-local-product-campaign.yml` and `scripts/run_trusted_local_product_campaign.py`.

This surface is intentionally different from ordinary PR CI:

- it runs only on the dedicated self-hosted local runtime label `job-pipeline-runtime-linux`;
- there is no GitHub-hosted fallback for Product/DB mutations;
- it resolves and validates the RCC runtime context before execution;
- the local `.env` remains on the operator host and is never copied into GitHub, an Actions artifact or a PR checkout;
- the persistent local project checkout must be clean and must fast-forward to the exact trusted `main` SHA before any mutation;
- privileged Product execution therefore runs trusted `main` code, never arbitrary PR code with local credentials available;
- every request is parsed as bounded data and is constrained to an explicit execution mode;
- exact candidate identity is revalidated before company-key child runners may execute;
- the campaign re-reads persisted state after each bounded transition rather than replaying a precomputed mutation sequence;
- safe receipts contain only bounded status/evidence summaries and may be persisted back to the active issue.

Current `db_only` mode may execute deterministic, allowlisted Employer-Origin DB/gate transitions. It fails closed before repository artifact generation, connector registration, source activation, final approval, UAC or any unrecognized action.

### 3. Exact schema migration CI

Database schema changes are also CI-eligible, but they remain a separate exact-migration authority boundary. Existing migration workflows establish the required pattern:

`read-only migration status -> require exact/sole expected pending migration -> apply exact migration -> schema/postcondition proof -> safe receipt`.

The Product campaign must not silently apply arbitrary pending schema migrations merely to make an E2E run pass.

## Manual work is the exception

Routine deterministic DB writes are not manual by definition. They should execute through Trusted Local Product CI when their authority and postconditions are machine-checkable.

Manual/operator interaction is reserved for real authority boundaries, including:

- UAC/elevation that cannot be safely prestaged behind an already-approved local capability;
- an explicit human product/governance approval;
- genuine semantic ambiguity classified as `manual_review_required`;
- destructive or exceptional recovery where automatic rollback/compensation authority is not established;
- a local infrastructure incident that prevents any trusted CI runner from executing.

A queued self-hosted Product job is an infrastructure wait, not a reason to fall back to a developer terminal or GitHub-hosted runner. The queued job should continue automatically when the trusted runner becomes available.

## CI-first development rule

For JAP development and Product Recovery:

1. make the smallest repository change that removes the observed E2E blocker;
2. use minimal local checks only when necessary to prevent obviously broken pushes;
3. push early and let full CI own broad validation;
4. after merge, use Trusted Local Product CI for bounded live runtime/DB continuation;
5. stop only at a real human/UAC/capability/invariant boundary;
6. feed that stop back into the Pipeline Development Navigator as the current horizontal position or vertical capability spike.

This contract exists to eliminate manual gate-by-gate copy/paste while keeping local credentials, Product truth and mutation authority fail-closed.
