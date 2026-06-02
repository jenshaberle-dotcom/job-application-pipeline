# S7G — Orchestrator Attention in Control Center

## Purpose

S7G connects the S7F nightly Search Intelligence orchestrator audit to the Gold-backed Control Center. The orchestrator should not remain CLI-only once it produces `attention_required` steps. Those steps must be visible where approvals, lifecycle blockers and market coverage are reviewed.

## Implemented Surface

S7G adds Gold read views for the latest orchestrator run:

- `gold_search_intelligence_orchestrator_latest_run`
- `gold_search_intelligence_orchestrator_attention_steps`

The Control Center then loads the latest attention steps and surfaces them in:

1. the dashboard overview as a compact attention panel,
2. a dedicated `Orchestrator` tab,
3. a copyable audit-only refresh command.

## Boundary

This remains a control-plane/read-model integration.

It does not:

- run child agents from the browser,
- browse external sources,
- mutate search profiles,
- register connectors,
- activate sources,
- write Bronze records,
- change scheduler configuration.

## Why This Matters

The nightly cycle is the system brain. If it says something requires attention, the product UI must show that state. Otherwise the intelligence loop becomes another hidden console script and loses product value.

## Next Step

After this, the next useful implementation block is a controlled action model for selected orchestrator recommendations. That should still preserve explicit approval gates and avoid turning the scheduler into a second hidden pipeline controller.
