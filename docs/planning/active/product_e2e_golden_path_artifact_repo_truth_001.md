# Product E2E Golden-Path Artifact Repo Truth — 001

## Problem

The Product E2E Golden Path previously copied `build_status` only from the
DB-backed lifecycle projection. After approved connector artifacts were generated
and merged, that projection could still report `artifact_generation_allowed` even
though the exact module, test and documentation files were present in the current
repository checkout.

The existing connector-build bridge already reconciles the same persisted request
with repository file truth. The Golden Path must use the same factual boundary so
that a completed connector-build slice advances to source-activation review rather
than remaining blocked at connector build.

## Reconciliation contract

For each candidate, the Golden Path now reads the dedicated persisted connector
build request and its exact three artifact paths:

- connector module path;
- connector test path;
- connector documentation path.

The effective status becomes `artifacts_present` only when all conditions hold:

1. the persisted request already has status `artifact_generation_allowed` or
   `artifacts_present`;
2. all three persisted paths are relative repository paths;
3. none of the paths resolves outside the repository root;
4. all three paths exist as files in the current checkout.

The dedicated build-request status takes precedence over a stale lifecycle-view
projection. Missing files, unsafe paths or any non-authorized build status preserve
the persisted status unchanged.

## Safety boundary

Repository file presence is evidence of completed approved artifact generation. It
is not authorization.

This reconciliation does not:

- approve artifact generation;
- persist or update a build request;
- register a connector;
- activate a source;
- write Bronze, Silver or Gold jobs;
- change scheduler or Wave policy;
- make network, provider or LLM calls;
- introduce company-specific control flow.

Connector artifacts still advance only to the existing separate
`source_activation_approval_required` operator gate.

## Validation

Unit coverage proves:

- authorized complete artifacts overlay stale DB status;
- the dedicated request status wins over a stale lifecycle view;
- one missing artifact prevents completion;
- file presence cannot bypass build approval;
- absolute and repository-escaping paths are rejected.

After merge, the private unchanged Golden-Path audit must be rerun against the
local DB. Accompio and Computacenter should advance from `connector_build` to
`source_activation`; the next priority must then be selected from the fresh
cross-source blocker evidence.
