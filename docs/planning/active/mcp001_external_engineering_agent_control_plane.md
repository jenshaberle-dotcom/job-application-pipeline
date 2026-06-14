# MCP-001 External Engineering Agent Control Plane

Status: Priority-1 external campaign
Boundary in this repository: planning, governance, and future integration contract only
Implementation home: separate MCP / Engineering Agent Control Plane project

## Decision

MCP-001 is externalized into its own project. The job-application-pipeline repository is the first target project and integration consumer, not the implementation home of the agent core.

The external project should be created as a separate repository, for example:

    ~/projects/mcp-autonomous-engineering-agent

or:

    ~/projects/engineering-agent-control-plane

## Why externalize

Externalization reduces blast radius, keeps the job product pipeline from becoming the agent implementation repo, and allows the engineering agent to become reusable across future projects.

It also makes security boundaries clearer:

- agent core has its own policy engine
- target projects define adapters and allowed capabilities
- target projects do not host uncontrolled agent logic
- integration can be tested progressively

## MCP-001 priority

This external MCP-001 Freeze supersedes the previous active freeze campaign as the priority-1 throughput recovery track.

The previous freeze/product maturity work is not deleted. It is paused and may be re-entered later through MCP-backed state inspection or explicit repo-backed planning.

## Target capability

MCP-001 targets hard-gated Level-5 engineering autonomy over time, including:

- repo inspection
- git and branch hygiene
- tests and validation
- patch planning and patch application
- commit / PR / merge workflows
- DB read-only inspection first, later gated DB migrations/writes
- scheduler changes
- candidate/source/gate/connector/pipeline mutations
- rollback and recovery
- GUI decision and rollback control
- chief-agent orchestration

## Non-negotiable guardrail

The Chief Engineering Agent may coordinate specialized agents, but it is not root of trust.

The Chief Agent may be chief of agents, but never chief of truth, policy, or recovery.

Truth, policy and recovery remain controlled by deterministic, auditable components with veto power.

## Local-first cost control

The external MCP project must be optimized for local execution and sparse LLM usage.

Local by default:

- repo reader
- git reader
- documentation scanner
- governance scanner
- DB read-only checks
- validation runner
- policy engine
- capability registry
- audit ledger
- backup / rollback manager
- confidence scoring
- evidence packet builder
- cost estimator
- GUI state

External LLM only for:

- hard impact analysis
- patch strategy where deterministic checks are insufficient
- high-risk T5 review
- operator-facing explanation where useful

Forbidden by default:

- full repository context sent to LLM
- secrets in LLM context
- web search unless explicitly enabled
- hosted containers unless explicitly enabled
- uncontrolled shell access
- unlisted tools for T5 actions

## Level-5 gate stack

Every mutating action requires:

1. repo/DB-backed truth basis
2. scope declaration
3. affected-object inventory
4. local checks first
5. evidence packet
6. decision flight
7. confidence score
8. cost estimate
9. rollback or recovery plan
10. postcondition plan
11. policy engine approval
12. operator approval unless a later confidence-gated auto-approval tier explicitly applies
13. audit record

## Full-ZIP retirement

Full-repository ZIP review remains the temporary bridge for this project until MCP demonstrates sufficient maturity.

Retirement criteria:

- MCP can read the target repo state reliably
- MCP can inspect relevant files and diffs
- MCP can detect active planning contradictions
- MCP can run or reference validations reliably
- MCP can perform DB read-only checks where needed
- MCP reports unknown/stale/inconsistent/needs_inspection instead of guessing
- MCP audit logs are complete enough for review
- MCP confidence scoring is stable across multiple iterations
- MCP state assessment matches or beats full-ZIP review in repeated comparisons

Chat retired restarts do not return when full-ZIP retires. MCP-backed state inspection replaces full-ZIP.

## Job-pipeline integration boundary

Future integration in this repository is limited to:

- `config/agent/project_profile.yaml`
- allowed validation definitions
- DB read-only query contracts
- rollback scope declarations
- source/gate/candidate mutation policies
- evidence packet schemas
- governance references

The agent core remains external.
