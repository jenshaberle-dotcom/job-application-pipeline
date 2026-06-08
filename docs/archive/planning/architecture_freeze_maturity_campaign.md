# Architecture Freeze and 90+ Maturity Campaign

Status: active planning baseline
Mode: architecture freeze

## Goal

Reach functional 90+ maturity before polish.

This means the project should become architecturally stable, safe, measurable and generically useful before spending major effort on visual polish or new feature breadth.

## Active rule

New ideas are not automatically added to the active plan.

A new idea can change the active plan only when it plausibly improves a named maturity area by roughly 15 to 20 points or closes a measured pipeline gap.

Otherwise it goes to the White-Whale or product backlog.

## Active maturity path

| Order | Block | Purpose |
|---:|---|---|
| 1 | ARCH-001 Safety, Security and Pipeline State Architecture Baseline | freeze contracts before more automation |
| 2 | EO-002E Gate Stop / Next-Safe-Action Evidence Analysis | understand what happens after selected URLs |
| 3 | EO-002F URL Finder Runtime Hardening | make probing safe, bounded and diagnostic |
| 4 | EO-002G Detail Evidence Discovery | find concrete job/detail evidence generically |
| 5 | EO-002H Candidate Promotion Calibration | tune Türsteher with downstream evidence |
| 6 | EO-002I Wave/Scheduler Stabilization | automate only after single-step maturity improves |
| 7 | EO-002J Operations/UI Observability | make review and operations actively usable |
| 8 | DOC-003 Adrian Reconciliation | align docs with actual system state |
| 9 | BENCH-001 Candidate Reality Benchmark | validate 20 to 40 diverse candidates |

## Current score baseline

| Area | Current estimate | Functional 90+ requirement |
|---|---:|---|
| Architecture contract | 78 | explicit contracts and state machine |
| Safety model | 55 | safety zones and permission enforcement |
| Security model | 38 | external request, secret and UI write boundaries |
| Diagnosis / observability | 64 | reports connect URLs, gates, stops and next actions |
| Operational generics | 48 | works across diverse candidates, not only known cases |
| Product maturity | 42 | coherent operation without demo-only assumptions |

## Parking rule

Saving an idea does not mean forgetting it. White whales are parked until their expected impact is large enough or the maturity path reaches the relevant area.
