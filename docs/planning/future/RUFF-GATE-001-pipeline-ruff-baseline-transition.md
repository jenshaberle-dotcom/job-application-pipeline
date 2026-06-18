# RUFF-GATE-001 — Pipeline Ruff Baseline Transition

Status: planned
Project: job-application-pipeline
Owner: Jens / MCP-supported project control
Created: 2026-06-18
Scope: Pipeline quality gates, Ruff baseline, MCP customer-loop application
Runtime impact: none
Database impact: none
Scheduler impact: none
Source/gate/matching impact: none in this planning slice

## Problem

The pipeline currently treats `pytest` as the hard functional validation gate, while full-repository Ruff is not yet a hard gate because a historical Ruff baseline exists.

On 2026-06-18, the first explicit Ruff baseline review showed 88 Ruff findings while the functional test suite remained green with 1076 passing tests. `RUFF-BASELINE-001B` removed the critical `F821` undefined-name findings, reducing the full Ruff diagnostic from 88 to 84 findings.

This means Ruff is not cosmetic. It exposes quality debt that can hide real defects, weaken review confidence, and turn red checks into accepted background noise if not handled deliberately.

## Decision direction

Ruff must become a hard quality gate for the pipeline, but not by abruptly switching the current red baseline into a permanent blocker without analysis.

The transition must be controlled:

1. Critical rules are hard immediately.
2. New Ruff findings must not be introduced.
3. Existing Ruff baseline findings must be reduced or explicitly governed.
4. The final target state is `ruff check .` as a hard green gate.

## Current baseline categories after critical repair

After `RUFF-BASELINE-001B`, `F821` should be zero.

Remaining baseline classes are expected to be:

- `F401` unused imports
- `F541` f-string without placeholders
- `F841` assigned-but-unused variables
- `E402` module import not at top of file

The non-E402 classes are expected to be mostly safe cleanup candidates. `E402` is policy-sensitive because many historical scripts use a local `sys.path.insert(...)` pattern before project imports.

## Gate policy during transition

Until the baseline is resolved, the pipeline should use this transitional policy:

- `F821` is always hard-blocking.
- Any new Ruff finding in modified Python files is hard-blocking.
- The total Ruff baseline must not grow.
- Python changes should run targeted Ruff checks for changed files.
- Full `ruff check .` remains a diagnostic until baseline resolution, but its output must not be ignored.
- Every Ruff baseline reduction must be tracked by a named PR or documented policy decision.

## Backlog path

### RUFF-BASELINE-001B — Critical repairs

Status: in progress / merge candidate

Goal:
- Remove all `F821` undefined-name findings.
- Avoid expanding command execution or mutating capabilities.
- Preserve functional test green state.

Expected evidence:
- Targeted `ruff --select F821` passes for affected files.
- `pytest -q` remains green.
- Full Ruff count decreases from 88 to 84.

### RUFF-BASELINE-001C — Safe cleanup

Status: next recommended implementation block

Goal:
- Fix safe Ruff findings: `F401`, `F541`, and selected `F841`.
- Avoid `E402` in this block.
- Keep changes small and reviewable.

Expected value:
- Major noise reduction.
- Ruff output becomes easier to interpret.
- Future new errors become more visible.

Expected risk:
- Low for `F401` and `F541`.
- Low to medium for `F841`, because unused variables can indicate either real dead code or an incomplete logic path.

### RUFF-BASELINE-001D — E402 import-policy decision

Status: planned, separate from safe cleanup

Goal:
- Decide whether historical script `sys.path.insert(...)` patterns are accepted, configured away, or refactored.
- Avoid silent import-policy drift.
- Prefer explicit configuration or packaging cleanup over ad-hoc local ignores.

Possible outcomes:
- Allow E402 in selected script/test paths with documented reason.
- Refactor scripts toward a cleaner invocation/import pattern.
- Use temporary allow-list plus later refactor campaign.

### RUFF-GATE-001 — Activate Ruff as a hard pipeline gate

Status: planned after baseline reduction/policy

Goal:
- Make `ruff check .` a hard green gate for the pipeline.
- Add or update validation documentation.
- Align PR workflow so Ruff cannot silently regress.

## MCP customer-loop application

This is a concrete example of applying the MCP control-loop pattern to a customer/target project.

Loop:

1. Observe target state
   - Pipeline exposes a red Ruff baseline while tests are green.

2. Classify risk
   - `F821` is critical and immediately blocking.
   - `F401/F541/F841` are quality cleanup candidates.
   - `E402` is a policy/architecture decision.

3. Apply bounded intervention
   - Fix only critical `F821` first.
   - Avoid mixing command-execution capability changes into a lint repair.

4. Validate outcome
   - Targeted Ruff class check.
   - Full test suite.
   - Full Ruff diagnostic count.

5. Record governance decision
   - Backlog entry documents why Ruff is becoming a hard gate and how the baseline transition works.

6. Tighten future gates
   - No new Ruff findings.
   - Baseline cannot grow.
   - Full Ruff becomes hard once baseline is resolved or explicitly governed.

## Non-goals

This planning slice does not:
- change runtime code,
- change DB schema,
- change scheduler behavior,
- change matching/search logic,
- configure Ruff,
- remove remaining Ruff findings,
- activate full Ruff as a hard gate immediately.

## Acceptance criteria

This backlog item is complete when:

- The transition policy is documented in the repository.
- `RUFF-BASELINE-001C` and `RUFF-BASELINE-001D` are represented as explicit follow-up work.
- Future pipeline PRs do not treat Ruff output as disposable noise.
- The final activation path toward full hard `ruff check .` is clear.
