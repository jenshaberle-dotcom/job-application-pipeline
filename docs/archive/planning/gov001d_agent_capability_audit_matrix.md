# GOV-001D Agent Capability Audit Matrix

Status: implemented as documentation foundation  
Scope: governance and documentation only

## Why this block exists

GOV-001A showed that the repository contains many agent-like scripts, tests, and governance-relevant documents. GOV-001B created the governance registry foundation. GOV-001C classified agent-like artifacts.

GOV-001D adds the next required layer:

> capability audit: can each product-facing agent actually handle the expected pipeline content and difficulties?

## Added artifacts

- `docs/reference/governance/agent_capability_audit_matrix.md`
- `docs/reference/governance/agent_capability_gap_register.md`

## Decisions

1. Agent names are not proof of capability.
2. Product agents need capability evidence: tests, runtime smoke, explicit boundaries, and documented known gaps.
3. STOP-001 is useful but incomplete; it needs STOP-002 taxonomy/strategy work before being considered broadly generic.
4. Several agents are now flagged for audit before further expansion.
5. DOC-001 should not try to preserve all historical artifacts as current truth.

## Boundaries

This block does not:

- change pipeline logic,
- access the database,
- run agents,
- migrate schema,
- change scheduler behavior,
- register connectors,
- activate sources,
- archive documentation yet.

## Validation

- Full pytest should remain green.
- `git diff --check` should pass.
- Review should verify the files are documentation-only.

## Next planned GOV blocks

- `GOV-001E Write Boundary & Routing Consolidation Review`
- `GOV-001F Connector Chain Responsibility Contract` if needed
- then `DOC-001 Documentation Rebaseline`
