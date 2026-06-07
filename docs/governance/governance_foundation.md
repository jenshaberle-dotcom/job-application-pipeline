# DOC-001 Governance Foundation Gate

## Purpose

This document defines the minimum governance foundation for the project.

It exists because the project now contains multiple interacting agents, gates, views, migrations, scripts, UI surfaces and documentation layers. A local change can easily look correct while creating drift elsewhere in the pipeline.

Governance in this project means:

- keep architecture decisions visible,
- keep implementation and documentation aligned,
- prevent CSV/export artifacts from becoming hidden inputs,
- prevent local-only shortcuts from becoming future cloud or CI debt,
- make agent decisions reviewable,
- preserve learning without chasing every white whale immediately.

This is intentionally a lightweight gate, not an engineering operating system.

---

## Required Checks Before a Meaningful PR

A meaningful PR is any change that touches one or more of:

- source discovery,
- candidate promotion,
- URL discovery/recovery,
- gate logic,
- connector generation/registration/activation,
- Bronze/Silver/Gold data flow,
- Control Center UI or ViewModels,
- scheduler/orchestration,
- migrations,
- documentation that describes current system behavior.

Before such a PR is merged, the author should perform the following checks.

---

## 1. System Impact Check

Question:

> What does this change affect across the full system?

Review the impact across:

```text
Discovery
→ Evidence
→ Candidate / Gate
→ Connector
→ Bronze
→ Silver
→ Gold
→ UI / Observability
```

Minimum answer:

- affected tables, views, scripts, agents and docs,
- whether false positives become more likely,
- whether false negatives become more likely,
- whether existing logic is duplicated or bypassed,
- whether the change should be local or centralized,
- which tests prove the boundary.

If a change touches a shared layer, do not describe it as source-specific without checking other sources.

---

## 2. Project Drift Index

Question:

> How far has the project drifted from the documented truth?

Use these levels:

| Level | Meaning | Action |
|---|---|---|
| PDI-0 | Docs and implementation agree. | Continue. |
| PDI-1 | Minor wording drift or missing reference. | Fix in the same PR if easy. |
| PDI-2 | A feature is implemented but not clearly documented. | Add a current-state note before building on it. |
| PDI-3 | Docs imply a different system than the repo/DB behavior. | Stop and reconcile before the next large block. |
| PDI-4 | The next implementation decision depends on stale docs. | Governance/doc baseline first. |

Current baseline as of DOC-001/DOC-002:

- Documentation drift is at least **PDI-3**.
- Governance exists conceptually, but this block moves it into the repository.
- Wave Search Intelligence and Discovery Iteration Closure must be described as built/partly tested but not fully operationally validated.

---

## 3. Lessons Learned Check

Question:

> If this bug, drift or failure happened once, how do we prevent recurrence?

For every meaningful fix, check whether the recurrence path needs one of:

- a unit test,
- a migration test,
- a preflight check,
- a DB constraint,
- an explicit CLI dry-run boundary,
- a documentation note,
- a Control Center warning,
- a backlog item.

A local fix is not complete until recurrence is either blocked or consciously documented as follow-up.

---

## 4. White Whale Backlog

Question:

> Is this idea valuable but too broad for the current block?

If yes, park it instead of losing it or turning the current PR into a whale hunt.

Examples:

- complete agent health dashboard,
- full market recall monitoring,
- production-grade reset/reprocess UI,
- full compliance/deletion workflow,
- full Gold/application layer,
- adaptive page-learning optimization beyond the current validation need.

Rule:

> Saving does not mean forgetting. Nicht jeder Wal muss heute gefangen werden.

---

## 5. Conversation Health Check

Question:

> Is the chat still a reliable working surface?

Create a handoff and start a new chat when multiple symptoms appear:

- app/web synchronization issues,
- missing or partially invisible answers,
- upload/download problems,
- significant subjective performance degradation,
- too many unresolved architecture decisions living only in chat,
- repeated re-explanation of the same project state.

The handoff is not complete until a reflection pass has checked whether new rules were invented while writing it.

---

## 6. Reflection Pass

At the end of a handoff or large planning block, ask:

- What did we decide while summarizing?
- Did we create a new project rule?
- Does the exported handoff include that new rule?
- Does the repository need a document update before implementation continues?

If the answer is yes, update the handoff or add a repo-level documentation task before declaring the context healthy.

---

## 7. Branch and PR Safety

Default workflow for implementation PRs:

1. Branch guard before staging or committing.
2. Final validation:
   - `python -m pytest -q`
   - `git diff --check`
3. Review staged diff before commit.
4. Push branch before PR creation.
5. Merge only after the expected validation is green.
6. Clean up local and remote branches after merge.

Commits on `main` are considered unsafe. The preferred guard should print a clear warning and switch/create the intended feature branch before committing.

---

## 8. Documentation as Product Surface

Documentation is not separate from the product.

Current-state docs must distinguish:

- implemented,
- tested,
- built but not operationally validated,
- planned,
- deprecated or historical,
- known stuck/broken behavior.

Never describe a feature as operationally complete only because code exists.
