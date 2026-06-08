# VALIDATE-001A Unified Validation Command

Status: reference contract  
Scope: Tooling/Governance  
Implemented by: `scripts/run_validate001_unified_validation.py`

VALIDATE-001A provides one boring, repeatable entry point for local validation
before commit, PR, merge cleanup, or handover. It does not replace the underlying
checks. It orchestrates them, keeps console output compact, and writes detailed
JSON/Markdown reports under `exports/`.

## Purpose

The command exists to reduce chat-to-chat drift in validation instructions.

It should answer:

- Which validation profile was run?
- Which required checks passed or failed?
- Where is the detailed report?
- What is the next safe action after validation?

## Profiles

The command supports three profiles:

| Profile | Intended use | Includes full pytest |
|---|---|---|
| `quick` | Fast tooling-contract check during local patch iteration. | no |
| `commit` | Default before commit and PR. | yes |
| `handover` | Stronger handover check with state and inspection reports. | yes |

Default command:

```bash
python scripts/run_validate001_unified_validation.py
```

This defaults to the `commit` profile.

## Commit and PR contract

Before commit or PR, use:

```bash
python scripts/run_validate001_unified_validation.py --profile commit
```

The `commit` profile includes:

- tooling script compilation
- targeted Tooling/Governance tests
- HANDOVER-001 contract validation
- RULES-001 index validation
- full `pytest -q`
- `git diff --check`
- `git diff --cached --check`
- `git status --short` as reported context

`git status --short` is reported but not treated as a required failure because a
pre-commit validation normally runs while files are intentionally modified.

## Handover contract

For a stronger handover-oriented check, use:

```bash
python scripts/run_validate001_unified_validation.py --profile handover
```

The `handover` profile also generates fresh STATE-001 and INSPECT-001 reports.

## Outputs

Each run writes:

- `exports/validate001_unified_validation_<timestamp>.json`
- `exports/validate001_unified_validation_<timestamp>.md`

The terminal output stays intentionally compact and prints only:

- profile
- overall status
- required failure count
- optional warning count
- report paths

## Safety boundary

VALIDATE-001A is validation tooling only.

It may:

- read repository files
- run local tests
- run read-only documentation and state validators
- write validation reports under `exports/`

It must not:

- perform external network requests
- write to the database
- mutate pipeline data
- activate sources or connectors
- change candidates, gates, Bronze/Silver/Gold, scheduler, or UI state
- create commits, PRs, or merges

## Relationship to STATE, INSPECT, HANDOVER and RULES

VALIDATE-001A sits after STATE-001A, INSPECT-001A, HANDOVER-001A and RULES-001A
in the Tooling/Governance sequence.

It uses those contracts as inputs and validation targets. It does not supersede
them.

## Relationship to NEXT-001

NEXT-001 should build on VALIDATE-001A by making the next safe action easier to
select after validation has passed or failed.

VALIDATE-001A answers: "Is the current state valid enough to proceed?"

NEXT-001 should answer: "What should happen next?"

## Anti-patterns

Do not use VALIDATE-001A to hide failing checks behind a green summary.

Do not add product decisions, external source calls, DB mutations, connector
activation, or candidate state transitions to this command.

Do not paste long validation output into chat when the generated report can be
attached or summarized instead.
