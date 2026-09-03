# DEMO-001 — live E2E demo re-entry

Status: **ACTIVE — LIVE READY / DEMO WALKTHROUGH**  
Owner issue: `#707`  
Demo date: `2026-09-03`  
Repository: `jenshaberle-dotcom/job-application-pipeline` (`id=1230805345`)

## Canonical checkpoint

Current merged repository truth:

```text
main = 31ac633e401f59824de1936d699148de51c62711
```

PR `#779` merged the final DEMO-001 live-readiness hardening after exact-head Pipeline CI `#1119` and Re-entry `#2075` passed.

The DEMO-001 backend/runtime readiness frontier is now closed for the current local demo dataset. A restart-safe live operator proof reached:

```text
DEMO_PREFLIGHT=PASS
DEMO_WORKSPACE_PROBE=PASS
DEMO_DRAFT_PROBE=PASS
PRODUCT_V1_LIVE_DEMO=READY
```

The proof used real current PostgreSQL/Product V1 truth, one bounded current-vacancy detail GET in the workspace probe, zero draft-handoff GETs, zero preflight provider requests and zero DB/application/submission/send writes.

The READY proof was executed on exact PR head `1d460228984dc4e224ce3a4a504598e78a77c088`; that content was merged unchanged by `#779` into the current main above. The canonical launcher reruns readiness before starting the server, so presentation start remains fail-closed.

## Required reads

Before continuing DEMO-001 work, read:

1. this file;
2. `docs/archive/demo-evidence/demo_001_live_ready_20260903.md`;
3. `scripts/run_product_v1_live_demo.py`;
4. `scripts/run_product_v1_demo_workspace_probe.py`;
5. owner issue `#707`, especially the latest live-ready checkpoint.

Chat history is supporting context only and must not override repository or current live-runtime truth.

## Proven current live product truth

The successful operator proof observed:

```text
CURRENT_ACTIVE=31
RANKABLE=1
TOP5=1
DEMO_SOURCES=3
SELECTED_JOB=434|Heartbeat AI GmbH|(Junior) Data Engineer - Data Platform (m/f/d)
```

For selected job `434`:

- `gold_product_v1_top_jobs` binds it as authoritative `product_rank=1`;
- Product V1 readiness is `rankable`;
- hard filter is `passed`;
- lifecycle is `active_confirmed`;
- application readiness is `ready_for_generation`;
- approved Candidate Facts are present;
- approved base CV and base application letter are present;
- local source PDF hashes match their approved DB metadata;
- exact current vacancy evidence is fetched once and then carried into the offline draft handoff.

No claim is made that there should be five Top-5 rows. Empty shortlist slots remain honest.

## PR #779 hardening now merged

`#779` closes the concrete live blockers found during manual operator execution:

1. removed arbitrary `LIMIT 200` windows from Product V1 job-readiness and application-readiness reads; this fixed the case where real Top-1 job `434` was present and application-ready in DB truth but absent from the truncated application-readiness payload;
2. canonical Jobs review surface now defaults to **all observed jobs, newest publication first** and supports operator filtering/search plus sorting by newest, oldest and fit;
3. displayed review rows retain a truthful deterministic fit surface; no missing Product V1 score is fabricated into ranking authority;
4. direct Python entrypoints are robust for both documented `python scripts/...` and module execution where supported;
5. the launcher now configures the same canonical private-document root as the demo server before readiness probes, so restart/re-entry no longer depends on a manually exported `PRODUCT_V1_PRIVATE_DOCUMENT_ROOT`;
6. the canonical default remains `<repo>/private_application_sources`, while an explicit operator override is preserved.

## Product outcome

The live demo must show one truthful vertical journey:

```text
Discover
-> Verify
-> Bronze / Silver / Gold evidence
-> Rank
-> authoritative current Top 5
-> select one real current job
-> Application Workspace
-> source-grounded draft_for_review
```

Presentation compression remains:

```text
Discover -> Verify -> Rank -> Prepare
```

That compression is presentation only and does not replace source, lifecycle, Product V1, ranking, Candidate Fact or application authority.

## Hard truth boundaries

- real current runtime/DB truth only;
- no fabricated Product V1 rows, Top-5 fill or demo-only success paths;
- employer-origin evidence remains required for application authority;
- approved hard-filter/ranking policy and read models remain authoritative;
- Candidate Facts plus exact current vacancy evidence remain factual authority for draft claims;
- application output is `draft_for_review` only;
- no automatic application submission or send authority;
- no source activation, ranking or application authority may be inferred from UI presentation;
- the React Product V1 Control Center is the canonical demo UI;
- local PostgreSQL/source/provider/scheduler/host mutations remain explicit operator actions.

## Canonical readiness authority

`scripts/run_product_v1_live_demo.py` remains the sole full demo readiness + launch path.

A genuine READY requires regenerated current artifacts:

```text
.runtime/demo/product_v1_demo_preflight.json
.runtime/demo/product_v1_demo_workspace_probe.json
.runtime/demo/product_v1_demo_draft_probe.json
```

and terminal result:

```text
PRODUCT_V1_LIVE_DEMO=READY
```

The launcher must continue to prove:

- coherent schema/tracking truth;
- real current employer-origin Product V1 data;
- authoritative Top-5 selection;
- approved Candidate Fact and source-document readiness;
- exact current vacancy binding;
- non-empty Candidate Fact claim plan;
- source-grounded provider-free draft proof;
- single-fetch workspace evidence handoff;
- zero preflight provider/write/submission/send authority.

## Sole next action

Synchronize the operator machine to current canonical main:

```bash
cd "$HOME/projects/job-application-pipeline"
git fetch origin main
git switch main
git pull --ff-only origin main
```

Then start the actual demo with the already-built frontend:

```bash
.venv/bin/python -m scripts.run_product_v1_live_demo --reuse-frontend
```

Do not manually export `PRODUCT_V1_PRIVATE_DOCUMENT_ROOT`; the launcher now resolves the canonical default itself and prints `DEMO_PRIVATE_DOCUMENT_ROOT=...` before readiness execution.

The launcher will rerun Preflight -> Workspace Probe -> Draft Handoff and start the Control Center only if all remain PASS.

## Operator walkthrough

Use the canonical route:

```text
Overall
-> Data Layers
-> Jobs
-> Top 5
-> Application
-> Applications
-> Sources
```

Verify particularly:

- `Discover -> Verify -> Rank -> Prepare` reads naturally;
- Data Layers can always be exited via normal navigation and `Esc`;
- Bronze/Silver/Gold values remain honest/null-preserving;
- Jobs defaults to all observed rows ordered newest-first and can be filtered/sorted;
- Top 5 never fabricates missing slots;
- selected Top-1 remains the real current job unless live truth changes;
- Application Workspace remains review-only / no-auto-submit;
- generated output remains `draft_for_review`;
- persistent truth ribbon remains visible: `Live DB truth · Review only · No submit / send`.

## Stop / acceptance rule

Do not open another backend-critical feature path before the actual presentation walkthrough result is known.

If the launcher remains READY and the walkthrough has no material defect, only bounded presentation/UX polish is appropriate before the demo.

If a real blocker appears, fix the **narrowest proven blocker** only and rerun the canonical launcher.

Post-demo immediate product extension remains `APP-TRACK-001` / issue `#737`:

```text
Prepared -> Applied -> Reply -> Interview -> Offer -> Closed
```

Email/recruiter communication is evidence, not silent application-state authority.
