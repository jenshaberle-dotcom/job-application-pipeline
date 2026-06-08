# S7F — Nightly Search Intelligence Orchestrator Foundation

## Purpose

S7F introduces the first explicit orchestration layer for the Search Intelligence rule cycle. The project already has focused agents for novelty analysis, vocabulary learning, candidate intelligence, origin-source discovery, connector build planning, approval handling and Gold-backed dashboard reads. S7F does not replace these agents. It creates the control-plane layer that can review their current state in one ordered cycle.

The goal is to make the system explainable as an intelligent product rather than a collection of crawler scripts.

## Boundary

The S7F foundation is intentionally audit-only.

It may:

- read Gold Search Intelligence views,
- derive ordered next actions,
- print a cycle report,
- persist its own orchestrator run and step audit when explicitly executed with `--write`.

It must not:

- browse external websites,
- mutate search profiles,
- register connectors,
- activate sources,
- write Bronze records,
- change scheduler configuration,
- create auto-PRs,
- use CSV or export files as pipeline inputs.

## Current Role

S7F is the bridge between the documented rule cycle and a later scheduled process. It answers:

1. What does the Gold layer currently say about market coverage?
2. Which candidates need lifecycle or gate reassessment?
3. Which approval items require explicit human review?
4. Which candidates still lack selected Origin Source Discovery Gate evidence?
5. Are learning and novelty signals currently actionable?
6. Is the system ready for scheduler integration?

## Proposed Cycle Order

The S7F report uses this ordered cycle:

1. `gold_market_coverage_snapshot`
2. `candidate_lifecycle_review`
3. `approval_queue_review`
4. `origin_source_discovery_gate_review`
5. `learning_and_novelty_review`
6. `scheduler_boundary_review`

The last step is deliberately deferred. Scheduler wiring should only happen after the orchestrator has stable manual run history.

## CLI

Dry-run:

```bash
python -m scripts.run_nightly_search_intelligence_orchestrator \
  --reviewed-by jens
```

Persist audit-only run:

```bash
python -m scripts.run_nightly_search_intelligence_orchestrator \
  --reviewed-by jens \
  --write
```

## Data Model

S7F adds:

- `search_intelligence_orchestrator_runs`
- `search_intelligence_orchestrator_steps`

These tables are audit/control-plane tables only. They do not become source-of-truth inputs for ingestion or activation decisions.

## Demo Narrative

The orchestrator allows the demo story to move from:

> I built a crawler.

To:

> I built a controlled market-intelligence loop. It reads bounded market evidence, learns companies and terms, gates origin sources, queues approvals, and stops before irreversible actions.

## Next Implementation Blocks

Likely follow-up work:

1. Add a Control Center tab or section for latest orchestrator runs.
2. Add targeted execution hooks for already-safe child agents.
3. Add run history and regression checks for repeated nightly cycles.
4. Only then evaluate scheduler integration.
