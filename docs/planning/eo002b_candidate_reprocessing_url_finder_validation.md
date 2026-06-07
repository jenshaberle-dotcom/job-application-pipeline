# EO-002B Candidate Reprocessing & URL Finder Validation

## Purpose

EO-002B is the next validation campaign after the governance and documentation drift baseline.

It deliberately uses a controlled guest-list approach instead of immediately weakening or rewriting the candidate promotion gate.

The goal is to validate whether relevant stuck or missing employer-origin candidates can progress when they are reset/reprocessed through the current URL Finder, evidence gates and next-safe-action flow.

---

## Why This Block Exists

The current diagnosis is not simply "the Türsteher is too strict".

The larger risk is that multiple layers may contribute to false negatives:

```text
Market Sensors
→ Candidate Promotion
→ URL Finder
→ Evidence Gates
→ Connector Build Candidate
→ Bronze / Silver / Gold
→ UI / Operations
```

Before changing the gate logic, EO-002B should measure where candidates actually stop.

---

## Campaign Name

Primary name:

**EO-002B Candidate Reprocessing & URL Finder Validation**

Recommended implementation naming:

**SI-015 / EO-002B**

Rationale:

- `EO` keeps the employer-origin campaign context visible.
- `SI` keeps the repository naming aligned with Search Intelligence as the responsible domain.

---

## Candidate Cohorts

### A-Tier: High-Value False-Negative Candidates

Candidates that are strategically relevant and suspected false negatives.

Examples:

- Hannover Rück
- other explicitly valuable employers from external reality checks

### B-Tier: Stuck or Review-Required Candidates

Candidates already known to the system but blocked by URL recovery, manual review or evidence gates.

Examples:

- candidates in `manual_review_required`, `discovery`, `build_approval_required` or equivalent review states,
- candidates with plausible origin URLs but insufficient selected detail evidence.

### C-Tier: Broader Pipeline Candidates

Lower-confidence candidates useful for measuring generalization.

This tier should be bounded and must not become uncontrolled mass reprocessing.

---

## Metrics to Collect

For every candidate run, collect:

| Metric | Purpose |
|---|---|
| Candidate ID / company key | Stable tracking. |
| Candidate tier | A/B/C success comparison. |
| Initial status | Understand starting point. |
| Selected URL | URL Finder primary decision. |
| Alternative URLs | Plausible options not selected. |
| Rejected URLs | Negative evidence and safety boundary. |
| Confidence | Decision strength. |
| Risk level | Operational/legal/quality risk. |
| Gate stop | Where the candidate stops. |
| Next safe action | What the system recommends next. |
| Final status after run | Whether the candidate progressed. |
| Human review need | Whether automation remains blocked. |

---

## Execution Phases

### Phase 1 — Read-Only Inventory

Build the candidate guest list from database state.

No candidate state changes.

Expected output:

- selected candidates,
- tier assignment,
- reason for inclusion,
- current status/gate state,
- known URLs/evidence.

### Phase 2 — Dry-Run Reprocessing

Run the existing reprocess benchmark in dry-run mode first.

Expected boundary:

- no candidate rows changed,
- no gate rows changed,
- duplicate/preflight checks visible,
- active-controlled sources protected by default.

### Phase 3 — Controlled Apply

Only after Phase 1/2 are understood, apply reprocessing to the bounded guest list.

Expected boundary:

- explicit allow/apply flag,
- no active-controlled reset unless consciously included,
- snapshot before/after,
- audit output.

### Phase 4 — URL Finder Validation

Run candidates through the URL Finder / origin source discovery path.

Expected output:

- selected URL,
- alternatives,
- rejected URLs,
- confidence,
- risk level,
- provider/search evidence where available.

### Phase 5 — Gate Stop Analysis

Classify where each candidate stops:

- no plausible URL,
- URL selected but no concrete job evidence,
- concrete job evidence found but gate blocks,
- build candidate ready,
- activation/registration approval required,
- active controlled.

### Phase 6 — Decision Report

Produce a short decision report before the next implementation block.

The report should answer:

- Is the URL Finder good enough?
- Are gates too strict or just correctly defensive?
- Does the Türsteher need a guest-list bypass, a learning update or a real redesign?
- Does Wave Search Intelligence feed enough new candidates into the funnel?
- Which tier performs best and why?

---

## Non-Goals

EO-002B does not:

- add new market sensors,
- rewrite the Türsteher directly,
- activate connectors automatically,
- turn manual URL entry into the default success path,
- rely on CSV/Excel artifacts as pipeline inputs,
- bypass evidence gates silently.

---

## Done Criteria

