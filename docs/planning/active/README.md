# Active Planning

Status: current planning truth  
Last rebaseline: Freeze II — Source Truth & Connector Reliability; `#1038` active, S0 baseline first

## Product authority

The Pipeline is a **Class A — Intent Locked** project.

The active engineering backlog remains the implementation inventory, but it is subordinate to the operator-approved product contract under `docs/reference/product-contract/`.

DON may adapt technical design and sequencing. It may not infer unresolved product behavior or treat the current implementation as the desired product definition.

`PRD-001` remains the progressive product-alignment gate. It does not block safety, defect, evidence, lifecycle or bounded deterministic acquisition hardening that preserves existing product authority.

## Current steering rule

**Freeze II — Source Truth & Connector Reliability / issue #1038 is the current campaign authority.**

Read these first:

1. `FREEZE-II-SOURCE-TRUTH-CONNECTOR-RELIABILITY.md` — canonical S0-S6 sequence and acceptance gates;
2. `../../current/REENTRY.md` — current cross-project/product re-entry state;
3. `acq_generalization_90_reentry.md` and `acq_generalization_90_reentry.json` — retained acquisition-builder evidence used by S1/S2, not current campaign sequencing;
4. `F4A-R2-OPERATOR-VISIBLE-REQUIREMENT-EVIDENCE.md` and `F4A-R7-SKILL-EVIDENCE-RELIABILITY.md` — retained field/provenance hardening evidence.

The immediate action is **S0 current truth baseline**. It must re-measure current source/connector counts, family concentration, deterministic first failures and Bronze->Silver->Product/CC metadata reliability before any new source activation.

## Historical #676 deterministic acquisition metric — NOT current authority

Retained historical checkpoint:

- distinct Employer-Origin candidates: `65`;
- strict functioning deterministic acquisition: `36/65 = 55.4%`;
- old target numerator at N=65: `59/65 = 90.8%`;
- historical materialized regression cohort: `36/40` strict proven.

These figures remain useful predecessor evidence only. Freeze-II S0 establishes the current denominator and current coverage pressure. Builder `recipe_ready` remains diagnostic and never substitutes for materialized strict Product connector coverage.

## Retained #676 frontier

Completed reusable work includes:

- fresh-10 root-cause clustering;
- balanced Origin V2 breadth-first planning with Origin failures `18 -> 8` and zero earlier-stage regressions;
- inventory surface and bridge audits;
- V3 provider-inventory composition with Inventory failures `17 -> 16`;
- exact 65-candidate first-failure cohorts;
- historical Workday CXS route recovery;
- live Clarios proof through employer authority -> Workday board -> CXS inventory -> concrete public detail;
- same-host Workday CXS detail proof projection without weakening `genuine_job_detail_proof`;
- bounded Workday acquisition composition: root GET -> exact CXS inventory POST -> exact same-host CXS detail GET;
- V4 Workday residual overlay;
- evidence-bounded first-party -> portal delegation class;
- builder-owned monotonic residual rewrite contract `rewrite_residual_suffix()`;
- V5 ordered residual composition: `V3 -> Workday -> portal -> remaining residuals`.

V5 delivery:

- merge PR `#685`;
- merge commit `45f99c1919e6869451b6301bf41a6d3d12ba7c78`;
- exact-head Pipeline CI `#887`: success;
- exact-head Re-entry `#1454`: success.

No numerical V5/product lift is claimed until the same 65-candidate cohort is replayed from the canonical WSL runtime/database.

## Retained #676 deterministic sequence

1. Resolve the current `origin/main` and any live #676 work PR before creating or editing a branch.
2. Run `scripts/run_deterministic_connector_builder_layer_audit_v5.py` against the same 65-candidate cohort from the canonical WSL runtime/database.
3. Record exact V3 -> V4 -> V5 transitions, including Workday and portal promotions, without changing the product numerator.
4. Re-cluster the V5 residual first-failure population after the measured generic lift.
5. Select the next reusable deterministic class by population lift, evidence strength and boundedness — never by named-employer convenience.
6. Materialize only stable evidence-backed connector recipes; rerun unchanged strict E2E acquisition before changing product coverage.
7. Admit residuals to the LLM booster only when no remaining bounded generic deterministic hypothesis is supported by evidence.

Every new mutating slice must branch from the then-current `origin/main` in a declared worktree. Historical #676 feature branches are not continuation bases.

## Connector-builder composition rule

The canonical layer order remains:

`identity -> origin -> origin_reachability -> delegation -> provider -> inventory -> detail -> proof -> recipe`

Residual adapters are not allowed to rewrite arbitrary history. The shared builder contract requires each adapter to declare the exact current first-failure it handles and the earliest layer whose evidence changes. All earlier layers are preserved exactly, and the rewrite may never introduce an earlier first failure.

Current residual ordering is explicit:

```text
V3 base
  -> Workday CXS adapter if first_failure == inventory
  -> bounded portal adapter if first_failure still == inventory
  -> residual cohort
```

This is diagnostic composition. Future materialized connectors must compile only the evidence-backed capabilities required by that candidate; they must not blindly probe every registered adapter.

## Workspace / migration state

The 2026-08-28 canonical-workspace migration is **fully merged and closed as a migration phase** for #676.

