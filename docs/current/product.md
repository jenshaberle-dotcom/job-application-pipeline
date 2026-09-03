# Product Current Truth

Status: current truth  
Project character: **A — Intent Locked**  
Active product track: **PRODUCT-RECOVERY-001 / issue #783**

## Product authority

This file is the short current-product summary. The detailed product contract is authoritative under `docs/reference/product-contract/`:

1. `PRD.md`
2. `PRODUCT_DECISION_REGISTER.md`
3. `ACCEPTANCE_SCENARIOS.md`
4. `TRACEABILITY.md`

Jens owns product intent. Implementation, tests, migrations and historical behavior do not silently redefine that intent.

## Product in one sentence

The Job Application Pipeline is a personal Search Intelligence and application-preparation product that should turn broad market discovery into a small set of **current, employer-origin-verified, explainably ranked jobs** and then into truthful review-ready application documents.

```text
Discover -> Verify Employer Origin -> Prove Current Vacancy
-> Bronze -> Silver -> Assess -> Hard Filter -> Rank
-> recommend up to five quality-threshold jobs
-> Application Workspace -> CV/letter DOCX/PDF/ZIP draft_for_review
```

## Current product checkpoint

The salvaged DEMO-001 path is retained on `main` and published as `v0.1.0-demo.1`.

The checkpoint proves that the core pieces can work together:

- React Product V1 Control Center;
- aggregator discovery separated from Employer-Origin action authority;
- Bronze/Silver/Gold data layers and Product V1 read models;
- live vacancy checks and detail-fingerprint refresh;
- assessment, capability-fit, hard-filter and deterministic ranking layers;
- Candidate Facts and exact-vacancy grounding;
- provider-backed application drafting with evidence-first fallback;
- local CV + application-letter export as DOCX/PDF plus ZIP;
- GitHub Release Management with release notes and explicit bug-fix history.

This is a **demo checkpoint, not production-readiness**.

## What DEMO-001 exposed

The demo window revealed a material gap between subsystem maturity and reliable product value:

- stale jobs could remain visible as current;
- discovery/aggregator URLs could leak into operator action surfaces instead of resolved Employer-Origin URLs;
- normal operation produced too few fully assessed/rankable jobs;
- reaching a broader rankable set required multiple repair/refill helpers rather than one normal product flow;
- provider integration had schema and surface-budget defects;
- application files were technically exportable before they were visually/content-wise close to submission quality;
- frontend runtime work could be technically green while still producing multi-minute operator startup.

These are Product Recovery inputs. They must not be hidden by demo-only logic or weaker gates.

## Current operator evidence boundary

Local operator validation on 2026-09-03 established runtime evidence that is **not shipped in Git**:

- 30 bounded candidates inspected;
- 28 observed live;
- 7 live role/Candidate-Fact matches;
- 6 selected vacancies refreshed after detail drift;
- 6 jobs became `rankable` after evidence-backed capability/hard-filter review;
- only one of those six was above the currently approved `PD-051` minimum quality threshold of **70/100**.

Therefore **6 rankable jobs does not mean five authoritative Top-5 recommendations**. The product contract still forbids filling Top 5 with below-threshold jobs merely to reach five.

## Active product objective — PRODUCT-RECOVERY-001

The primary product truth is now one repeatable normal cold-to-application path:

```text
market discovery
-> Employer-Origin resolution
-> freshly verified exact vacancy
-> Bronze / Silver
-> assessment
-> capability fit
-> hard filter
-> deterministic ranking
-> >=5 current Employer-Origin jobs meeting the approved recommendation contract
-> Application Workspace
-> coherent review-ready CV/letter package
```

Primary recovery metric:

**five current Employer-Origin jobs that pass the approved product gates and recommendation threshold, with at least one application package requiring only small human edits.**

The target must be reached by improving truth propagation, freshness, assessment/ranking throughput and application quality — **not by lowering evidence requirements or silently weakening the 70/100 product threshold**.

## Current product boundaries

### Discovery vs Product authority

BA, StepStone, GuteJobs and similar aggregators are valuable discovery evidence. They are not final Product/Application action authority. A recommended/actionable job requires a current Employer-Origin vacancy path or another explicitly approved equivalent origin-evidence path.

### Rankable vs recommended

`rankable` means required Product V1 evidence/gates and score components are complete enough to rank. It does **not** automatically mean Top-5 eligible.

Current approved Top-5 contract:

- at most five jobs (`PD-050`);
- minimum overall quality 70/100 (`PD-051`);
- hard-filter failures or unresolved required evidence cannot enter (`PD-053`, `PD-054`);
- ranking reasons, components and uncertainty must be visible (`PD-055`, `PD-056`).

### Application preparation

Application generation is an explicit operator action. Approved Candidate Facts remain the factual authority for candidate claims; exact vacancy evidence is the job-specific authority. During the explicit Generate action, approved base CV/letter text may be shared with the configured provider for structure/style adaptation. Generated artifacts remain `draft_for_review` and no automatic application submission or send authority exists.

## Current non-goals

Until PRODUCT-RECOVERY-001 closes the core path:

- no broad new deterministic hardening without measurable effect on the primary product metric;
- no ML expansion beyond already-approved foundation work;
- no post-application feature expansion beyond preserving the existing contract/backlog;
- no new demo-only orchestration or fabricated success paths;
- no cloud/Kafka/Spark expansion without demonstrated product value.

## Current success test

The repository is not considered product-recovered because individual subsystems or thousands of tests are green. The relevant acceptance question is:

> Can one normal operator flow reliably produce current Employer-Origin recommendations that satisfy the approved product contract and then create a high-quality review-ready application package without repair campaigns between stages?

Until the answer is repeatably yes, PRODUCT-RECOVERY-001 remains the primary product line.