EO-002B is done when:

- the candidate guest list is explicit and DB-backed,
- the dry-run benchmark output is reviewed,
- controlled apply is used only if safe,
- URL Finder metrics are collected for each candidate,
- gate stops are classified,
- A/B/C-tier success rates are visible,
- false-negative candidates such as Hannover Rück are explicitly evaluated,
- a decision report recommends the next block.

---

## Implementation Foundation — 2026-06-07

This block adds the first executable EO-002B foundation. It is intentionally split into two tools:

1. `scripts/run_employer_origin_reprocess_benchmark.py` remains the dry-run-first reset and next-safe-action benchmark. It now supports an explicit guest list via repeated `--company-key` arguments. Active-controlled candidates remain protected unless `--include-active-controlled` is passed.
2. `scripts/run_eo002b_url_finder_validation.py` is a read-only URL Finder validation runner. It executes the existing Origin Source Discovery agent for the selected guest list and writes a JSON review report under `exports/eo002b_candidate_reprocessing_url_finder_validation/`.

The URL Finder validation report contains:

| Field | Meaning |
|---|---|
| `selected_url` | URL Finder primary selected origin URL, if any. |
| `alternative_url_count` | Number of plausible non-selected URL alternatives. |
| `rejected_url_count` | Number of rejected URLs and safety/evidence negatives. |
| `confidence_score` | URL Finder confidence for the outcome. |
| `decision` | Origin Source Discovery decision. |
| `success_tier` | A/B/C/D validation tier for campaign comparison. |
| `false_negative_candidate` | Marks critical false-negative validation candidates such as Hannover Rück. |
| `gate_stop` | Reserved for the follow-up gate-stop join/report. |

### Example: read-only guest-list URL Finder validation

```bash
python -m scripts.run_eo002b_url_finder_validation \
  --benchmark-label eo002b_20260607_url_finder_guest_list \
  --company-key hannover_ruck \
  --company-key hdi \
  --company-key vhv_gruppe \
  --target-location Hannover \
  --search-provider none \
  --include-raw-results
```

Optional offline search replay for provider-independent validation:

```bash
python -m scripts.run_eo002b_url_finder_validation \
  --benchmark-label eo002b_20260607_url_finder_replay \
  --company-key hannover_ruck \
  --search-results-json exports/manual_review/hannover_ruck_search_results.json \
  --no-probe
```

### Example: dry-run guest-list reprocessing plan

```bash
python -m scripts.run_employer_origin_reprocess_benchmark \
  --benchmark-label eo002b_20260607_guest_list \
  --company-key hannover_ruck \
  --company-key hdi \
  --company-key vhv_gruppe \
  --snapshot-before \
  --reset-candidates \
  --run-next-safe-actions \
  --target-location Hannover \
  --reviewed-by jens
```

Only after the dry-run output and duplicate preflight are reviewed should `--apply` be considered.

### Explicit Boundaries

This implementation does not:

- register connectors,
- activate sources,
- write candidate URLs from URL Finder output,
- write Bronze/Silver job data,
- change scheduler behavior,
- bypass gates,
- use exports/CSV/Excel files as hidden pipeline inputs.

The JSON report is a human-readable review output only.

<!-- EO-002C-DECISION-REPORT:START -->
## EO-002C Decision Report Scaffold — 2026-06-07

EO-002C is the read-only reporting layer after EO-002B.

Tool:

```bash
python -m scripts.run_eo002c_reprocessing_decision_report \
  --benchmark-label eo002c_20260607 \
  --report-json exports/eo002b_candidate_reprocessing_url_finder_validation/<eo002b-report>.json
```

Default output:

```text
exports/eo002c_reprocessing_metrics_decision_report/<label>_decision_report.json
exports/eo002c_reprocessing_metrics_decision_report/<label>_decision_report.md
```

EO-002C reads EO-002B JSON reports and aggregates:

| Metric | Purpose |
|---|---|
| selected URL rate | Decides whether the URL Finder is strong enough for gate analysis. |
| A/B-tier rate | Shows how often candidates produce high or usable URL evidence. |
| success tier counts | Compares A/B/C/D campaign outcomes. |
| gate stop counts | Shows whether failures cluster around specific gates. |
| decision counts | Shows how the Origin Source Discovery agent decided. |
| false-negative candidates | Keeps high-value missing employers visible. |

Boundary:

- no candidate write,
- no gate write,
- no connector registration,
- no source activation,
- no scheduler change.

The report is a decision aid. It must not silently approve gate changes, scheduler automation or connector activation.
<!-- EO-002C-DECISION-REPORT:END -->
