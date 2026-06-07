# DOC-002 Documentation Drift Baseline

## Purpose

This document records the current documentation drift baseline and the immediate correction strategy.

It is intentionally not the full Adrian/product-polish documentation campaign. It is the minimum truth-restoration layer required before the next large Search Intelligence mutation.

---

## Current Assessment

As of 2026-06-07, the documentation drift is material.

The project has moved faster than the narrative in several areas:

- Search Intelligence has grown from a concept into a multi-agent operating layer.
- Employer-origin discovery, URL finding, recovery, gates, connector generation and Control Center flows now interact.
- StepStone Discovery Iteration Closure / Wave Search Intelligence exists in code and tests, but its operational effectiveness still needs validation.
- Candidate reprocessing exists as a conservative dry-run-first benchmark, but the next validation campaign still needs a consolidated metrics frame.
- Governance rules emerged through real project work and chat handoffs, but were not yet represented as a repo-level operating model.

Documentation drift is therefore classified as **PDI-3** until the current-state docs are reconciled.

---

## Immediate Correction Strategy

DOC-002 is not a rewrite of all documentation.

It should establish a reliable baseline by making the following visible:

| Area | Current Truth Required |
|---|---|
| Governance | The lightweight checks are now repo-level rules, not chat-only habits. |
| Search Intelligence | Current state must show what is implemented, unvalidated, stuck or planned. |
| Wave Search Intelligence | Must be described as built/partly tested, but not yet operationally proven. |
| Candidate Reprocessing | Must be documented as the next validation block, not a permanent workaround. |
| URL Finder | Must expose selected, alternative and rejected URL evidence with confidence. |
| Scheduler/Orchestrator | Must not be presented as fully solved until operational validation exists. |
| Large design polish | Deferred until after the validation block produces stable truth. |

---

## Required Current-State Labels

Use these labels consistently in documentation:

| Label | Meaning |
|---|---|
| Implemented | Code exists and the expected local tests pass. |
| Tested | Unit/integration tests cover the relevant behavior. |
| Operationally validated | The behavior has been observed working in realistic project data. |
| Built but unvalidated | Code/tests exist, but practical effectiveness is not proven yet. |
| Planned | Design target exists, no reliable implementation yet. |
| Historical burden | Data or behavior exists for history/learning, not current product truth. |
| Deprecated | Should not guide future implementation except for migration/cleanup context. |

---

## Current Drift Hotspots

### 1. Search Intelligence Current State

The current-state narrative must include the operational funnel:

```text
Market Sensors
→ Candidate Promotion / Türsteher
→ URL Finder
→ Evidence Gates
→ Connector Build Candidate
→ Bronze / Silver / Gold
→ UI / Operations
```

The older vocabulary-only flow is no longer sufficient as the main operational description.

### 2. Wave Search Intelligence

Wave Search Intelligence / StepStone Discovery Iteration Closure must be shown as:

- implemented,
- covered by first tests,
- intended to temporarily suppress known companies to expose new companies,
- not yet proven as effective in the running scheduler/orchestration path.

### 3. Candidate Reprocessing

EO-002B should be documented as the next validation campaign:

**EO-002B Candidate Reprocessing & URL Finder Validation**

It uses a controlled guest-list approach to validate whether stuck candidates can progress with the current URL Finder and gates before changing Türsteher logic.

### 4. Governance

System Impact Check, Project Drift Index, Lessons Learned Check, White Whale Backlog, Conversation Health Check and Reflection Pass must be treated as reusable project rules.

### 5. Large Documentation Campaign

The large Adrian-quality documentation/design pass remains important, but it should follow the next validation block. Otherwise it risks polishing an unvalidated intermediate state.

---

## Done Criteria for DOC-002

DOC-002 is sufficient when:

- governance docs exist and are linked,
- README points to governance and current-state docs,
- Search Intelligence current state has a current operational snapshot,
- roadmap shows the immediate sequence:
  - DOC-001/DOC-002,
  - EO-002B,
  - metrics decision report,
  - Wave/Scheduler validation,
  - large documentation/design polish,
- tests guard the presence of the new baseline documents.

DOC-002 is not expected to fix every historical source-analysis note.
