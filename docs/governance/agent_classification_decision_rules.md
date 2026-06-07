# Agent Classification Decision Rules

Status: GOV-001C foundation
Scope: governance, naming, documentation, and future refactoring decisions

## Purpose

The project should not keep creating agent-like scripts without a clear rule for
whether they are product agents, helper scripts, historical artifacts, or
temporary implementation scaffolding.

These rules decide when an artifact may be called an agent and when it should be
renamed, merged, archived, or treated as a helper.

## Rule 1: A product agent owns a responsibility, not a script name

A file name containing `agent` does not make an artifact a product agent.

An artifact is a product agent only if it owns a durable pipeline
responsibility, such as:

- route a candidate to a next safe action,
- audit whether a pipeline stop is valid,
- repair a specific evidence class,
- evaluate a specific gate,
- validate connector output,
- control a lifecycle transition,
- orchestrate a scheduled intelligence cycle.

If the artifact only previews, records, dumps, or manually assists a decision,
it is an operator helper, not a product agent.

## Rule 2: Routers do not repair

Router agents may prioritize and route. They should not perform the repair they
recommend.

Good:

- Candidate Queue Agent routes blocked candidates to Stopper Reassessment.
- Candidate Queue Agent routes evidence gaps to Detail Evidence Repair.

Bad:

- Candidate Queue Agent performs source URL recovery.
- Candidate Queue Agent writes gate decisions while also choosing next actions.

## Rule 3: Repair agents do not approve their own result

Repair agents may discover or rebuild evidence, but they should not be the final
authority that their own repair is sufficient for source activation or connector
registration.

Good:

- Detail Evidence Repair finds supported detail evidence.
- A gate or approval agent evaluates whether the evidence is sufficient.

Bad:

- Detail Evidence Repair finds one promising detail URL and directly marks the
  candidate ready for activation.

## Rule 4: Gate agents evaluate gates; they do not discover evidence

Gate agents should evaluate existing evidence against a contract. They may
record the decision when explicitly allowed, but they should not become search
or repair agents.

Good:

- Gate agent reads evidence and writes a gate review with explicit apply.

Bad:

- Gate agent performs external source discovery to make its decision pass.

## Rule 5: Stopper reassessment is not automatic unblocking

The Pipeline Stopper Reassessment Agent is a stop-validity audit and Stage-2
repair planner.

It may classify stops as likely valid, stale, over-sensitive, or recoverable.
It may generate dry-run and apply commands for a repair stage.

It must not silently change candidate status, gate status, URLs, evidence,
connector files, registrations, or source activation.

## Rule 6: A new agent needs a 15-20 point improvement case

During the architecture freeze/maturity campaign, a new product agent should
only be created when it materially improves at least one of:

- safety,
- security,
- false-negative handling,
- product maturity,
- diagnostic clarity,
- architectural separation.

Otherwise, the idea belongs in the White-Whale Backlog or as a future DOC/STOP
follow-up.

## Rule 7: A helper must not appear in the product pipeline diagram as an agent

Operator helpers can exist, but docs and diagrams must not make them look like
autonomous product agents.

Helpers should use names such as:

- `preview_*`,
- `inspect_*`,
- `record_*`,
- `audit_*`,
- `report_*`.

They should avoid names such as:

- `run_*_agent`,
- `*_orchestrator`,
- `*_controller`,
- `*_gate`.

Exceptions are allowed only when the helper has become a real product agent and
has an explicit registry entry.

## Rule 8: Historical docs remain accessible but must not describe current state

Historical planning docs are useful, but DOC-001 must separate them from current
architecture truth.

Every historical or superseded agent document should be clearly marked as one of:

- current,
- historical,
- superseded,
- spike,
- archived,
- pending capability audit.

## Rule 9: Capability audit determines trust level

An agent is not trusted just because it has tests. It becomes trusted only when
the capability audit verifies that it can handle expected content types and
failure modes for its responsibility.

Capability audit questions:

- What inputs does the agent expect?
- What evidence types does it understand?
- What stops or edge cases can it classify?
- What false-negative risks remain?
- What repair or routing actions can it plan?
- What writes can it perform, and are they gated?
- What tests and runtime reports prove the behavior?
- When must it route to another agent?
- When must it stop for operator review?

## Rule 10: Duplicate decision logic is a governance smell

If two artifacts answer the same product question, one of the following must be
true:

1. One is the authoritative decision owner and the other is a helper.
2. They operate at different stages with different inputs/outputs.
3. One is historical and should be marked as such.
4. A consolidation/refactor follow-up is required.

Examples of questions that should have one owner:

- What is the next safe action for this candidate?
- Is this stop valid or over-sensitive?
- Is this source URL validated enough to persist?
- Is this candidate ready for connector artifact generation?
- Is this connector ready for registration?

## Outcome expected from GOV-001

GOV-001 is complete only when the project has:

- a canonical product-agent registry,
- a helper/stub/legacy classification,
- a capability-audit backlog,
- a consolidation map,
- a rule for creating or rejecting future agents,
- documentation boundaries that DOC-001 can apply across the project.
