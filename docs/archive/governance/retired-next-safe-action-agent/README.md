
# Retired next-safe-action / child-run steering artifacts

Status: Historical archive / retired anti-pattern
Boundary: Not executable project logic

These artifacts are retained only as historical evidence for CONSISTENCY-001B.

They must not be imported by active tests, invoked by active scripts, used as
restart truth, used as chat handover steering, used as NEXT steering, or used as
pipeline-control logic.

Retired patterns include:

- `next safe action` as chat-/handover-/restart steering
- `planned_command` as executable next-work instruction
- `run_child` as active child-run orchestration
- assistant/chat/export-derived next-work control

Future MCP/agent systems may produce local decision evidence, but execution must
go through MCP policy, capability, audit, validation and rollback controls.
