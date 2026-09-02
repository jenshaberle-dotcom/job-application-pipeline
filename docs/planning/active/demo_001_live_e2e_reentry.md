# DEMO-001 — live E2E demo re-entry

Status: **ACTIVE — DEMO MODE**  
Owner issue: `#707`  
Demo date: `2026-09-03`

## Operator outcome

Demonstrate the existing Job Application Pipeline as one truthful product journey:

```text
discovery / market evidence
-> employer + origin
-> connector/source health
-> Bronze
-> Silver
-> Gold / Product V1
-> authoritative Top 5
-> select one current job
-> Application Workspace
-> source-grounded draft_for_review
```

The demo must end with a concrete reviewable application package, not merely a ranking screen.

## Priority override

The operator explicitly paused further ACQ-676 deterministic hardening for the demo window. ACQ-676 remains preserved and is not superseded or rejected. DEMO-001 is the current active product-delivery priority until the live demo is complete or the operator changes priority again.

`POST-MIGRATION-RESTART=PASS` is positive work-admission authority for this repository. Other projects' migration state is not a work-admission blocker for this already-PASS project. Portfolio all-PASS remains relevant only to separately coordinated portfolio-wide Warmrunner/DRJ/convergence work.

## Hard truth boundaries

- real current runtime/DB truth only;
- no fake Product V1 rows, fabricated Top-5 jobs, or demo-only success branches;
- aggregator evidence never becomes employer-origin/application authority by presentation alone;
- existing ranking and hard-filter authority remains unchanged;
- application generation is `draft_for_review` only;
- Candidate Facts and exact vacancy evidence remain the factual authority for generated claims;
- no automatic application submission or send action;
- no proof or source-authority weakening;
- existing React Control Center remains the demo UI; framework migration is deferred until after the demo.

## Definition of done

1. One reliable preflight exposes live demo readiness before presentation time.
2. Control Center shows current source/connector lifecycle and Bronze/Silver presence from existing truth.
3. Current Product V1 jobs and authoritative Top-5 are visible without fabricated fill.
4. One authoritative Top-5 employer-origin job can open a bounded Application Workspace.
5. Application Workspace shows source-document readiness, Candidate Fact readiness, job evidence, and draft boundaries.
6. An operator-triggered bounded drafting path can return a validated source-grounded `draft_for_review` package when all prerequisites are present.
7. The final UI visibly presents CV assistance + application-letter assistance + evidence/uncertainty while retaining explicit REVIEW REQUIRED / NO SUBMISSION AUTHORITY semantics.
8. Current Pipeline CI and Re-entry identity remain green.

## Current implementation

PR `#708` / branch `agent/707-live-demo-e2e-application-workspace` starts from exact `main@a56814fbe2ca397c532daad7d52687ae05aedb11`.

First slice:

- `scripts/run_product_v1_demo_preflight.py`;
- `tests/test_product_v1_demo_preflight.py`.

The preflight is read-only and selects a candidate only from existing authoritative Top-5 truth: employer-origin, validated, active, hard-filter passed, rankable.

## Immediate continuation

1. Qualify the demo preflight.
2. Run it against the live local runtime DB and inspect exact blockers.
3. Bind one selected Top-5 job to the existing `ProductV1ApplicationContext` using approved private Candidate Facts and approved base-document references.
4. Expose the bounded application workspace through the demo Control Center runtime.
5. Wire the existing source-grounded drafter behind an explicit operator action; provider request is allowed only after context readiness and never grants application/submission authority.
6. Add the final Control Center Application Workspace presentation.
7. Re-run the live preflight and exercise the actual demonstration sequence.

## Overnight continuation

From 22:00 on 2026-09-02 through 08:00 on 2026-09-03, hourly continuation should prioritize the narrowest remaining DEMO-001 blocker. Each slice must leave durable repository/Issue evidence and must never invent product truth to make the demo look greener.
