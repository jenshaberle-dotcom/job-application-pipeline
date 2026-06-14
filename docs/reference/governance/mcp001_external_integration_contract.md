# MCP-001 External Integration Contract

Status: Draft contract for later integration
Boundary: job-application-pipeline as target project

## Purpose

This contract defines what the external MCP / Engineering Agent Control Plane may eventually read, validate, propose, mutate, and rollback in this repository.

It is not an implementation of the agent core.

## Initial integration mode

Initial integration is read-only and local-first:

- inspect repository files
- inspect git state
- inspect documentation and governance rules
- inspect tests and validation scripts
- run explicitly allowed validations
- perform explicitly allowed DB read-only queries
- build evidence packets
- report unknown/stale/inconsistent/needs_inspection

## Forbidden in initial mode

- no DB writes
- no scheduler changes
- no candidate/source/gate/connector/pipeline mutations
- no commits, pushes, PRs or merges
- no export files as source of truth
- no chat or retired restart artifact as source of truth
- no secrets in evidence packets
- no full repository context to LLM

## Later Level-5 mode

Later Level-5 mode may include mutating actions only after capability-specific gates exist:

- decision flight
- policy approval
- operator approval or mature confidence-gated auto-approval
- audit event
- backup / rollback checkpoint
- dry-run
- affected-object inventory
- postcondition checks
- cost preview
- failure quarantine

## Project profile responsibilities

The job-application-pipeline repository should later provide a project profile with:

- repository identity
- relevant documentation roots
- relevant test commands
- validation commands
- DB read-only inspection contracts
- prohibited paths and inputs
- rollback scopes
- capability-specific approval policies
- safety boundaries

## Agent responsibilities

The external MCP agent must:

- treat this contract as policy input, not as truth override
- verify repository truth directly
- fail closed when evidence is insufficient
- record audit events
- avoid uncontrolled shell, DB, scheduler, pipeline or GitHub operations
- preserve the rule that the Chief Agent is not chief of truth, policy or recovery