- canonical persistent checkout authority: WSL `main` under `PROJECT-LOCAL-WORKSPACE.json`;
- old PR #678: closed and superseded, never merged;
- old branch ancestry was not imported;
- qualified old content was harvested as one ancestry-free commit on current-main lineage;
- delivery PR #682: merged;
- migration delivery merge: `6af34cb54a9bbf29ffc257d1109f495d08d1678d`.

Historical migration checkpoint files remain retained provenance while #676 evidence is reused by Freeze-II S1/S2. Their filenames do not make them disposable.

Retention rule: **qualified content is preserved on main; superseded branch/worktree cleanup is a separate DRJ technical action requiring fresh local observation.** The repository mailbox remains `NO_REQUEST` unless a fresh hygiene pass establishes exact safe retirement candidates.

See `acq_generalization_90_reentry.md` for retained ACTIVE/PRESERVE/SUPERSEDED/disposable dispositions; Freeze-II #1038 owns current sequencing.

## Active control surfaces

1. `FREEZE-II-SOURCE-TRUTH-CONNECTOR-RELIABILITY.md` — **current Freeze-II campaign authority**.
2. `../../current/REENTRY.md` — canonical current re-entry and installed Product truth.
3. `../../reference/product-contract/README.md` — product authority and decision status.
4. `prd001_product_intent_rebaseline.md` — progressive PRD-alignment gate.
5. `acq_generalization_90_reentry.md` / `.json` — retained deterministic acquisition evidence for S1/S2.
6. `acq_generalization_90_target.md` — retained >=90% acquisition target; denominator must be rebaselined by S0.
7. `deterministic_connector_builder_layers.md` — evidence-driven builder and residual-adapter architecture.
8. `F4A-R2-OPERATOR-VISIBLE-REQUIREMENT-EVIDENCE.md` — source-to-operator field/provenance baseline.
9. `F4A-R7-SKILL-EVIDENCE-RELIABILITY.md` — deterministic-before-ML semantic evidence baseline.
10. `backlog_refinement.md`, `backlog_catalog.json`, `roadmap.md` — broader inventory/sequence references.

## Lifecycle truth already closed

Current main includes both reusable recurring lifecycle classes:

- `#502/#668`: exact-detail recurring health reconciliation;
- `#669/#670`: verified complete-inventory absence deriving `not_seen/complete_inventory` with atomic negative persistence and without rewriting legacy Bronze authority.

These are completed deterministic layers, not current blockers.

## Deterministic / booster / ML sequencing

Development order:

```text
deterministic hardening -> LLM booster engineering -> ML algorithm engineering
```

Productive decision order:

```text
deterministic -> ML algorithm -> booster
```

For acquisition, the booster remains deferred while #676 exposes evidence-backed deterministic classes.

The StepStone phrase `ML-first` refers to Machine-Learning-Engineer search terms, not to the future ML-algorithm layer.

Matching/ranking behavior remains product-intent gated where required.

## Canonical target profile

The repository currently records:

- Foundation: Machine Learning Engineer.
- Technical focus: Data Engineering and data-centric ML systems.
- Future direction: AI Reliability / Data & AI Reliability Engineering.
- GenAI is a cross-cutting engineering competency, not a separate target profile.

This hierarchy remains recorded repository truth pending explicit confirmation in the product decision register. No runtime or product behavior should silently expand it.

## Truth rules

- Operator-approved product requirements and scenarios define desired behavior.
- Repository code, tests and migrations are implementation truth.
- DB/runtime/live bounded evidence is required for live-state claims.
- Merged PRs prove implementation, not current runtime health or product desirability.
- Reference/archive artifacts may supply ideas; they do not steer directly.
- Chat and assistant memory are not project truth.
- Missing evidence yields inspection/blocked state, never a guessed continuation.
- Missing product intent yields `open_operator_decision`, never an inferred default.
- Technical failed, cancelled, skipped or startup-failed acquisition runs are non-evidence.
- A detector exhausting its currently instrumented surfaces does not prove the underlying deterministic problem class is globally exhausted.
- DRJ never infers semantic value from age/path/name; project semantic dispositions are explicit in current truth/re-entry.

## Parallel work allowed during PRD-001

- safety and security fixes;
- defect repair;
- documentation consistency;
- read-only evidence recomputation;
- CI/runtime stabilization;
- bounded deterministic acquisition diagnostics preserving proof/authority boundaries;
- bounded lifecycle hardening;
- ML learning-foundation work that does not alter productive ranking/acquisition authority.

## Product-shaping work gated by PRD-001

- candidate apply semantics;
- Top-5 and ranking behavior;
- queue composition;
- operator review actions;
- target-profile interpretation;
- application intelligence;
- autonomous product decisions.

## Retained predecessor / parked tracks

- `#672` residual-cluster evidence remains retained predecessor input; any still-open technical class must be re-admitted through #676's current population/evidence model rather than resumed from stale sequencing text;
- `#671` StepStone wave-cycle plan/read-only hardening remains deferred behind the current deterministic acquisition frontier;
- `#522` LLM acquisition booster remains deferred until #676 reaches evidence-backed deterministic exhaustion;
- V1 application intelligence and later semantic enrichment;
- FREEZE-002 and REFACTOR-001;
- Cloud, outbox, Kafka and Spark;
- CV update automation;
- provider calls, scheduler changes and mutating paths without explicit gates.
